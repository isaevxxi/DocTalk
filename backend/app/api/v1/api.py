"""API v1 router configuration."""

from fastapi import APIRouter

# Import endpoint routers
from app.api.v1.endpoints import health, recordings, transcripts

# Create API v1 router
api_router = APIRouter()

# Include endpoint routers
api_router.include_router(
    health.router,
    tags=["Health"],
)
api_router.include_router(
    recordings.router,
    tags=["Recordings"],
)
api_router.include_router(
    transcripts.router,
    tags=["Transcripts"],
)
