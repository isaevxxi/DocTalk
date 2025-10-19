"""Pydantic schemas for Transcript API."""

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.transcript import TranscriptStatus


class TranscriptSegment(BaseModel):
    """Schema for a single transcript segment with timestamps."""

    start: float = Field(..., description="Start time in seconds")
    end: float = Field(..., description="End time in seconds")
    text: str = Field(..., description="Transcribed text for this segment")
    confidence: float = Field(..., description="Confidence score")
    no_speech_prob: float = Field(..., description="Probability of no speech")
    words: Optional[list[dict[str, Any]]] = Field(None, description="Word-level timestamps")


class DiarizationSummary(BaseModel):
    """Summary of speaker diarization results (compact)."""

    num_speakers: int = Field(..., description="Number of speakers detected")
    diarization_time_sec: float = Field(..., description="Processing time")
    diarization_engine: str = Field(..., description="Engine used (e.g., 'pyannote-audio-3.1')")
    total_segments: int = Field(..., description="Number of speaker segments")
    speaker_timeline: Optional[str] = Field(
        None,
        description="Compressed timeline: '0.0:S0,5.46:S1,13.78:S0' (start:speaker)",
    )


class TranscriptResponse(BaseModel):
    """Response for transcript retrieval."""

    id: UUID = Field(..., description="Transcript ID")
    recording_id: UUID = Field(..., description="Associated recording ID")
    asr_engine: str = Field(..., description="ASR engine used")
    asr_model_version: Optional[str] = Field(None, description="Model version")
    status: TranscriptStatus = Field(..., description="Processing status")
    plain_text: Optional[str] = Field(None, description="Full transcript text")
    segments: Optional[list[dict[str, Any]]] = Field(None, description="Timestamped segments")
    language_detected: Optional[str] = Field(None, description="Detected language code")
    duration: Optional[float] = Field(None, description="Audio duration in seconds")
    processing_time_sec: Optional[float] = Field(None, description="Processing time")
    average_confidence: Optional[float] = Field(None, description="Average confidence score")
    created_at: datetime = Field(..., description="Creation timestamp")
    completed_at: Optional[datetime] = Field(None, description="Completion timestamp")
    error_message: Optional[str] = Field(None, description="Error if failed")

    # Speaker diarization (lazy-loaded via include_diarization parameter)
    speaker_mapping: Optional[dict[str, str]] = Field(
        None,
        description="Speaker label mapping (e.g., {'SPEAKER_00': 'SPEAKER_0'})",
    )
    diarization_summary: Optional[DiarizationSummary] = Field(
        None, description="Diarization summary (compact format)"
    )

    # Physician corrections (for learning loop)
    is_corrected: bool = Field(..., description="Whether physician corrected")
    corrected_text: Optional[str] = Field(None, description="Corrected version")
    corrected_at: Optional[datetime] = Field(None, description="When corrected")
    physician_rating: Optional[int] = Field(None, ge=1, le=5, description="Quality rating (1-5)")
    physician_feedback: Optional[str] = Field(None, description="Free-text feedback")

    class Config:
        """Pydantic config."""

        from_attributes = True


class TranscriptSummaryResponse(BaseModel):
    """Summary response when transcript is processing."""

    recording_id: UUID = Field(..., description="Recording ID")
    status: TranscriptStatus = Field(..., description="Current status")
    message: str = Field(..., description="Status message")
    started_at: Optional[datetime] = Field(None, description="When started")
    estimated_completion: Optional[str] = Field(None, description="Estimated completion time")

    class Config:
        """Pydantic config."""

        from_attributes = True
