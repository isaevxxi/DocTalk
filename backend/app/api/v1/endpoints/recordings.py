"""Recordings API endpoints."""

import io
import uuid
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import select

from app.api.dependencies import User, get_current_active_user
from app.core.config import settings
from app.core.database import get_tenant_db
from app.models.encounter import Encounter
from app.models.recording import Recording, RecordingStatus
from app.models.transcript import Transcript
from app.schemas.recording import (
    RecordingDetailResponse,
    RecordingStatusResponse,
    RecordingUploadResponse,
)
from app.services.storage import MinIOService
from app.worker.arq import enqueue_transcription

router = APIRouter()


# Audio file validation constants
ALLOWED_AUDIO_TYPES = {
    "audio/mpeg",  # MP3
    "audio/mp3",
    "audio/wav",
    "audio/wave",
    "audio/x-wav",
    "audio/m4a",
    "audio/mp4",
    "audio/ogg",
    "audio/webm",
    "audio/flac",
}

MAX_FILE_SIZE = 500 * 1024 * 1024  # 500 MB
MIN_FILE_SIZE = 1024  # 1 KB


@router.post(
    "/encounters/{encounter_id}/recordings",
    response_model=RecordingUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload audio recording",
    description="Upload an audio recording for transcription. File will be validated and queued for processing.",
)
async def upload_recording(
    encounter_id: UUID,
    file: Annotated[UploadFile, File(description="Audio file to transcribe")],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> RecordingUploadResponse:
    """
    Upload audio recording for an encounter.

    Validation:
    - Encounter must exist and belong to user's tenant
    - File type must be valid audio format
    - File size must be between 1KB and 500MB
    - Storage upload must succeed

    Returns:
        RecordingUploadResponse with recording ID, status, and job ID
    """
    # Validate content type
    if file.content_type not in ALLOWED_AUDIO_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported audio format: {file.content_type}. "
            f"Allowed formats: {', '.join(ALLOWED_AUDIO_TYPES)}",
        )

    # Read file content
    audio_data = await file.read()
    file_size = len(audio_data)

    # Validate file size
    if file_size < MIN_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File too small. Minimum size is {MIN_FILE_SIZE} bytes",
        )

    if file_size > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File too large. Maximum size is {MAX_FILE_SIZE / 1024 / 1024:.0f} MB",
        )

    # Get tenant-scoped database session
    async for db in get_tenant_db(current_user.tenant_id):
        # Verify encounter exists and belongs to tenant
        encounter_result = await db.execute(
            select(Encounter).where(Encounter.id == encounter_id)
        )
        encounter = encounter_result.scalar_one_or_none()

        if not encounter:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Encounter {encounter_id} not found",
            )

        # Create recording record
        recording_id = uuid.uuid4()

        # Determine file format from content type
        file_format = file.content_type.split("/")[-1]

        # Generate storage key (must match MinIOService.upload_recording format)
        # Format: tenant_id/encounter_id/recording_id.ext
        storage_key = f"{current_user.tenant_id}/{encounter_id}/{recording_id}.{file_format}"

        # Create recording in database
        recording = Recording(
            id=recording_id,
            tenant_id=current_user.tenant_id,
            encounter_id=encounter_id,
            storage_key=storage_key,
            storage_bucket=settings.MINIO_BUCKET_RECORDINGS,
            file_format=file_format,
            file_size_bytes=file_size,
            status=RecordingStatus.UPLOADING,
            original_filename=file.filename,
            content_type=file.content_type,
        )

        db.add(recording)
        await db.commit()
        await db.refresh(recording)

        # Upload to MinIO
        try:
            minio_service = MinIOService()
            file_stream = io.BytesIO(audio_data)
            await minio_service.upload_recording(
                tenant_id=current_user.tenant_id,
                encounter_id=encounter_id,
                recording_id=recording_id,
                file_data=file_stream,
                file_size=file_size,
                content_type=file.content_type,
                file_extension=file_format,
            )

            # Update status to pending transcription
            recording.status = RecordingStatus.PENDING_TRANSCRIPTION
            await db.commit()

        except Exception as e:
            # Update recording status to failed
            recording.status = RecordingStatus.FAILED
            recording.error_message = f"Storage upload failed: {str(e)}"
            await db.commit()

            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to upload recording: {str(e)}",
            )

        # Enqueue transcription job
        try:
            job_id = await enqueue_transcription(str(recording_id))
        except Exception as e:
            # Update recording status to failed
            recording.status = RecordingStatus.FAILED
            recording.error_message = f"Failed to enqueue transcription: {str(e)}"
            await db.commit()

            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to enqueue transcription: {str(e)}",
            )

        # Return response
        return RecordingUploadResponse(
            recording_id=recording.id,
            encounter_id=recording.encounter_id,
            status=recording.status,
            storage_key=recording.storage_key,
            job_id=job_id,
            created_at=recording.created_at,
        )


@router.get(
    "/recordings/{recording_id}",
    response_model=RecordingDetailResponse,
    summary="Get recording details",
    description="Retrieve recording status and optionally transcript if available",
)
async def get_recording(
    recording_id: UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> RecordingDetailResponse:
    """
    Get recording details with optional transcript information.

    Returns:
        RecordingDetailResponse with recording status and transcript availability
    """
    async for db in get_tenant_db(current_user.tenant_id):
        # Get recording
        recording_result = await db.execute(
            select(Recording).where(Recording.id == recording_id)
        )
        recording = recording_result.scalar_one_or_none()

        if not recording:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Recording {recording_id} not found",
            )

        # Check if transcript exists
        transcript_result = await db.execute(
            select(Transcript).where(Transcript.recording_id == recording_id)
        )
        transcript = transcript_result.scalar_one_or_none()

        # Build response
        recording_status = RecordingStatusResponse(
            id=recording.id,
            encounter_id=recording.encounter_id,
            status=recording.status,
            storage_key=recording.storage_key,
            file_format=recording.file_format,
            file_size_bytes=recording.file_size_bytes,
            duration_sec=recording.duration_sec,
            created_at=recording.created_at,
            transcription_started_at=recording.transcription_started_at,
            transcription_completed_at=recording.transcription_completed_at,
            error_message=recording.error_message,
            retry_count=recording.retry_count,
        )

        return RecordingDetailResponse(
            recording=recording_status,
            has_transcript=transcript is not None,
            transcript_id=transcript.id if transcript else None,
        )
