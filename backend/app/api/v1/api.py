"""API v1 router configuration."""

from fastapi import APIRouter

# Import endpoint routers
from app.api.v1.endpoints import recordings, transcripts

# Create API v1 router
api_router = APIRouter()

# Include endpoint routers
api_router.include_router(
    recordings.router,
    tags=["Recordings"],
)
api_router.include_router(
    transcripts.router,
    tags=["Transcripts"],
)


# Health check for API v1
@api_router.get("/health", tags=["Health"])
async def api_health() -> dict[str, str]:
    """API v1 health check."""
    return {
        "status": "healthy",
        "api_version": "v1",
    }
