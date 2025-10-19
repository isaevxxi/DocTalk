"""Authentication dependencies for API endpoints."""

from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer
from pydantic import BaseModel

# Mock user model for Phase 1
class User(BaseModel):
    """User model for authentication."""

    id: UUID
    tenant_id: UUID
    email: str
    full_name: str
    is_active: bool = True


# Security scheme
security = HTTPBearer()


async def get_current_user(
    token: Annotated[str, Depends(security)]
) -> User:
    """
    Mock authentication - returns a test user.

    TODO: Replace with real JWT validation in production.
    This is a temporary implementation for Phase 1 testing.

    Args:
        token: Bearer token from Authorization header

    Returns:
        User: Mock user with test tenant_id

    Raises:
        HTTPException: If authentication fails (not implemented in mock)
    """
    # For Phase 1, return a mock user with consistent tenant_id
    # This allows testing the full pipeline without auth infrastructure
    return User(
        id=UUID("10000000-0000-0000-0000-000000000001"),
        tenant_id=UUID("00000000-0000-0000-0000-000000000001"),
        email="test@doctalk.ru",
        full_name="Test Physician",
    )


async def get_current_active_user(
    current_user: Annotated[User, Depends(get_current_user)]
) -> User:
    """
    Verify user is active.

    Args:
        current_user: User from get_current_user dependency

    Returns:
        User: Active user

    Raises:
        HTTPException: If user is inactive
    """
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user",
        )
    return current_user
