"""Health check API endpoints."""

from fastapi import APIRouter, status

from app.schemas.health import HealthCheckResponse, HealthStatus
from app.services.health import HealthCheckService

router = APIRouter()


@router.get(
    "/health",
    response_model=HealthCheckResponse,
    status_code=status.HTTP_200_OK,
    summary="System health check",
    description="Check health of all system components (database, Redis, MinIO, ML models)",
    tags=["Health"],
)
async def health_check() -> HealthCheckResponse:
    """
    Perform comprehensive health check of all services.

    This endpoint checks:
    - **Database**: PostgreSQL connection and query execution
    - **Redis**: Cache connectivity and PING response
    - **MinIO**: Object storage connectivity and bucket access
    - **Whisper**: ASR model availability and metadata
    - **Diarization**: Speaker diarization model availability (if enabled)

    Response status codes:
    - 200: System is healthy or degraded (check `status` field)
    - 503: System is unhealthy (returned via response_class override)

    Response statuses:
    - `healthy`: All services operational
    - `degraded`: Non-critical services down (MinIO, diarization)
    - `unhealthy`: Critical services down (database, Redis, Whisper)

    Returns:
        HealthCheckResponse with detailed service statuses and response times
    """
    health_service = HealthCheckService()
    health_response = await health_service.perform_health_check()

    # Note: We return 200 even if unhealthy, allowing clients to parse
    # the detailed response. For strict health checks (like k8s liveness),
    # clients should check the `status` field.

    return health_response


@router.get(
    "/health/live",
    status_code=status.HTTP_200_OK,
    summary="Liveness probe",
    description="Simple liveness check for Kubernetes/container orchestration",
    tags=["Health"],
)
async def liveness_probe() -> dict[str, str]:
    """
    Kubernetes liveness probe endpoint.

    This endpoint always returns 200 OK if the application is running.
    Use this for liveness probes to detect if the container needs to be restarted.

    Returns:
        Simple status message
    """
    return {"status": "alive"}


@router.get(
    "/health/ready",
    status_code=status.HTTP_200_OK,
    summary="Readiness probe",
    description="Readiness check for Kubernetes/container orchestration (checks critical services)",
    tags=["Health"],
    responses={
        200: {"description": "Service is ready to accept traffic"},
        503: {"description": "Service is not ready (critical services down)"},
    },
)
async def readiness_probe() -> dict[str, str]:
    """
    Kubernetes readiness probe endpoint.

    Checks critical services (database, Redis, Whisper) and returns:
    - 200 OK: All critical services are healthy
    - 503 Service Unavailable: At least one critical service is down

    Use this for readiness probes to detect if the container should receive traffic.

    Returns:
        Status message and HTTP status code

    Raises:
        HTTPException: 503 if any critical service is unhealthy
    """
    from fastapi import HTTPException

    health_service = HealthCheckService()
    health_response = await health_service.perform_health_check()

    # Return 503 if system is unhealthy (critical services down)
    if health_response.status == HealthStatus.UNHEALTHY:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "status": "not_ready",
                "reason": "Critical services are unhealthy",
                "services": {
                    name: {
                        "status": service.status.value,
                        "error": service.error,
                    }
                    for name, service in health_response.services.items()
                    if service.status == HealthStatus.UNHEALTHY
                },
            },
        )

    # Return 200 for healthy or degraded (non-critical services down)
    return {"status": "ready"}
