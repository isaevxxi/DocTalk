"""User model - System users with authentication."""

from enum import Enum
from typing import Optional

from sqlalchemy import Enum as SQLEnum
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class UserRole(str, Enum):
    """User roles for RBAC."""

    PHYSICIAN = "physician"  # Can create/edit clinical notes
    ADMIN = "admin"  # Full tenant admin rights
    STAFF = "staff"  # Limited access (scheduling, etc.)


class User(BaseModel):
    """
    User model.

    Users belong to a tenant and have roles for RBAC.
    Authentication via email/password (hashed with bcrypt).
    """

    __tablename__ = "users"

    # Authentication
    email: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
        comment="Email address (used for login)",
    )

    password_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Bcrypt password hash",
    )

    is_active: Mapped[bool] = mapped_column(
        default=True,
        nullable=False,
        comment="Whether user account is active",
    )

    # Profile
    full_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Full name of user",
    )

    role: Mapped[UserRole] = mapped_column(
        SQLEnum(UserRole, name="user_role", native_enum=False, create_constraint=True),
        nullable=False,
        default=UserRole.PHYSICIAN,
        comment="User role for RBAC",
    )

    # Optional profile fields
    phone: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="Contact phone number",
    )

    # License/credential info (for physicians)
    medical_license_number: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="Medical license number (323-FZ requirement)",
    )

    specialty: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="Medical specialty",
    )

    # Relationships
    # tenant = relationship("Tenant", back_populates="users")

    def __repr__(self) -> str:
        """String representation."""
        return f"<User {self.email} ({self.role.value})>"
