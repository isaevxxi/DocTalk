"""ARQ client for enqueueing tasks."""

from arq import create_pool
from arq.connections import ArqRedis, RedisSettings

from app.core.config import settings


async def enqueue_transcription(recording_id: str) -> str:
    """
    Enqueue transcription task for a recording.

    Args:
        recording_id: UUID of the recording to transcribe

    Returns:
        str: Job ID from ARQ

    Raises:
        Exception: If enqueueing fails
    """
    # Parse Redis URL to extract host, port, database
    # Format: redis://host:port/database or redis://host:port
    redis_url = str(settings.ARQ_REDIS_URL)
    parts = redis_url.replace("redis://", "").split("/")
    host_port = parts[0].split(":")
    host = host_port[0]
    port = int(host_port[1]) if len(host_port) > 1 else 6379
    database = int(parts[1]) if len(parts) > 1 else 0

    redis_settings = RedisSettings(
        host=host,
        port=port,
        database=database,
    )

    redis: ArqRedis = await create_pool(redis_settings)

    try:
        job = await redis.enqueue_job(
            "transcribe_recording",
            recording_id,
            _queue_name="doktalk-worker",
        )
        return job.job_id
    finally:
        await redis.close()
