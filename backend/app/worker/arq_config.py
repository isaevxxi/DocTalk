"""ARQ worker configuration for async task processing."""

import logging
from typing import Any

from arq.connections import RedisSettings
from arq.worker import func

from app.core.config import settings

logger = logging.getLogger(__name__)


async def startup(ctx: dict[str, Any]) -> None:
    """
    Worker startup hook.

    Initializes services needed by worker tasks:
    - MinIO client for audio file access
    - Whisper model for transcription
    - Speaker diarization (if enabled)
    - Database connection pool
    """
    from app.core.config import settings
    from app.services.storage import get_minio_service
    from app.services.transcription import get_whisper_service

    ctx["minio"] = get_minio_service()
    ctx["whisper"] = get_whisper_service()

    # Initialize diarization service if enabled
    if settings.DIARIZATION_ENABLED:
        try:
            from app.services.diarization import get_diarization_service

            ctx["diarization"] = get_diarization_service()
            logger.info("Speaker diarization enabled")
        except Exception as e:
            logger.warning(f"Failed to initialize diarization service: {e}")
            logger.info("Continuing without speaker diarization")
            ctx["diarization"] = None
    else:
        ctx["diarization"] = None
        logger.info("Speaker diarization disabled")

    # Ensure MinIO buckets exist
    await ctx["minio"].ensure_buckets_exist()


async def shutdown(ctx: dict[str, Any]) -> None:
    """
    Worker shutdown hook.

    Clean up resources before worker exits.
    """
    # Cleanup can be added here if needed
    pass


# Import task functions
from app.worker.tasks import transcribe_recording  # noqa: E402


# Redis settings (evaluated at module import time, after env vars are loaded)
redis_settings = RedisSettings.from_dsn(settings.ARQ_REDIS_URL)


class WorkerSettings:
    """ARQ worker settings."""

    # Redis connection
    redis_settings = redis_settings

    # Worker configuration
    queue_name = "doktalk-worker"
    max_jobs = 10
    job_timeout = 3600  # 1 hour max per job
    keep_result = 3600  # Keep job results for 1 hour

    # Retry configuration
    max_tries = 3
    retry_jobs = True

    # Lifecycle hooks
    on_startup = startup
    on_shutdown = shutdown

    # Task functions
    functions = [
        func(transcribe_recording, name="transcribe_recording"),
    ]
