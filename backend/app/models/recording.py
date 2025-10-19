"""Recording model - Audio recordings of medical consultations."""

from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Enum as SQLEnum, ForeignKey, Index, Integer, String, BigInteger, Float
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TenantMixin, TimestampMixin


class RecordingStatus(str, Enum):
    """Status of audio recording processing pipeline."""

    UPLOADING = "uploading"  # File upload in progress
    PENDING_TRANSCRIPTION = "pending_transcription"  # Uploaded, waiting for ASR
    PROCESSING = "processing"  # Currently being transcribed
    COMPLETED = "completed"  # Transcription successful
    FAILED = "failed"  # Processing failed


class Recording(Base, TenantMixin, TimestampMixin):
    """
    Audio Recording model.

    Represents an audio file of a medical consultation.
    Files are stored in MinIO (S3-compatible storage).
    """

    __tablename__ = "recordings"
    __table_args__ = (
        # Composite index for common queries: fetch recordings by encounter and status
        Index("idx_recordings_encounter_status", "encounter_id", "status"),
        # Composite index for monitoring: fetch processing/failed recordings by tenant
        Index("idx_recordings_tenant_status", "tenant_id", "status", "created_at"),
    )

    # Primary key
    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        comment="Primary key (UUID)",
    )

    # Encounter reference
    encounter_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("encounters.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Encounter this recording belongs to",
    )

    # Storage metadata
    storage_key: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        unique=True,
        comment="Path/key in MinIO storage (e.g., 'tenant_id/encounter_id/recording_id.mp3')",
    )

    storage_bucket: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        default="audio-recordings",
        comment="MinIO bucket name",
    )

    # File metadata
    file_format: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="Audio format (mp3, wav, m4a, etc.)",
    )

    file_size_bytes: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        comment="File size in bytes",
    )

    duration_sec: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        comment="Duration in seconds (extracted after upload)",
    )

    # Processing status
    status: Mapped[RecordingStatus] = mapped_column(
        SQLEnum(RecordingStatus, name="recording_status", native_enum=False, create_constraint=True, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=RecordingStatus.UPLOADING,
        index=True,
        comment="Current processing status",
    )

    # Error tracking
    error_message: Mapped[Optional[str]] = mapped_column(
        String(1000),
        nullable=True,
        comment="Error message if status=failed",
    )

    retry_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Number of transcription retry attempts",
    )

    # Processing timestamps
    transcription_started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When transcription processing started",
    )

    transcription_completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When transcription completed (success or failure)",
    )

    # Metadata
    original_filename: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="Original filename from upload",
    )

    content_type: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="MIME type (audio/mpeg, audio/wav, etc.)",
    )

    # Relationships
    # encounter = relationship("Encounter", back_populates="recordings")
    # transcripts = relationship("Transcript", back_populates="recording")

    def __repr__(self) -> str:
        """String representation."""
        return f"<Recording id={self.id} encounter={self.encounter_id} status={self.status.value}>"
