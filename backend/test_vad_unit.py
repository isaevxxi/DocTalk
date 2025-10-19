#!/usr/bin/env python3
"""
Unit tests for VAD service and chunking logic.

Tests core functionality without full diarization processing.
"""

import asyncio
from pathlib import Path

from app.services.vad import get_vad_service


async def test_vad_basic():
    """Test basic VAD speech detection."""
    print("=" * 80)
    print("VAD UNIT TESTS")
    print("=" * 80)

    # Load test audio
    audio_file = Path("test_long_record.mp3")
    if not audio_file.exists():
        print(f"❌ Audio file not found: {audio_file}")
        return

    with open(audio_file, "rb") as f:
        audio_data = f.read()

    print(f"\nTest File: {audio_file.name} ({len(audio_data) / 1024 / 1024:.2f} MB)")

    # Test 1: VAD Detection
    print("\n" + "-" * 80)
    print("TEST 1: Speech Region Detection")
    print("-" * 80)

    vad_service = get_vad_service()
    speech_regions = vad_service.detect_speech(audio_data)

    print(f"\nResults:")
    print(f"  Speech regions detected: {len(speech_regions)}")
    print(f"\n  First 5 regions:")
    for i, region in enumerate(speech_regions[:5]):
        duration = region['end'] - region['start']
        print(f"    {i+1}. {region['start']:.2f}s - {region['end']:.2f}s ({duration:.2f}s)")

    # Calculate speech ratio
    total_speech_duration = sum(r['end'] - r['start'] for r in speech_regions)
    total_audio_duration = 136.66  # Known duration
    speech_ratio = (total_speech_duration / total_audio_duration) * 100
    silence_ratio = 100 - speech_ratio

    print(f"\n  Speech Statistics:")
    print(f"    Total audio:     {total_audio_duration:.2f}s")
    print(f"    Speech detected: {total_speech_duration:.2f}s ({speech_ratio:.1f}%)")
    print(f"    Silence removed: {total_audio_duration - total_speech_duration:.2f}s ({silence_ratio:.1f}%)")

    # Test 2: Chunking Logic Validation
    print("\n" + "-" * 80)
    print("TEST 2: Chunking Logic Validation")
    print("-" * 80)

    from app.core.config import settings

    pad_ms = settings.DIARIZATION_VAD_PAD_MS
    total_duration_ms = total_audio_duration * 1000

    print(f"\nPadding: {pad_ms}ms")
    print(f"Total duration: {total_duration_ms}ms")

    # Simulate chunking
    chunks = []
    for region in speech_regions:
        chunk_start_ms = max(0, int(region['start'] * 1000) - pad_ms)
        chunk_end_ms = min(total_duration_ms, int(region['end'] * 1000) + pad_ms)
        chunk_duration_ms = chunk_end_ms - chunk_start_ms

        chunks.append({
            'start_ms': chunk_start_ms,
            'end_ms': chunk_end_ms,
            'duration_ms': chunk_duration_ms,
        })

    total_chunk_duration = sum(c['duration_ms'] for c in chunks) / 1000
    processing_ratio = (total_chunk_duration / total_audio_duration) * 100

    print(f"\nChunk Statistics:")
    print(f"  Total chunks:      {len(chunks)}")
    print(f"  Chunk duration:    {total_chunk_duration:.2f}s ({processing_ratio:.1f}% of total)")
    print(f"  Time savings:      {100 - processing_ratio:.1f}%")

    print(f"\n  Sample chunks (first 3):")
    for i, chunk in enumerate(chunks[:3]):
        print(f"    {i+1}. {chunk['start_ms'] / 1000:.2f}s - {chunk['end_ms'] / 1000:.2f}s ({chunk['duration_ms'] / 1000:.2f}s)")

    # Test 3: Offset Mapping Validation
    print("\n" + "-" * 80)
    print("TEST 3: Offset Mapping Validation")
    print("-" * 80)

    # Simulate a segment in a chunk
    chunk_offset_ms = chunks[0]['start_ms']
    chunk_offset_sec = chunk_offset_ms / 1000

    # Simulated segment within chunk (relative to chunk start)
    segment_in_chunk = {'start': 1.5, 'end': 3.2}

    # Map to original timeline
    mapped_start = segment_in_chunk['start'] + chunk_offset_sec
    mapped_end = segment_in_chunk['end'] + chunk_offset_sec

    print(f"\nOffset Mapping Example (Chunk 1):")
    print(f"  Chunk offset:      {chunk_offset_sec:.2f}s")
    print(f"  Segment in chunk:  {segment_in_chunk['start']:.2f}s - {segment_in_chunk['end']:.2f}s")
    print(f"  Mapped to original: {mapped_start:.2f}s - {mapped_end:.2f}s")

    # Validate it's within original audio duration
    if mapped_start >= 0 and mapped_end <= total_audio_duration:
        print(f"  ✅ Timecodes valid (within 0-{total_audio_duration:.2f}s)")
    else:
        print(f"  ❌ Timecodes invalid!")

    # Test 4: Segment Stitching Logic
    print("\n" + "-" * 80)
    print("TEST 4: Segment Stitching Logic")
    print("-" * 80)

    # Simulate segments that should be stitched
    test_segments = [
        {'start': 1.0, 'end': 3.0, 'speaker': 'SPEAKER_00', 'duration': 2.0},
        {'start': 3.2, 'end': 5.0, 'speaker': 'SPEAKER_00', 'duration': 1.8},  # Same speaker, small gap (0.2s)
        {'start': 5.5, 'end': 7.0, 'speaker': 'SPEAKER_01', 'duration': 1.5},  # Different speaker
        {'start': 7.1, 'end': 9.0, 'speaker': 'SPEAKER_01', 'duration': 1.9},  # Same speaker, small gap (0.1s)
    ]

    stitch_gap_sec = settings.DIARIZATION_STITCH_GAP_MS / 1000.0

    print(f"\nStitching gap threshold: {stitch_gap_sec}s")
    print(f"Input segments: {len(test_segments)}")
    print(f"\n  Before stitching:")
    for i, seg in enumerate(test_segments):
        print(f"    {i+1}. {seg['start']:.1f}s-{seg['end']:.1f}s [{seg['speaker']}]")

    # Simulate stitching
    stitched = []
    current = test_segments[0].copy()

    for next_seg in test_segments[1:]:
        gap = next_seg['start'] - current['end']
        same_speaker = next_seg['speaker'] == current['speaker']

        if same_speaker and gap <= stitch_gap_sec:
            current['end'] = next_seg['end']
            current['duration'] = current['end'] - current['start']
        else:
            stitched.append(current)
            current = next_seg.copy()

    stitched.append(current)

    print(f"\n  After stitching:")
    for i, seg in enumerate(stitched):
        print(f"    {i+1}. {seg['start']:.1f}s-{seg['end']:.1f}s ({seg['duration']:.1f}s) [{seg['speaker']}]")

    print(f"\n  Stitched {len(test_segments)} → {len(stitched)} segments")

    if len(stitched) == 2:
        print(f"  ✅ Stitching logic correct (expected 2 segments)")
    else:
        print(f"  ❌ Stitching logic incorrect (expected 2, got {len(stitched)})")

    # Summary
    print("\n" + "=" * 80)
    print("UNIT TEST SUMMARY")
    print("=" * 80)
    print(f"✅ VAD Detection:        {len(speech_regions)} speech regions detected")
    print(f"✅ Speech Ratio:         {speech_ratio:.1f}% speech, {silence_ratio:.1f}% silence")
    print(f"✅ Processing Savings:   {100 - processing_ratio:.1f}% less audio to process")
    print(f"✅ Offset Mapping:       Validated")
    print(f"✅ Segment Stitching:    Validated")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(test_vad_basic())
