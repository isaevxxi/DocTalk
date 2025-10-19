"""Pydantic schemas for Recording API."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.recording import RecordingStatus


class RecordingCreate(BaseModel):
    """Schema for creating a new recording."""

    encounter_id: UUID = Field(..., description="Encounter this recording belongs to")
    original_filename: str = Field(..., description="Original filename from upload")
    content_type: str = Field(..., description="MIME type (audio/mpeg, audio/wav, etc.)")
    file_size_bytes: int = Field(..., gt=0, description="File size in bytes")


class RecordingUploadResponse(BaseModel):
    """Response after successful upload."""

    recording_id: UUID = Field(..., description="Unique recording ID")
    encounter_id: UUID = Field(..., description="Associated encounter ID")
    status: RecordingStatus = Field(..., description="Current processing status")
    storage_key: str = Field(..., description="Storage path in MinIO")
    job_id: str = Field(..., description="ARQ background job ID")
    created_at: datetime = Field(..., description="Creation timestamp")

    class Config:
        """Pydantic config."""

        from_attributes = True


class RecordingStatusResponse(BaseModel):
    """Response for recording status check."""

    id: UUID = Field(..., description="Recording ID")
    encounter_id: UUID = Field(..., description="Associated encounter ID")
    status: RecordingStatus = Field(..., description="Current status")
    storage_key: str = Field(..., description="Storage path")
    file_format: str = Field(..., description="Audio format")
    file_size_bytes: int = Field(..., description="File size")
    duration_sec: Optional[float] = Field(None, description="Duration in seconds")
    created_at: datetime = Field(..., description="Upload time")
    transcription_started_at: Optional[datetime] = Field(None, description="When transcription started")
    transcription_completed_at: Optional[datetime] = Field(None, description="When transcription completed")
    error_message: Optional[str] = Field(None, description="Error if failed")
    retry_count: int = Field(..., description="Number of retry attempts")

    class Config:
        """Pydantic config."""

        from_attributes = True


class RecordingDetailResponse(BaseModel):
    """Detailed recording response with optional transcript."""

    recording: RecordingStatusResponse
    has_transcript: bool = Field(..., description="Whether transcript is available")
    transcript_id: Optional[UUID] = Field(None, description="Transcript ID if available")

    class Config:
        """Pydantic config."""

        from_attributes = True
