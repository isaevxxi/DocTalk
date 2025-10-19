"""Task queue service for enqueueing background jobs."""

from functools import lru_cache
from typing import Any
from uuid import UUID

from arq import create_pool
from arq.connections import ArqRedis

from app.core.config import settings


class TaskQueueService:
    """
    Service for enqueueing background tasks to ARQ.

    Provides high-level methods for common task operations.
    """

    def __init__(self) -> None:
        """Initialize task queue service."""
        self._pool: ArqRedis | None = None

    async def get_pool(self) -> ArqRedis:
        """Get or create ARQ Redis pool."""
        if self._pool is None:
            # ARQ type stubs are incomplete - create_pool accepts both str and RedisSettings
            # as well as max_connections kwarg at runtime
            self._pool = await create_pool(
                settings.ARQ_REDIS_URL,  # type: ignore[arg-type]
                max_connections=10,  # type: ignore[call-arg]
            )
        return self._pool

    async def close(self) -> None:
        """Close Redis pool."""
        if self._pool is not None:
            await self._pool.close()
            self._pool = None

    async def enqueue_transcription(
        self,
        recording_id: UUID,
        queue_name: str = "transcribe_recording",
    ) -> dict[str, Any]:
        """
        Enqueue audio transcription task.

        Args:
            recording_id: UUID of recording to transcribe
            queue_name: Task queue name (default: 'transcribe_recording')

        Returns:
            Dict with job info (job_id, enqueue_time)
        """
        pool = await self.get_pool()
        job = await pool.enqueue_job(
            queue_name,
            str(recording_id),  # Convert UUID to string for serialization
        )

        # ARQ type stubs are incomplete - Job has these attributes at runtime
        return {
            "job_id": job.job_id,  # type: ignore[union-attr]
            "enqueue_time": job.enqueue_time,  # type: ignore[union-attr]
            "recording_id": str(recording_id),
        }

    async def get_job_status(self, job_id: str) -> dict[str, Any] | None:
        """
        Get status of a background job.

        Args:
            job_id: Job ID returned from enqueue

        Returns:
            Dict with job status or None if not found
        """
        pool = await self.get_pool()
        job = await pool.get_job(job_id)  # type: ignore[attr-defined]

        if job is None:
            return None

        # ARQ type stubs are incomplete - Job has these attributes at runtime
        return {
            "job_id": job.job_id,
            "function": job.function,
            "enqueue_time": job.enqueue_time,
            "score": job.score,
        }


@lru_cache
def get_task_queue_service() -> TaskQueueService:
    """Get cached task queue service instance."""
    return TaskQueueService()
