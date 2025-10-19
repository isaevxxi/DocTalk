"""Note models - Clinical notes with immutable version history."""

from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID

from sqlalchemy import DateTime, Enum as SQLEnum
from sqlalchemy import ForeignKey, Integer, Text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class NoteStatus(str, Enum):
    """Status of clinical note."""

    DRAFT = "draft"  # Being edited
    FINAL = "final"  # Finalized/signed
    AMENDED = "amended"  # Amended after finalization
    ARCHIVED = "archived"  # Archived/historical


class Note(BaseModel):
    """
    Clinical Note model (current/head version).

    Represents the current state of a clinical note.
    All edits create new entries in note_versions (WORM).
    """

    __tablename__ = "notes"

    # Encounter reference
    encounter_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("encounters.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Encounter this note belongs to",
    )

    # Content (SOAP format)
    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Clinical note content (SOAP: Subjective/Objective/Assessment/Plan)",
    )

    # Status
    status: Mapped[NoteStatus] = mapped_column(
        SQLEnum(NoteStatus, name="note_status", native_enum=False, create_constraint=True),
        nullable=False,
        default=NoteStatus.DRAFT,
        comment="Current status of note",
    )

    # Versioning
    current_version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        comment="Current version number (increments on each edit)",
    )

    # Finalization
    finalized_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When note was finalized/signed",
    )

    finalized_by: Mapped[Optional[UUID]] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=True,
        comment="User who finalized the note",
    )

    # Amendment tracking
    amendment_reason: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Reason for amendment (required if status=amended)",
    )

    # Relationships
    # encounter = relationship("Encounter", back_populates="notes")
    # versions = relationship("NoteVersion", back_populates="note")

    def __repr__(self) -> str:
        """String representation."""
        return f"<Note id={self.id} encounter={self.encounter_id} v{self.current_version} {self.status.value}>"


class NoteVersion(BaseModel):
    """
    Note Version model - Immutable version history (WORM).

    Every edit creates a new NoteVersion entry.
    WORM enforcement: Trigger blocks UPDATE and DELETE operations.
    Compliance: 323-FZ requires immutable medical record history.
    """

    __tablename__ = "note_versions"

    # Note reference
    note_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("notes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Note this version belongs to",
    )

    # Version metadata
    version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Version number (1, 2, 3...)",
    )

    # Content snapshot
    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Content snapshot for this version",
    )

    status: Mapped[NoteStatus] = mapped_column(
        SQLEnum(NoteStatus, name="note_status", native_enum=False, create_constraint=True),
        nullable=False,
        comment="Status at time of this version",
    )

    # Change metadata
    change_summary: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Summary of changes in this version",
    )

    # WORM enforcement
    # - INSERT allowed (new versions)
    # - UPDATE blocked by trigger
    # - DELETE blocked by trigger
    # See migration for trigger definition

    # Relationships
    # note = relationship("Note", back_populates="versions")

    def __repr__(self) -> str:
        """String representation."""
        return f"<NoteVersion note={self.note_id} v{self.version}>"
