"""Health check service for monitoring system components."""

import asyncio
import logging
import time
from datetime import datetime
from typing import Any

import redis.asyncio as aioredis
from sqlalchemy import text

from app.core.config import settings
from app.core.database import async_session_maker, engine
from app.schemas.health import HealthCheckResponse, HealthStatus, ServiceHealth
from app.services.diarization import get_diarization_service
from app.services.storage import MinIOService
from app.services.transcription import get_whisper_service

logger = logging.getLogger(__name__)


class HealthCheckService:
    """Service for checking health of all system components."""

    async def check_database(self) -> ServiceHealth:
        """
        Check PostgreSQL database health.

        Tests:
        - Connection pool availability
        - Simple query execution
        - Response time

        Returns:
            ServiceHealth with database status
        """
        start_time = time.time()
        try:
            async with async_session_maker() as session:
                # Execute simple query to verify connection
                result = await session.execute(text("SELECT 1"))
                result.scalar()

                # Get pool stats if available
                pool_size = engine.pool.size()  # type: ignore[attr-defined]
                checked_in = engine.pool.checkedin()  # type: ignore[attr-defined]

                response_time_ms = (time.time() - start_time) * 1000

                return ServiceHealth(
                    status=HealthStatus.HEALTHY,
                    response_time_ms=response_time_ms,
                    details={
                        "pool_size": pool_size,
                        "active_connections": pool_size - checked_in,
                        "database": "postgresql",
                    },
                )

        except Exception as e:
            logger.error(f"Database health check failed: {e}", exc_info=True)
            response_time_ms = (time.time() - start_time) * 1000
            return ServiceHealth(
                status=HealthStatus.UNHEALTHY,
                response_time_ms=response_time_ms,
                error=str(e),
            )

    async def check_redis(self) -> ServiceHealth:
        """
        Check Redis health.

        Tests:
        - Connection availability
        - PING command
        - Response time

        Returns:
            ServiceHealth with Redis status
        """
        start_time = time.time()
        try:
            # Create Redis client
            redis_client = aioredis.from_url(
                settings.REDIS_URL, encoding="utf-8", decode_responses=True
            )

            try:
                # Execute PING command
                ping_result = await redis_client.ping()

                response_time_ms = (time.time() - start_time) * 1000

                return ServiceHealth(
                    status=HealthStatus.HEALTHY,
                    response_time_ms=response_time_ms,
                    details={"ping": "PONG" if ping_result else "FAILED"},
                )

            finally:
                await redis_client.close()

        except Exception as e:
            logger.error(f"Redis health check failed: {e}", exc_info=True)
            response_time_ms = (time.time() - start_time) * 1000
            return ServiceHealth(
                status=HealthStatus.UNHEALTHY,
                response_time_ms=response_time_ms,
                error=str(e),
            )

    async def check_minio(self) -> ServiceHealth:
        """
        Check MinIO storage health.

        Tests:
        - Connection availability
        - Bucket access
        - Response time

        Returns:
            ServiceHealth with MinIO status
        """
        start_time = time.time()
        try:
            minio_service = MinIOService()

            # List buckets to verify connection
            buckets = minio_service.client.list_buckets()
            bucket_count = len(buckets) if buckets else 0

            response_time_ms = (time.time() - start_time) * 1000

            return ServiceHealth(
                status=HealthStatus.HEALTHY,
                response_time_ms=response_time_ms,
                details={
                    "buckets": bucket_count,
                    "endpoint": settings.MINIO_ENDPOINT,
                    "ssl": settings.MINIO_USE_SSL,
                },
            )

        except Exception as e:
            logger.error(f"MinIO health check failed: {e}", exc_info=True)
            response_time_ms = (time.time() - start_time) * 1000
            return ServiceHealth(
                status=HealthStatus.UNHEALTHY,
                response_time_ms=response_time_ms,
                error=str(e),
            )

    async def check_whisper(self) -> ServiceHealth:
        """
        Check Whisper ASR model health.

        Tests:
        - Model availability
        - Model metadata access
        - Response time

        Returns:
            ServiceHealth with Whisper status
        """
        start_time = time.time()
        try:
            whisper_service = get_whisper_service()

            # Get model info (this verifies model is loaded)
            model_name = whisper_service.get_model_name()
            model_version = whisper_service.get_model_version()

            response_time_ms = (time.time() - start_time) * 1000

            return ServiceHealth(
                status=HealthStatus.HEALTHY,
                response_time_ms=response_time_ms,
                details={
                    "model": model_name,
                    "version": model_version,
                    "device": settings.WHISPER_DEVICE,
                    "compute_type": settings.WHISPER_COMPUTE_TYPE,
                },
            )

        except Exception as e:
            logger.error(f"Whisper health check failed: {e}", exc_info=True)
            response_time_ms = (time.time() - start_time) * 1000
            return ServiceHealth(
                status=HealthStatus.UNHEALTHY,
                response_time_ms=response_time_ms,
                error=str(e),
            )

    async def check_diarization(self) -> ServiceHealth:
        """
        Check diarization model health.

        Tests:
        - Model availability (if enabled)
        - Model metadata access
        - Response time

        Returns:
            ServiceHealth with diarization status
        """
        start_time = time.time()

        # If diarization is disabled, return healthy but note it's disabled
        if not settings.DIARIZATION_ENABLED:
            return ServiceHealth(
                status=HealthStatus.HEALTHY,
                response_time_ms=0.0,
                details={"enabled": False, "note": "Diarization is disabled"},
            )

        try:
            diarization_service = get_diarization_service()

            # Verify pipeline is loaded
            if diarization_service.pipeline is None:
                raise RuntimeError("Diarization pipeline not loaded")

            response_time_ms = (time.time() - start_time) * 1000

            return ServiceHealth(
                status=HealthStatus.HEALTHY,
                response_time_ms=response_time_ms,
                details={
                    "enabled": True,
                    "model": "pyannote/speaker-diarization-3.1",
                    "device": "cpu",  # pyannote uses CPU by default
                    "num_speakers": settings.DIARIZATION_NUM_SPEAKERS,
                },
            )

        except Exception as e:
            logger.error(f"Diarization health check failed: {e}", exc_info=True)
            response_time_ms = (time.time() - start_time) * 1000
            return ServiceHealth(
                status=HealthStatus.UNHEALTHY,
                response_time_ms=response_time_ms,
                error=str(e),
            )

    async def perform_health_check(self) -> HealthCheckResponse:
        """
        Perform comprehensive health check of all services.

        Runs all health checks in parallel for optimal performance.

        Returns:
            HealthCheckResponse with overall system health
        """
        timestamp = datetime.utcnow()

        # Run all health checks in parallel
        results = await asyncio.gather(
            self.check_database(),
            self.check_redis(),
            self.check_minio(),
            self.check_whisper(),
            self.check_diarization(),
            return_exceptions=True,
        )

        # Map results to service names
        services = {
            "database": results[0]
            if isinstance(results[0], ServiceHealth)
            else ServiceHealth(
                status=HealthStatus.UNHEALTHY, error=str(results[0])
            ),
            "redis": results[1]
            if isinstance(results[1], ServiceHealth)
            else ServiceHealth(
                status=HealthStatus.UNHEALTHY, error=str(results[1])
            ),
            "minio": results[2]
            if isinstance(results[2], ServiceHealth)
            else ServiceHealth(
                status=HealthStatus.UNHEALTHY, error=str(results[2])
            ),
            "whisper": results[3]
            if isinstance(results[3], ServiceHealth)
            else ServiceHealth(
                status=HealthStatus.UNHEALTHY, error=str(results[3])
            ),
            "diarization": results[4]
            if isinstance(results[4], ServiceHealth)
            else ServiceHealth(
                status=HealthStatus.UNHEALTHY, error=str(results[4])
            ),
        }

        # Determine overall status
        overall_status = self._compute_overall_status(services)

        return HealthCheckResponse(
            status=overall_status,
            timestamp=timestamp,
            version=settings.APP_VERSION,
            services=services,
        )

    def _compute_overall_status(
        self, services: dict[str, ServiceHealth]
    ) -> HealthStatus:
        """
        Compute overall system health from individual services.

        Logic:
        - UNHEALTHY: Any critical service (database, Redis, Whisper) is unhealthy
        - DEGRADED: Non-critical service (MinIO, diarization) is unhealthy
        - HEALTHY: All services are healthy

        Args:
            services: Dictionary of service health statuses

        Returns:
            Overall system health status
        """
        # Critical services that must be healthy
        critical_services = ["database", "redis", "whisper"]

        # Check critical services
        for service_name in critical_services:
            if services[service_name].status == HealthStatus.UNHEALTHY:
                return HealthStatus.UNHEALTHY

        # Check non-critical services
        for service_name, service_health in services.items():
            if (
                service_name not in critical_services
                and service_health.status == HealthStatus.UNHEALTHY
            ):
                return HealthStatus.DEGRADED

        return HealthStatus.HEALTHY
