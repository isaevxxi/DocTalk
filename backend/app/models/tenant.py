"""Tenant model - Organizations using the system."""

from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import String
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import AuditMixin, Base


class Tenant(Base, AuditMixin):
    """
    Tenant (Organization) model.

    Each tenant is an isolated organization (clinic, hospital, etc).
    All other tables reference tenant_id for RLS isolation.

    Note: Tenant table itself doesn't have tenant_id (it IS the tenant).
    """

    __tablename__ = "tenants"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Organization name",
    )

    slug: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        unique=True,
        index=True,
        comment="URL-safe identifier (e.g., 'central-clinic')",
    )

    is_active: Mapped[bool] = mapped_column(
        default=True,
        nullable=False,
        comment="Whether tenant is active",
    )

    # Compliance metadata
    data_localization_country: Mapped[str] = mapped_column(
        String(2),
        default="RU",
        nullable=False,
        comment="Data localization country code (ISO 3166-1 alpha-2)",
    )

    retention_years: Mapped[int] = mapped_column(
        default=7,
        nullable=False,
        comment="Data retention period (years) - 323-FZ requires 7",
    )

    # Contact
    contact_email: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="Primary contact email",
    )

    contact_phone: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="Primary contact phone",
    )

    # Relationships (for ORM convenience)
    # users = relationship("User", back_populates="tenant")
    # patients = relationship("Patient", back_populates="tenant")

    def __repr__(self) -> str:
        """String representation."""
        return f"<Tenant {self.slug} ({self.name})>"
