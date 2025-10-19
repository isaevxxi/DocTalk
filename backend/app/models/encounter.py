"""Encounter model - Clinical encounters/visits."""

from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID

from sqlalchemy import DateTime, Enum as SQLEnum
from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class EncounterType(str, Enum):
    """Type of clinical encounter."""

    IN_PERSON = "in_person"  # Physical visit to clinic
    TELEMED = "telemed"  # Video/phone telemedicine (965n)
    PHONE = "phone"  # Phone-only consultation


class EncounterStatus(str, Enum):
    """Encounter workflow status."""

    SCHEDULED = "scheduled"  # Future appointment
    IN_PROGRESS = "in_progress"  # Currently ongoing
    COMPLETED = "completed"  # Finished, notes finalized
    CANCELLED = "cancelled"  # Cancelled appointment
    NO_SHOW = "no_show"  # Patient didn't attend


class Encounter(BaseModel):
    """
    Encounter (Clinical Visit) model.

    Represents a patient-physician interaction.
    Audio recordings and notes are linked to encounters.
    """

    __tablename__ = "encounters"

    # Patient reference
    patient_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("patients.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Patient this encounter is for",
    )

    # Physician reference
    physician_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
        comment="Physician conducting the encounter",
    )

    # Encounter metadata
    encounter_type: Mapped[EncounterType] = mapped_column(
        SQLEnum(EncounterType, name="encounter_type", native_enum=False, create_constraint=True, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=EncounterType.IN_PERSON,
        comment="Type of encounter (in-person/telemed/phone)",
    )

    status: Mapped[EncounterStatus] = mapped_column(
        SQLEnum(EncounterStatus, name="encounter_status", native_enum=False, create_constraint=True, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=EncounterStatus.SCHEDULED,
        comment="Current status of encounter",
    )

    # Scheduling
    scheduled_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Scheduled appointment time",
    )

    started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Actual start time",
    )

    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Actual completion time",
    )

    # Clinical context
    chief_complaint: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
        comment="Patient's primary complaint/reason for visit",
    )

    diagnosis: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Working diagnosis (free text, v1)",
    )

    # Telemedicine compliance (965n)
    consent_recorded: Mapped[bool] = mapped_column(
        default=False,
        nullable=False,
        comment="Whether patient consent was recorded (965n requirement)",
    )

    recording_path: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
        comment="Path to audio/video recording in MinIO",
    )

    # Relationships
    # patient = relationship("Patient", back_populates="encounters")
    # physician = relationship("User")
    # notes = relationship("Note", back_populates="encounter")

    def __repr__(self) -> str:
        """String representation."""
        return f"<Encounter id={self.id} patient={self.patient_id} status={self.status.value}>"
