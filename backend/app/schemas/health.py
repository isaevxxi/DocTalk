"""Health check response schemas."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class HealthStatus(str, Enum):
    """Health check status values."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


class ServiceHealth(BaseModel):
    """Health status for individual service."""

    status: HealthStatus = Field(description="Service health status")
    response_time_ms: float | None = Field(
        default=None, description="Response time in milliseconds"
    )
    details: dict[str, str | int | float | bool] | None = Field(
        default=None, description="Additional service details"
    )
    error: str | None = Field(default=None, description="Error message if unhealthy")


class HealthCheckResponse(BaseModel):
    """Complete health check response."""

    status: HealthStatus = Field(description="Overall system health status")
    timestamp: datetime = Field(description="Health check timestamp")
    version: str = Field(description="Application version")
    services: dict[str, ServiceHealth] = Field(
        description="Health status of individual services"
    )

    class Config:
        """Pydantic config."""

        json_schema_extra = {
            "example": {
                "status": "healthy",
                "timestamp": "2025-10-20T12:00:00Z",
                "version": "1.0.0",
                "services": {
                    "database": {
                        "status": "healthy",
                        "response_time_ms": 5.2,
                        "details": {"pool_size": 20, "active_connections": 3},
                    },
                    "redis": {
                        "status": "healthy",
                        "response_time_ms": 2.1,
                        "details": {"ping": "PONG"},
                    },
                    "minio": {
                        "status": "healthy",
                        "response_time_ms": 8.3,
                        "details": {"buckets": 4},
                    },
                    "whisper": {
                        "status": "healthy",
                        "response_time_ms": 15.7,
                        "details": {"model": "base", "device": "cpu"},
                    },
                    "diarization": {
                        "status": "healthy",
                        "response_time_ms": 42.1,
                        "details": {
                            "model": "pyannote/speaker-diarization-3.1",
                            "device": "cpu",
                        },
                    },
                },
            }
        }
