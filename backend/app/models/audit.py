"""Audit event model - Append-only audit log with hash chain."""

from datetime import datetime
from typing import Any, Optional
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Index, LargeBinary, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TenantMixin


class AuditEvent(Base, TenantMixin):
    """
    Audit Event model - Immutable audit log with cryptographic hash chain.

    Every sensitive operation creates an audit event.
    Hash chain provides tamper-evidence:
    - current_hash = sha256(prev_hash || created_at || event_data)
    - Breaking the chain indicates tampering

    Compliance: 152-FZ (audit trail), 323-FZ (medical record access logging)
    """

    __tablename__ = "audit_events"

    # Primary key
    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        comment="Primary key (UUID)",
    )

    # Event metadata
    event_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
        comment="Type of event (e.g., 'note.create', 'patient.view', 'user.login')",
    )

    # User who performed the action
    user_id: Mapped[Optional[UUID]] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=True,
        index=True,
        comment="User who performed the action (NULL for system events)",
    )

    # Resource being accessed/modified
    resource_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Type of resource (e.g., 'note', 'patient', 'encounter')",
    )

    resource_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=False,
        index=True,
        comment="ID of the resource being accessed",
    )

    # Event payload
    event_data: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        comment="Event payload (changes, metadata, etc.) - no PII",
    )

    # Timestamp
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
        comment="When the event occurred",
    )

    # Hash chain for tamper-evidence
    prev_hash: Mapped[Optional[bytes]] = mapped_column(
        LargeBinary(32),  # SHA-256 = 32 bytes
        nullable=True,
        comment="Hash of previous audit event (NULL for first event in chain)",
    )

    current_hash: Mapped[bytes] = mapped_column(
        LargeBinary(32),  # SHA-256 = 32 bytes
        nullable=False,
        comment="SHA-256 hash of (prev_hash || created_at || event_data)",
    )

    # IP and user agent for security tracking
    ip_address: Mapped[Optional[str]] = mapped_column(
        String(45),  # IPv6 max length
        nullable=True,
        comment="IP address of the request",
    )

    user_agent: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
        comment="User agent string",
    )

    # Indexes and constraints for efficient querying and data integrity
    __table_args__ = (
        # Performance indexes
        Index("ix_audit_events_tenant_created_at", "tenant_id", "created_at"),
        Index("ix_audit_events_user_created_at", "user_id", "created_at"),
        Index("ix_audit_events_resource", "resource_type", "resource_id"),

        # Race condition prevention: Ensure no two events can reference the same prev_hash
        # This prevents hash chain "forks" when concurrent requests try to append events
        # NULL prev_hash is allowed (for first event in tenant's chain)
        UniqueConstraint(
            "tenant_id",
            "prev_hash",
            name="uq_audit_events_tenant_prev_hash",
            postgresql_nulls_not_distinct=False,  # Allow multiple NULL prev_hash (one per tenant)
        ),
    )

    def __repr__(self) -> str:
        """String representation."""
        return f"<AuditEvent {self.event_type} by user={self.user_id} on {self.resource_type}:{self.resource_id}>"
