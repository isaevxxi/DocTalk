"""Transcript model - ASR output and corrections."""

from datetime import datetime
from enum import Enum
from typing import Any, Optional
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Enum as SQLEnum, ForeignKey, Index, String, Text, Integer, Float, Boolean
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TenantMixin, TimestampMixin


class TranscriptStatus(str, Enum):
    """Status of transcript processing."""

    PROCESSING = "processing"  # ASR in progress
    COMPLETED = "completed"  # ASR successful
    FAILED = "failed"  # ASR failed


class Transcript(Base, TenantMixin, TimestampMixin):
    """
    Transcript model - ASR output and physician corrections.

    Stores the output from automatic speech recognition (ASR) engines.
    Multiple transcripts can exist for the same recording (different engines).
    Physician corrections create new versions for learning loop.
    """

    __tablename__ = "transcripts"
    __table_args__ = (
        # Composite index for fetching transcripts by recording and engine
        Index("idx_transcripts_recording_engine", "recording_id", "asr_engine"),
        # Index for finding corrected transcripts (ML training data)
        Index("idx_transcripts_corrected", "is_corrected", "corrected_at"),
    )

    # Primary key
    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        comment="Primary key (UUID)",
    )

    # Recording reference
    recording_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("recordings.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Recording this transcript belongs to",
    )

    # ASR engine identification
    asr_engine: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
        comment="ASR engine used (e.g., 'whisper-large-v3', 'vosk-ru', 'yandex-speechkit')",
    )

    asr_model_version: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="Specific model version (e.g., 'openai/whisper-large-v3-20231215')",
    )

    # Processing status
    status: Mapped[TranscriptStatus] = mapped_column(
        SQLEnum(TranscriptStatus, name="transcript_status", native_enum=False, create_constraint=True, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=TranscriptStatus.PROCESSING,
        index=True,
        comment="Processing status",
    )

    # Transcript content
    plain_text: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Plain text transcription (no timestamps or speaker labels)",
    )

    # Structured ASR output
    raw_output: Mapped[Optional[dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=True,
        comment="""
        Full ASR engine output including:
        - Timestamped segments
        - Speaker diarization
        - Confidence scores
        - Language detection
        Example: {"segments": [{"start": 0.0, "end": 2.5, "text": "...", "speaker": "A"}]}
        """,
    )

    # Processing metadata
    processing_time_sec: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        comment="ASR processing time in seconds",
    )

    average_confidence: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        comment="Average confidence score (0.0-1.0) from ASR engine",
    )

    language_detected: Mapped[Optional[str]] = mapped_column(
        String(10),
        nullable=True,
        comment="Detected language code (e.g., 'ru', 'en')",
    )

    # Speaker diarization results
    speaker_mapping: Mapped[Optional[dict[str, str]]] = mapped_column(
        JSONB,
        nullable=True,
        comment="""
        Mapping of pyannote speaker labels to semantic labels.
        Example: {"SPEAKER_00": "SPEAKER_0", "SPEAKER_01": "SPEAKER_1"}
        Can be manually updated to: {"SPEAKER_00": "DOCTOR", "SPEAKER_01": "PATIENT"}
        """,
    )

    diarization_metadata: Mapped[Optional[dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=True,
        comment="""
        Speaker diarization metadata:
        - num_speakers: int (number of speakers detected)
        - diarization_time_sec: float (processing time for diarization)
        - speaker_segments: list[dict] (raw diarization segments with timestamps)
        - diarization_engine: str (e.g., "pyannote-audio-3.1")
        Example: {
            "num_speakers": 2,
            "diarization_time_sec": 175.5,
            "diarization_engine": "pyannote-audio-3.1",
            "speaker_segments": [
                {"start": 0.0, "end": 5.5, "speaker": "SPEAKER_00"},
                {"start": 6.5, "end": 13.8, "speaker": "SPEAKER_01"}
            ]
        }
        """,
    )

    # Error tracking
    error_message: Mapped[Optional[str]] = mapped_column(
        String(1000),
        nullable=True,
        comment="Error message if status=failed",
    )

    # Timestamps
    started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When ASR processing started",
    )

    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When ASR processing completed",
    )

    # Physician corrections (for learning loop)
    is_corrected: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="True if physician has manually corrected this transcript",
    )

    corrected_text: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Physician-corrected version of the transcript (for ML training)",
    )

    correction_metadata: Mapped[Optional[dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=True,
        comment="""
        Metadata about corrections:
        - Edit distance (Levenshtein)
        - Time spent correcting
        - Sections corrected (timestamps)
        - Correction type (drug names, medical terms, patient names, etc.)
        """,
    )

    corrected_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When physician completed corrections",
    )

    corrected_by: Mapped[Optional[UUID]] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="User ID of physician who corrected the transcript",
    )

    # Quality feedback
    physician_rating: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Physician rating of transcript quality (1-5)",
    )

    physician_feedback: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Free-text feedback from physician about transcript quality",
    )

    # Relationships
    # recording = relationship("Recording", back_populates="transcripts")

    def __repr__(self) -> str:
        """String representation."""
        return f"<Transcript id={self.id} recording={self.recording_id} engine={self.asr_engine} status={self.status.value}>"
