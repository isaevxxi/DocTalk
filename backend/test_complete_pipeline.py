#!/usr/bin/env python3
"""
Complete pipeline test - Shows full transcription + diarization output.
This is the actual text that will be processed by the LLM.
"""

import asyncio
from pathlib import Path

from app.services.diarization import get_diarization_service
from app.services.transcription import get_whisper_service


async def test_complete_pipeline():
    """Test complete transcription + diarization pipeline."""

    # Load test audio
    audio_file = Path("test_long_record.mp3")
    if not audio_file.exists():
        print(f"❌ Audio file not found: {audio_file}")
        return

    with open(audio_file, "rb") as f:
        audio_data = f.read()

    print("=" * 100)
    print("COMPLETE PIPELINE TEST - TRANSCRIPTION + DIARIZATION")
    print("=" * 100)
    print()
    print(f"Test Audio: {audio_file.name}")
    print(f"File Size: {len(audio_data) / 1024 / 1024:.2f} MB")
    print()

    # ========================================================================
    # STEP 1: TRANSCRIPTION (Whisper)
    # ========================================================================
    print("=" * 100)
    print("STEP 1: TRANSCRIPTION (Whisper ASR)")
    print("=" * 100)
    print()

    print("⏱️  Running Whisper transcription...")
    whisper_service = get_whisper_service()
    transcription_result = await whisper_service.transcribe(audio_data, language="ru")

    print(f"✅ Transcription complete!")
    print()
    print(f"TRANSCRIPTION RESULTS:")
    print(f"  Duration:        {transcription_result['duration']:.2f}s")
    print(f"  Processing Time: {transcription_result['processing_time']:.2f}s")
    print(f"  Language:        {transcription_result['language']}")
    print(f"  Segments:        {len(transcription_result['segments'])}")
    print(f"  Confidence:      {transcription_result['average_confidence']:.2f}")
    print()

    # ========================================================================
    # STEP 2: DIARIZATION (Pyannote)
    # ========================================================================
    print("=" * 100)
    print("STEP 2: DIARIZATION (Pyannote + Silero VAD)")
    print("=" * 100)
    print()

    print("⏱️  Running speaker diarization...")
    diarization_service = get_diarization_service()
    diarization_result = await diarization_service.diarize(audio_data, num_speakers=2)

    print(f"✅ Diarization complete!")
    print()
    print(f"DIARIZATION RESULTS:")
    print(f"  Speakers:        {diarization_result['num_speakers']}")
    print(f"  Segments:        {len(diarization_result['segments'])}")

    if 'vad_metadata' in diarization_result:
        meta = diarization_result['vad_metadata']
        print(f"  VAD Time:        {meta['vad_time']:.2f}s")
        print(f"  Diarization:     {meta['diarization_time']:.2f}s")
        print(f"  Speech Regions:  {meta['speech_regions']}")

    print()

    # ========================================================================
    # STEP 3: MERGE TRANSCRIPTION + DIARIZATION
    # ========================================================================
    print("=" * 100)
    print("STEP 3: MERGED OUTPUT (Transcription + Speaker Labels)")
    print("=" * 100)
    print()
    print("This is the final text that will be sent to the LLM for processing.")
    print()

    # Merge transcription segments with diarization
    merged_segments = merge_transcription_with_diarization(
        transcription_result['segments'],
        diarization_result['segments']
    )

    print(f"MERGED SEGMENTS ({len(merged_segments)} total):")
    print("-" * 100)
    print()

    for i, segment in enumerate(merged_segments, 1):
        speaker = segment['speaker']
        start = segment['start']
        end = segment['end']
        text = segment['text']

        start_min = int(start // 60)
        start_sec = start % 60
        end_min = int(end // 60)
        end_sec = end % 60

        print(f"{i:2d}. [{speaker}] {start_min}:{start_sec:05.2f} → {end_min}:{end_sec:05.2f}")
        print(f"    {text}")
        print()

    # ========================================================================
    # STEP 4: FINAL TEXT FOR LLM
    # ========================================================================
    print("=" * 100)
    print("STEP 4: FINAL TEXT FOR LLM (Speaker-Labeled Transcript)")
    print("=" * 100)
    print()

    # Format as speaker-labeled conversation
    conversation = format_for_llm(merged_segments)

    print(conversation)
    print()
    print("=" * 100)
    print()

    # Show statistics
    total_chars = len(conversation)
    print(f"STATISTICS:")
    print(f"  Total Characters: {total_chars:,}")
    print(f"  Total Words:      {len(conversation.split()):,}")
    print(f"  Total Segments:   {len(merged_segments)}")
    print(f"  Speakers:         {diarization_result['num_speakers']}")
    print()
    print("✅ This text is now ready for LLM processing (summarization, analysis, etc.)")
    print("=" * 100)


def merge_transcription_with_diarization(
    transcription_segments: list[dict],
    diarization_segments: list[dict]
) -> list[dict]:
    """
    Merge Whisper transcription segments with Pyannote speaker labels.

    Args:
        transcription_segments: Whisper segments with text and timestamps
        diarization_segments: Pyannote segments with speaker labels and timestamps

    Returns:
        List of merged segments with text, speaker, and timestamps
    """
    merged = []

    for trans_seg in transcription_segments:
        trans_start = trans_seg['start']
        trans_end = trans_seg['end']
        trans_text = trans_seg['text'].strip()

        if not trans_text:
            continue

        # Find overlapping diarization segment
        # Use midpoint to determine speaker
        trans_midpoint = (trans_start + trans_end) / 2

        best_speaker = "UNKNOWN"
        max_overlap = 0.0

        for diar_seg in diarization_segments:
            diar_start = diar_seg['start']
            diar_end = diar_seg['end']

            # Calculate overlap
            overlap_start = max(trans_start, diar_start)
            overlap_end = min(trans_end, diar_end)
            overlap_duration = max(0, overlap_end - overlap_start)

            # Check if midpoint falls within this segment
            if diar_start <= trans_midpoint <= diar_end:
                best_speaker = diar_seg['speaker']
                break

            # Track best overlap
            if overlap_duration > max_overlap:
                max_overlap = overlap_duration
                best_speaker = diar_seg['speaker']

        merged.append({
            'start': trans_start,
            'end': trans_end,
            'text': trans_text,
            'speaker': best_speaker,
            'duration': trans_end - trans_start,
        })

    return merged


def format_for_llm(segments: list[dict]) -> str:
    """
    Format merged segments as speaker-labeled conversation for LLM.

    Args:
        segments: Merged segments with speaker and text

    Returns:
        Formatted conversation text
    """
    lines = []
    current_speaker = None
    current_text = []

    for segment in segments:
        speaker = segment['speaker']
        text = segment['text'].strip()

        if speaker == current_speaker:
            # Same speaker, continue
            current_text.append(text)
        else:
            # Speaker change, output previous speaker's text
            if current_speaker is not None and current_text:
                combined = " ".join(current_text)
                lines.append(f"{current_speaker}: {combined}")

            # Start new speaker
            current_speaker = speaker
            current_text = [text]

    # Output final speaker
    if current_speaker is not None and current_text:
        combined = " ".join(current_text)
        lines.append(f"{current_speaker}: {combined}")

    return "\n\n".join(lines)


if __name__ == "__main__":
    asyncio.run(test_complete_pipeline())
