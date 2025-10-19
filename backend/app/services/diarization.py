"""Speaker diarization service using pyannote.audio."""

import asyncio
import logging
import time
from functools import lru_cache
from io import BytesIO
from typing import Any

from pydub import AudioSegment
from pyannote.audio import Pipeline

from app.core.config import settings

logger = logging.getLogger(__name__)


class DiarizationService:
    """
    Speaker diarization service for identifying who spoke when.

    Uses pyannote.audio pipeline for speaker separation.
    Designed for medical consultations with 2 speakers (doctor + patient).
    """

    def __init__(self) -> None:
        """
        Initialize diarization pipeline with performance optimizations.

        Note: Requires Hugging Face token for model download.
        Set HF_TOKEN environment variable.

        Raises:
            RuntimeError: If pipeline initialization fails
        """
        try:
            # Load pretrained pipeline
            # Use pyannote/speaker-diarization-3.1 (state-of-the-art as of 2024)
            self.pipeline = Pipeline.from_pretrained(
                "pyannote/speaker-diarization-3.1",
                use_auth_token=settings.HF_TOKEN,
            )

            # Apply performance optimizations (10-30% speedup)
            # These parameters tune the internal models for faster inference
            # without significantly impacting accuracy

            # Optimization 1: Increase batch sizes for faster processing
            # Segmentation model processes audio chunks - larger batches = faster
            if hasattr(self.pipeline, "_segmentation"):
                self.pipeline._segmentation.batch_size = settings.DIARIZATION_SEGMENTATION_BATCH_SIZE
                logger.debug(f"Segmentation batch size: {settings.DIARIZATION_SEGMENTATION_BATCH_SIZE}")

            # Embedding model extracts speaker features - larger batches = faster
            if hasattr(self.pipeline, "_embedding"):
                self.pipeline._embedding.batch_size = settings.DIARIZATION_EMBEDDING_BATCH_SIZE
                logger.debug(f"Embedding batch size: {settings.DIARIZATION_EMBEDDING_BATCH_SIZE}")

            logger.info("Diarization pipeline initialized successfully with optimizations")

        except Exception as e:
            logger.error(f"Failed to initialize diarization pipeline: {e}")
            raise RuntimeError(f"Diarization pipeline initialization failed: {e}") from e

        # Configure for medical consultations (typically 2 speakers)
        self.num_speakers = 2  # Doctor + Patient
        self.min_speakers = 1  # Sometimes only doctor speaks (dictation)
        self.max_speakers = 3  # Occasionally: doctor + patient + family member

    async def diarize(
        self,
        audio_data: bytes,
        num_speakers: int | None = None,
    ) -> dict[str, Any]:
        """
        Perform speaker diarization on audio.

        Args:
            audio_data: Raw audio file bytes
            num_speakers: Expected number of speakers (default: 2 for medical)

        Returns:
            Dict with:
                - segments: List of speaker segments with start/end times
                - speakers: List of unique speaker labels
                - speaker_mapping: Suggested mapping to DOCTOR/PATIENT

        Raises:
            RuntimeError: If diarization fails
        """

        def _diarize() -> dict[str, Any]:
            """Sync wrapper for pyannote pipeline with optional VAD pre-processing."""
            # Validate input
            if not audio_data or len(audio_data) == 0:
                raise ValueError("Audio data is empty")

            try:
                # Option 1: VAD-enabled diarization (20-40% faster)
                if settings.DIARIZATION_ENABLE_PRE_VAD:
                    return self._diarize_with_vad(audio_data, num_speakers)

                # Option 2: Standard diarization (full audio)
                else:
                    return self._diarize_standard(audio_data, num_speakers)

            except ValueError:
                # Re-raise validation errors
                raise
            except Exception as e:
                logger.error(f"Diarization failed: {e}", exc_info=True)
                raise RuntimeError(f"Speaker diarization failed: {e}") from e

        # Run in thread pool (CPU-intensive)
        return await asyncio.to_thread(_diarize)

    def _diarize_standard(
        self,
        audio_data: bytes,
        num_speakers: int | None = None,
    ) -> dict[str, Any]:
        """
        Standard diarization without VAD pre-processing.

        Processes the entire audio file.

        Args:
            audio_data: Raw audio bytes
            num_speakers: Expected number of speakers

        Returns:
            Diarization results with segments and speaker mapping
        """
        # Convert bytes to file-like object
        audio_file = BytesIO(audio_data)

        # Run diarization
        if num_speakers:
            logger.debug(f"Running standard diarization with num_speakers={num_speakers}")
            diarization = self.pipeline(
                audio_file,
                num_speakers=num_speakers,
            )
        else:
            logger.debug(f"Running standard diarization with min={self.min_speakers}, max={self.max_speakers}")
            diarization = self.pipeline(
                audio_file,
                min_speakers=self.min_speakers,
                max_speakers=self.max_speakers,
            )

        # Extract segments
        segments = []
        speakers = set()

        for turn, _, speaker in diarization.itertracks(yield_label=True):
            segments.append(
                {
                    "start": turn.start,
                    "end": turn.end,
                    "speaker": speaker,
                    "duration": turn.end - turn.start,
                }
            )
            speakers.add(speaker)

        if not segments:
            logger.warning("Diarization produced no segments")
            return {
                "segments": [],
                "speakers": [],
                "speaker_mapping": {},
                "num_speakers": 0,
            }

        # Get neutral speaker mapping
        speaker_mapping = self._infer_roles(segments, list(speakers))

        logger.info(f"Diarization complete: {len(speakers)} speakers, {len(segments)} segments")

        return {
            "segments": segments,
            "speakers": list(speakers),
            "speaker_mapping": speaker_mapping,
            "num_speakers": len(speakers),
        }

    def _diarize_with_vad(
        self,
        audio_data: bytes,
        num_speakers: int | None = None,
    ) -> dict[str, Any]:
        """
        VAD-enabled diarization with chunking and offset mapping.

        Process flow:
        1. Run Silero VAD to detect speech regions
        2. Extract audio chunks for each speech region (with padding)
        3. Run diarization on each chunk independently
        4. Map segment timestamps back to original timeline
        5. Stitch adjacent same-speaker segments

        Expected speedup: 20-40% on typical medical audio (20-40% silence)

        Args:
            audio_data: Raw audio bytes
            num_speakers: Expected number of speakers

        Returns:
            Diarization results with segments mapped to original timeline
        """
        from app.services.vad import get_vad_service

        vad_start_time = time.time()

        # Step 1: Detect speech regions using Silero VAD
        logger.debug("Running VAD to detect speech regions...")
        vad_service = get_vad_service()
        speech_regions = vad_service.detect_speech(audio_data)

        if not speech_regions:
            logger.warning("VAD detected no speech regions")
            return {
                "segments": [],
                "speakers": [],
                "speaker_mapping": {},
                "num_speakers": 0,
            }

        vad_time = time.time() - vad_start_time
        logger.info(f"VAD complete in {vad_time:.2f}s: {len(speech_regions)} speech regions detected")

        # Step 2: Load full audio for chunking
        audio_segment = AudioSegment.from_file(BytesIO(audio_data))
        total_duration_ms = len(audio_segment)
        total_duration_sec = total_duration_ms / 1000.0

        # Step 3: Process each speech chunk
        all_segments = []
        all_speakers = set()

        diarization_start_time = time.time()

        for idx, region in enumerate(speech_regions):
            # Calculate chunk boundaries with padding (in milliseconds)
            chunk_start_ms = max(0, int(region['start'] * 1000) - settings.DIARIZATION_VAD_PAD_MS)
            chunk_end_ms = min(total_duration_ms, int(region['end'] * 1000) + settings.DIARIZATION_VAD_PAD_MS)

            # Extract audio chunk
            audio_chunk = audio_segment[chunk_start_ms:chunk_end_ms]

            # Convert chunk to bytes for pyannote
            chunk_buffer = BytesIO()
            audio_chunk.export(chunk_buffer, format="wav")
            chunk_buffer.seek(0)

            # Run diarization on this chunk
            logger.debug(
                f"Processing chunk {idx + 1}/{len(speech_regions)}: "
                f"{chunk_start_ms / 1000:.2f}s - {chunk_end_ms / 1000:.2f}s "
                f"({(chunk_end_ms - chunk_start_ms) / 1000:.2f}s duration)"
            )

            try:
                if num_speakers:
                    chunk_diarization = self.pipeline(
                        chunk_buffer,
                        num_speakers=num_speakers,
                    )
                else:
                    chunk_diarization = self.pipeline(
                        chunk_buffer,
                        min_speakers=self.min_speakers,
                        max_speakers=self.max_speakers,
                    )

                # Extract segments and map to original timeline
                offset_sec = chunk_start_ms / 1000.0

                for turn, _, speaker in chunk_diarization.itertracks(yield_label=True):
                    # Map timestamps back to original timeline
                    original_start = turn.start + offset_sec
                    original_end = turn.end + offset_sec

                    # Clamp to valid range [0, total_duration]
                    original_start = max(0.0, min(original_start, total_duration_sec))
                    original_end = max(0.0, min(original_end, total_duration_sec))

                    # Skip invalid segments
                    if original_end <= original_start:
                        continue

                    all_segments.append(
                        {
                            "start": original_start,
                            "end": original_end,
                            "speaker": speaker,
                            "duration": original_end - original_start,
                        }
                    )
                    all_speakers.add(speaker)

            except Exception as chunk_error:
                logger.warning(f"Failed to process chunk {idx + 1}: {chunk_error}")
                # Continue with other chunks
                continue

        diarization_time = time.time() - diarization_start_time
        logger.info(f"Chunk diarization complete in {diarization_time:.2f}s: {len(all_segments)} raw segments")

        if not all_segments:
            logger.warning("Diarization produced no segments after VAD filtering")
            return {
                "segments": [],
                "speakers": [],
                "speaker_mapping": {},
                "num_speakers": 0,
            }

        # Step 4: Sort segments by start time
        all_segments.sort(key=lambda x: x["start"])

        # Step 5: Stitch adjacent same-speaker segments
        stitched_segments = self._stitch_segments(all_segments)

        # Step 6: Generate speaker mapping
        speaker_mapping = self._infer_roles(stitched_segments, list(all_speakers))

        total_time = time.time() - vad_start_time
        logger.info(
            f"VAD-enabled diarization complete in {total_time:.2f}s: "
            f"{len(all_speakers)} speakers, {len(stitched_segments)} final segments "
            f"(stitched from {len(all_segments)} raw segments)"
        )

        return {
            "segments": stitched_segments,
            "speakers": list(all_speakers),
            "speaker_mapping": speaker_mapping,
            "num_speakers": len(all_speakers),
            "vad_metadata": {
                "vad_time": vad_time,
                "diarization_time": diarization_time,
                "total_time": total_time,
                "speech_regions": len(speech_regions),
                "raw_segments": len(all_segments),
                "stitched_segments": len(stitched_segments),
            },
        }

    def _stitch_segments(
        self,
        segments: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """
        Stitch adjacent segments from the same speaker.

        Merges segments that are close together (gap < DIARIZATION_STITCH_GAP_MS)
        and spoken by the same speaker. This reduces fragmentation from chunked processing.

        Args:
            segments: List of segments sorted by start time

        Returns:
            List of stitched segments
        """
        if not segments:
            return []

        stitch_gap_sec = settings.DIARIZATION_STITCH_GAP_MS / 1000.0
        stitched = []
        current = segments[0].copy()

        for next_seg in segments[1:]:
            gap = next_seg["start"] - current["end"]
            same_speaker = next_seg["speaker"] == current["speaker"]

            # Stitch if same speaker and gap is small enough
            if same_speaker and gap <= stitch_gap_sec:
                # Extend current segment to include next segment
                current["end"] = next_seg["end"]
                current["duration"] = current["end"] - current["start"]
            else:
                # Finish current segment and start new one
                stitched.append(current)
                current = next_seg.copy()

        # Add final segment
        stitched.append(current)

        logger.debug(f"Stitched {len(segments)} segments into {len(stitched)} segments")

        return stitched

    def _infer_roles(
        self, segments: list[dict[str, Any]], speakers: list[str]
    ) -> dict[str, str]:
        """
        Return neutral speaker labels without automatic role inference.

        Automatic role inference (DOCTOR vs PATIENT) is unreliable because:
        - Medical conversations have high variability (dictation, consultation, family present)
        - Speaking time/frequency heuristics often fail on short recordings
        - Incorrect labels are worse than neutral labels for downstream processing

        Instead, we return normalized neutral labels (SPEAKER_0, SPEAKER_1, etc.)
        sorted by first appearance in the audio timeline.

        Benefits:
        - ✅ No incorrect assumptions about speaker roles
        - ✅ Consistent labeling across recordings
        - ✅ Role assignment can be done in post-processing or UI
        - ✅ Faster processing (no heuristic calculations)

        Args:
            segments: Diarization segments
            speakers: List of unique speaker labels from pyannote

        Returns:
            Mapping of pyannote labels to neutral labels
            (e.g., {"SPEAKER_00": "SPEAKER_0", "SPEAKER_01": "SPEAKER_1"})
        """
        if len(speakers) == 0:
            return {}

        # Sort speakers by first appearance in timeline
        first_appearance = {}
        for segment in segments:
            speaker = segment["speaker"]
            if speaker not in first_appearance:
                first_appearance[speaker] = segment["start"]

        sorted_speakers = sorted(first_appearance.items(), key=lambda x: x[1])

        # Map to neutral labels (SPEAKER_0, SPEAKER_1, ...)
        mapping = {}
        for idx, (speaker, _) in enumerate(sorted_speakers):
            mapping[speaker] = f"SPEAKER_{idx}"

        return mapping

    def map_transcription_to_speakers(
        self,
        transcription_segments: list[dict[str, Any]],
        diarization_segments: list[dict[str, Any]],
        speaker_mapping: dict[str, str],
    ) -> list[dict[str, Any]]:
        """
        Map Whisper transcription segments to speaker labels.

        Uses temporal overlap to assign speakers to transcription segments.

        Args:
            transcription_segments: Segments from Whisper with text + timestamps
            diarization_segments: Speaker segments from pyannote
            speaker_mapping: Mapping of speaker labels to roles

        Returns:
            Transcription segments with added "speaker" field
        """
        enriched_segments = []

        for trans_seg in transcription_segments:
            trans_start = trans_seg["start"]
            trans_end = trans_seg["end"]

            # Find diarization segment with maximum overlap
            best_speaker = "UNKNOWN"
            max_overlap = 0.0

            for diar_seg in diarization_segments:
                diar_start = diar_seg["start"]
                diar_end = diar_seg["end"]

                # Calculate overlap
                overlap_start = max(trans_start, diar_start)
                overlap_end = min(trans_end, diar_end)
                overlap = max(0.0, overlap_end - overlap_start)

                if overlap > max_overlap:
                    max_overlap = overlap
                    raw_speaker = diar_seg["speaker"]
                    best_speaker = speaker_mapping.get(raw_speaker, raw_speaker)

            # Add speaker to segment
            enriched_seg = trans_seg.copy()
            enriched_seg["speaker"] = best_speaker
            enriched_segments.append(enriched_seg)

        return enriched_segments


@lru_cache
def get_diarization_service() -> DiarizationService:
    """Get cached diarization service instance."""
    return DiarizationService()
