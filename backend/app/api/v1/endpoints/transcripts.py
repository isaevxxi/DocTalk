"""Transcripts API endpoints."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import User, get_current_active_user
from app.core.database import get_db_session_for_tenant
from app.models.transcript import Transcript
from app.schemas.transcript import DiarizationSummary, TranscriptResponse
from app.utils.diarization import expand_diarization_summary

router = APIRouter()


@router.get(
    "/recordings/{recording_id}/transcript",
    response_model=TranscriptResponse,
    summary="Get transcript for recording",
    description="Retrieve the completed transcript for a recording. Use include_diarization=true to load speaker data.",
)
async def get_transcript(
    recording_id: UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    include_diarization: bool = Query(
        False,
        description="Include speaker diarization data (adds ~1 KB to response)",
    ),
) -> TranscriptResponse:
    """
    Get transcript for a recording.

    Optimization: Diarization data is lazy-loaded via include_diarization parameter.
    This reduces default response size by ~1-5 KB.

    Args:
        recording_id: UUID of the recording
        current_user: Authenticated user
        include_diarization: Whether to include speaker diarization data

    Returns:
        TranscriptResponse with transcript data (+ optional diarization)

    Raises:
        404: Recording not found or transcript not available
    """
    async with get_db_session_for_tenant(current_user.tenant_id) as db:
        # Get transcript for recording
        transcript_result = await db.execute(
            select(Transcript).where(Transcript.recording_id == recording_id)
        )
        transcript = transcript_result.scalar_one_or_none()

        if not transcript:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Transcript not found for recording {recording_id}",
            )

        # Parse segments from raw_output if available
        segments = None
        duration = None

        if transcript.raw_output:
            segments = transcript.raw_output.get("segments")
            duration = transcript.raw_output.get("duration")

        # Lazy-load diarization data (only if requested)
        speaker_mapping = None
        diarization_summary = None

        if include_diarization:
            speaker_mapping = transcript.speaker_mapping

            # Build diarization summary from metadata
            if transcript.diarization_metadata:
                diarization_summary = DiarizationSummary(
                    num_speakers=transcript.diarization_metadata.get("num_speakers", 0),
                    diarization_time_sec=transcript.diarization_metadata.get(
                        "diarization_time_sec", 0.0
                    ),
                    diarization_engine=transcript.diarization_metadata.get(
                        "diarization_engine", "unknown"
                    ),
                    total_segments=transcript.diarization_metadata.get("total_segments", 0),
                    speaker_timeline=transcript.diarization_metadata.get("speaker_timeline"),
                )

        # Build response
        return TranscriptResponse(
            id=transcript.id,
            recording_id=transcript.recording_id,
            asr_engine=transcript.asr_engine,
            asr_model_version=transcript.asr_model_version,
            status=transcript.status,
            plain_text=transcript.plain_text,
            segments=segments,
            language_detected=transcript.language_detected,
            duration=duration,
            processing_time_sec=transcript.processing_time_sec,
            average_confidence=transcript.average_confidence,
            created_at=transcript.created_at,
            completed_at=transcript.completed_at,
            error_message=transcript.error_message,
            # Diarization data (lazy-loaded)
            speaker_mapping=speaker_mapping,
            diarization_summary=diarization_summary,
            # Physician corrections
            is_corrected=transcript.is_corrected,
            corrected_text=transcript.corrected_text,
            corrected_at=transcript.corrected_at,
            physician_rating=transcript.physician_rating,
            physician_feedback=transcript.physician_feedback,
        )
