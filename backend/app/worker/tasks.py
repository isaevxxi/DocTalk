"""ARQ async task definitions for background processing."""

import asyncio
import logging
import time
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import async_session_maker, set_tenant_context
from app.models.recording import Recording, RecordingStatus
from app.models.transcript import Transcript, TranscriptStatus
from app.utils.diarization import create_diarization_summary

logger = logging.getLogger(__name__)


async def transcribe_recording(
    ctx: dict[str, Any],
    recording_id: str,
) -> dict[str, Any]:
    """
    Transcribe audio recording using Whisper ASR with speaker diarization.

    This is the main background task for the audio pipeline.
    Workflow:
    1. Fetch recording from database
    2. Download audio file from MinIO
    3. Run speaker diarization (if enabled)
    4. Run Whisper transcription
    5. Map speakers to transcription segments
    6. Save transcript to database
    7. Update recording status

    Args:
        ctx: ARQ context with minio, whisper, diarization services
        recording_id: UUID of recording to transcribe

    Returns:
        Dict with transcription results and metadata

    Raises:
        RuntimeError: If transcription fails
    """
    logger.info(f"Starting transcription task for recording {recording_id}")
    task_start_time = time.time()

    recording_uuid = UUID(recording_id)
    minio_service = ctx["minio"]
    whisper_service = ctx["whisper"]
    diarization_service = ctx.get("diarization")

    async with async_session_maker() as session:
        # 1. Fetch recording
        recording = await _get_recording(session, recording_uuid)
        if not recording:
            logger.error(f"Recording {recording_id} not found")
            raise RuntimeError(f"Recording {recording_id} not found")

        # Set RLS context for tenant isolation
        await set_tenant_context(session, recording.tenant_id)

        logger.info(
            f"Processing recording: {recording_id} (tenant={recording.tenant_id}, "
            f"storage_key={recording.storage_key})"
        )

        try:
            # Update status to processing
            recording.status = RecordingStatus.PROCESSING
            recording.transcription_started_at = datetime.utcnow()
            await session.flush()

            # 2. Download audio file
            logger.debug(f"Downloading audio from storage: {recording.storage_key}")
            download_start = time.time()
            audio_data = await minio_service.download_recording(recording.storage_key)
            download_time = time.time() - download_start
            logger.info(f"Download complete: {len(audio_data)} bytes in {download_time:.2f}s")

            # 3 & 4. Run diarization and transcription IN PARALLEL (optimization)
            # Instead of sequential execution (diarization → transcription),
            # run both simultaneously to save time (~10% faster)
            logger.info("Starting parallel diarization and transcription")
            parallel_start = time.time()

            diarization_result = None
            diarization_time_sec = 0.0
            result = None

            # Create tasks for parallel execution
            tasks: list[Any] = []

            # Task 1: Transcription (always runs)
            async def run_transcription() -> tuple[dict[str, Any], float]:
                """Run Whisper transcription."""
                trans_start = time.time()
                try:
                    logger.info("Starting Whisper transcription")
                    trans_result = await whisper_service.transcribe(
                        audio_data=audio_data,
                        language="ru",  # Russian by default
                    )
                    trans_time = time.time() - trans_start
                    logger.info(f"Transcription complete in {trans_time:.2f}s")
                    return trans_result, trans_time
                except Exception as e:
                    logger.error(f"Transcription failed: {e}", exc_info=True)
                    raise

            tasks.append(run_transcription())

            # Task 2: Diarization (only if enabled)
            if settings.DIARIZATION_ENABLED and diarization_service:
                async def run_diarization() -> tuple[dict[str, Any] | None, float]:
                    """Run speaker diarization."""
                    diar_start = time.time()
                    try:
                        logger.info("Starting speaker diarization")
                        diar_result = await diarization_service.diarize(
                            audio_data=audio_data,
                            num_speakers=settings.DIARIZATION_NUM_SPEAKERS,
                        )
                        diar_time = time.time() - diar_start
                        logger.info(f"Diarization complete in {diar_time:.2f}s")
                        return diar_result, diar_time
                    except Exception as diar_error:
                        # Log diarization error but don't fail the entire task
                        logger.warning(
                            f"Diarization failed for {recording_id}, continuing without speaker labels: {diar_error}",
                            exc_info=True,
                        )
                        return None, 0.0

                tasks.append(run_diarization())

            # Wait for all tasks to complete
            results = await asyncio.gather(*tasks)

            # Extract results
            result, transcription_time = results[0]

            if len(results) > 1:
                # Diarization was enabled
                diarization_result, diarization_time_sec = results[1]

            parallel_time = time.time() - parallel_start
            logger.info(
                f"Parallel processing complete in {parallel_time:.2f}s "
                f"(transcription: {transcription_time:.2f}s, diarization: {diarization_time_sec:.2f}s)"
            )

            # 5. Map speakers to transcription segments (if diarization succeeded)
            segments = result["segments"]
            if diarization_result and diarization_service:
                logger.debug("Mapping speakers to transcription segments")
                segments = diarization_service.map_transcription_to_speakers(
                    transcription_segments=segments,
                    diarization_segments=diarization_result["segments"],
                    speaker_mapping=diarization_result["speaker_mapping"],
                )

            # 6. Create transcript record with optimized diarization storage
            raw_output = {
                "segments": segments,
                "duration": result.get("duration"),
            }

            # Store COMPRESSED diarization metadata (70-88% space savings)
            speaker_mapping = None
            diarization_metadata = None

            if diarization_result:
                speaker_mapping = diarization_result["speaker_mapping"]
                diarization_metadata = create_diarization_summary(
                    diarization_result,
                    diarization_time_sec=diarization_time_sec,
                )
                logger.debug(
                    f"Diarization metadata compressed: {len(diarization_result['segments'])} segments "
                    f"-> {len(diarization_metadata.get('speaker_timeline', ''))} chars"
                )

            transcript = Transcript(
                tenant_id=recording.tenant_id,
                recording_id=recording_uuid,
                asr_engine=whisper_service.get_model_name(),
                asr_model_version=whisper_service.get_model_version(),
                status=TranscriptStatus.COMPLETED,
                plain_text=result["text"],
                raw_output=raw_output,
                processing_time_sec=result["processing_time"],
                average_confidence=result.get("average_confidence"),
                language_detected=result.get("language"),
                # Optimized diarization storage
                speaker_mapping=speaker_mapping,
                diarization_metadata=diarization_metadata,
                # Timestamps
                started_at=recording.transcription_started_at,
                completed_at=datetime.utcnow(),
            )
            session.add(transcript)

            # 7. Update recording status
            recording.status = RecordingStatus.COMPLETED
            recording.transcription_completed_at = datetime.utcnow()
            recording.duration_sec = result.get("duration")

            await session.commit()

            task_total_time = time.time() - task_start_time

            logger.info(
                f"Transcription task complete for {recording_id}: "
                f"transcript_id={transcript.id}, text_length={len(result['text'])}, "
                f"total_time={task_total_time:.2f}s"
            )

            return {
                "success": True,
                "recording_id": recording_id,
                "transcript_id": str(transcript.id),
                "text_length": len(result["text"]),
                "processing_time": result["processing_time"],
                "diarization_time": diarization_time_sec,
                "total_task_time": task_total_time,
            }

        except Exception as e:
            # Handle transcription failure
            logger.error(
                f"Transcription task failed for {recording_id}: {e}",
                exc_info=True,
            )

            recording.status = RecordingStatus.FAILED
            recording.error_message = str(e)[:1000]
            recording.retry_count += 1
            recording.transcription_completed_at = datetime.utcnow()

            # Create failed transcript record
            transcript = Transcript(
                tenant_id=recording.tenant_id,
                recording_id=recording_uuid,
                asr_engine=whisper_service.get_model_name(),
                status=TranscriptStatus.FAILED,
                error_message=str(e)[:1000],
                started_at=recording.transcription_started_at,
                completed_at=datetime.utcnow(),
            )
            session.add(transcript)

            await session.commit()

            raise RuntimeError(f"Transcription failed for {recording_id}: {e}") from e


async def _get_recording(session: AsyncSession, recording_id: UUID) -> Recording | None:
    """Fetch recording by ID."""
    result = await session.execute(select(Recording).where(Recording.id == recording_id))
    return result.scalar_one_or_none()
