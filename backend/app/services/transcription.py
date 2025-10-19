"""Whisper ASR transcription service."""

import asyncio
import logging
import time
from functools import lru_cache
from io import BytesIO
from typing import Any

import faster_whisper
from faster_whisper import WhisperModel

from app.core.config import settings
from app.services.transcript_processing import TranscriptProcessor

logger = logging.getLogger(__name__)


class WhisperService:
    """
    Whisper speech-to-text transcription service.

    Uses faster-whisper for efficient inference with CTranslate2.
    Optimized for fast, stable transcription with ASR hygiene filtering.
    """

    def __init__(self) -> None:
        """
        Initialize Whisper model with application settings.

        Raises:
            RuntimeError: If model initialization fails
        """
        try:
            self.model_name = settings.WHISPER_MODEL
            self.device = settings.WHISPER_DEVICE
            self.compute_type = settings.WHISPER_COMPUTE_TYPE
            self.language = settings.WHISPER_LANGUAGE

            logger.info(
                f"Initializing Whisper model: {self.model_name} "
                f"(device={self.device}, compute_type={self.compute_type})"
            )

            # Load model
            self.model = WhisperModel(
                model_size_or_path=self.model_name,
                device=self.device,
                compute_type=self.compute_type,
            )

            logger.info("Whisper model loaded successfully")

        except Exception as e:
            logger.error(f"Failed to initialize Whisper model: {e}")
            raise RuntimeError(f"Whisper model initialization failed: {e}") from e


    async def transcribe(
        self,
        audio_data: bytes,
        language: str = "ru",
    ) -> dict[str, Any]:
        """
        Transcribe audio data to text.

        Args:
            audio_data: Raw audio file bytes
            language: Language code (default: 'ru' for Russian)

        Returns:
            Dict with:
                - text: Full transcription text
                - segments: List of timestamped segments with speaker info
                - language: Detected language
                - duration: Audio duration in seconds
                - processing_time: Time taken to transcribe
                - average_confidence: Average confidence score

        Raises:
            RuntimeError: If transcription fails
        """

        def _transcribe() -> dict[str, Any]:
            """Sync wrapper for Whisper transcription."""
            # Validate input
            if not audio_data or len(audio_data) == 0:
                raise ValueError("Audio data is empty")

            try:
                start_time = time.time()

                logger.debug(f"Starting transcription (language={language}, size={len(audio_data)} bytes)")

                # Transcribe with word-level timestamps
                # NOTE: Keeping configuration minimal for best performance
                # Medical vocabulary boosting via hotwords/prompts caused 2-6x slowdown
                segments, info = self.model.transcribe(
                    audio=BytesIO(audio_data),
                    language=language,
                    beam_size=5,
                    word_timestamps=True,
                    vad_filter=True,  # Voice activity detection
                    vad_parameters={
                        "threshold": 0.5,
                        "min_speech_duration_ms": 250,
                        "max_speech_duration_s": float("inf"),
                        "min_silence_duration_ms": 2000,
                        "speech_pad_ms": 400,
                    },
                )

                # Process segments
                full_text = []
                segment_list = []
                total_confidence = 0.0
                segment_count = 0

                for segment in segments:
                    segment_text = segment.text.strip()

                    # Build structured segment
                    segment_data = {
                        "start": segment.start,
                        "end": segment.end,
                        "text": segment_text,  # Original text (will be updated if hygiene applied)
                        "confidence": segment.avg_logprob,
                        "no_speech_prob": segment.no_speech_prob,
                    }

                    # Add word-level timestamps if available
                    if segment.words:
                        raw_words = [
                            {
                                "word": word.word,
                                "start": word.start,
                                "end": word.end,
                                "probability": word.probability,
                            }
                            for word in segment.words
                        ]

                        # Apply ASR hygiene filtering
                        cleaned_words, removed_words = TranscriptProcessor.apply_hygiene_filter(
                            raw_words,
                            min_probability=0.3,
                        )

                        # Rebuild segment text from cleaned words
                        cleaned_text = "".join(w["word"] for w in cleaned_words).strip()

                        # Update segment with cleaned data
                        segment_data["words"] = cleaned_words
                        segment_data["text"] = cleaned_text  # Use cleaned text
                        segment_data["hygiene"] = {
                            "original_word_count": len(raw_words),
                            "cleaned_word_count": len(cleaned_words),
                            "removed_word_count": len(removed_words),
                            "removed_words": removed_words if removed_words else None,
                        }

                        # Use cleaned text for full transcript
                        full_text.append(cleaned_text)
                    else:
                        # No word-level data, use original segment text
                        full_text.append(segment_text)

                    segment_list.append(segment_data)
                    total_confidence += segment.avg_logprob
                    segment_count += 1

                processing_time = time.time() - start_time

                # Apply segment merging if enabled
                final_segments = segment_list
                merge_stats = None
                if settings.MERGE_SHORT_PAUSES:
                    final_segments = TranscriptProcessor.merge_short_pauses(
                        segment_list,
                        max_gap=settings.MERGE_PAUSE_THRESHOLD,
                    )
                    merge_stats = TranscriptProcessor.calculate_merge_stats(
                        segment_list,
                        final_segments,
                    )

                # Rebuild full text from final segments
                final_text = " ".join(seg["text"] for seg in final_segments)

                result = {
                    "text": final_text,
                    "segments": final_segments,
                    "language": info.language,
                    "duration": info.duration,
                    "processing_time": processing_time,
                    "average_confidence": (
                        total_confidence / segment_count if segment_count > 0 else 0.0
                    ),
                }

                # Add merge stats if merging was applied
                if merge_stats:
                    result["merge_stats"] = merge_stats

                logger.info(
                    f"Transcription complete: {len(final_text)} chars, "
                    f"{len(final_segments)} segments, {processing_time:.2f}s"
                )

                return result

            except ValueError as e:
                # Re-raise validation errors
                raise
            except Exception as e:
                logger.error(f"Transcription failed: {e}", exc_info=True)
                raise RuntimeError(f"Whisper transcription failed: {e}") from e

        # Run in thread pool (Whisper is CPU/GPU bound)
        return await asyncio.to_thread(_transcribe)

    def get_model_name(self) -> str:
        """Get model name for metadata."""
        return f"faster-whisper-{self.model_name}"

    def get_model_version(self) -> str:
        """Get model version for metadata."""
        return f"faster-whisper-{faster_whisper.__version__}"


@lru_cache
def get_whisper_service() -> WhisperService:
    """Get cached Whisper service instance."""
    return WhisperService()
