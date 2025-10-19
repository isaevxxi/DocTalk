"""Patient model - Patient demographics and MRN."""

from datetime import date
from enum import Enum
from typing import Optional

from sqlalchemy import Date, Enum as SQLEnum
from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class PatientSex(str, Enum):
    """Patient biological sex."""

    MALE = "male"
    FEMALE = "female"
    OTHER = "other"
    UNKNOWN = "unknown"


class Patient(BaseModel):
    """
    Patient model.

    Stores patient demographics with PII.
    Access controlled via RLS (tenant_id).
    """

    __tablename__ = "patients"

    # Identity
    full_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Patient full name (PII)",
    )

    date_of_birth: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        comment="Patient date of birth (PII)",
    )

    sex: Mapped[PatientSex] = mapped_column(
        SQLEnum(PatientSex, name="patient_sex", native_enum=False, create_constraint=True),
        nullable=False,
        default=PatientSex.UNKNOWN,
        comment="Patient biological sex",
    )

    # Medical Record Number (external ID for EHR integration)
    mrn: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        index=True,
        comment="Medical Record Number (external system ID)",
    )

    # Contact information (PII)
    phone: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="Primary contact phone (PII)",
    )

    email: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="Contact email (PII)",
    )

    # Address (simplified for v1)
    address: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Full address (PII) - will be structured in v2",
    )

    # Clinical metadata
    is_active: Mapped[bool] = mapped_column(
        default=True,
        nullable=False,
        comment="Whether patient record is active",
    )

    notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Administrative notes (allergies, special needs, etc.)",
    )

    # Relationships
    # encounters = relationship("Encounter", back_populates="patient")

    def __repr__(self) -> str:
        """String representation (avoid PII in logs)."""
        return f"<Patient id={self.id} mrn={self.mrn}>"

    @property
    def age(self) -> int:
        """Calculate current age."""
        from datetime import datetime

        today = datetime.now().date()
        return (
            today.year
            - self.date_of_birth.year
            - ((today.month, today.day) < (self.date_of_birth.month, self.date_of_birth.day))
        )
