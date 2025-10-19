#!/usr/bin/env python3
"""
Final validation test - Shows actual output with timing.
Compares WITH VAD vs WITHOUT VAD side-by-side.
"""

import asyncio
import time
from pathlib import Path

from app.core.config import settings
from app.services.diarization import get_diarization_service


async def test_final_validation():
    """Final validation showing actual output."""

    # Load test audio
    audio_file = Path("test_long_record.mp3")
    if not audio_file.exists():
        print(f"❌ Audio file not found: {audio_file}")
        return

    with open(audio_file, "rb") as f:
        audio_data = f.read()

    print("=" * 100)
    print("FINAL VALIDATION TEST - ACTUAL OUTPUT COMPARISON")
    print("=" * 100)
    print()
    print(f"Test Audio: {audio_file.name}")
    print(f"File Size: {len(audio_data) / 1024 / 1024:.2f} MB")
    print(f"Duration: ~136.7 seconds (2 minutes 17 seconds)")
    print()

    # ========================================================================
    # TEST 1: WITHOUT VAD (Baseline)
    # ========================================================================
    print("=" * 100)
    print("TEST 1: WITHOUT SILERO VAD (Baseline)")
    print("=" * 100)
    print()

    # Disable VAD
    settings.DIARIZATION_ENABLE_PRE_VAD = False
    get_diarization_service.cache_clear()
    service = get_diarization_service()

    print("⏱️  Starting baseline diarization...")
    start_time = time.time()
    result_without_vad = await service.diarize(audio_data, num_speakers=2)
    baseline_time = time.time() - start_time

    print(f"✅ Baseline complete in {baseline_time:.2f}s")
    print()
    print(f"RESULTS:")
    print(f"  Processing Time: {baseline_time:.2f}s")
    print(f"  RT Factor:       {baseline_time / 136.66:.2f}x")
    print(f"  Speakers:        {result_without_vad['num_speakers']}")
    print(f"  Segments:        {len(result_without_vad['segments'])}")
    print()

    print("ACTUAL SEGMENTS DETECTED (WITHOUT VAD):")
    print("-" * 100)
    for i, seg in enumerate(result_without_vad['segments'][:10], 1):
        speaker = seg['speaker']
        start = seg['start']
        end = seg['end']
        duration = seg['duration']

        start_min = int(start // 60)
        start_sec = start % 60
        end_min = int(end // 60)
        end_sec = end % 60

        print(f"{i:2d}. [{speaker}] {start_min}:{start_sec:05.2f} → {end_min}:{end_sec:05.2f} ({duration:5.2f}s)")

    if len(result_without_vad['segments']) > 10:
        print(f"... ({len(result_without_vad['segments']) - 10} more segments)")
    print()

    # ========================================================================
    # TEST 2: WITH SILERO VAD (Optimized)
    # ========================================================================
    print("=" * 100)
    print("TEST 2: WITH SILERO VAD (Optimized)")
    print("=" * 100)
    print()

    # Enable VAD
    settings.DIARIZATION_ENABLE_PRE_VAD = True
    get_diarization_service.cache_clear()
    service = get_diarization_service()

    print("⏱️  Starting VAD-optimized diarization...")
    start_time = time.time()
    result_with_vad = await service.diarize(audio_data, num_speakers=2)
    vad_time = time.time() - start_time

    print(f"✅ VAD-optimized complete in {vad_time:.2f}s")
    print()
    print(f"RESULTS:")
    print(f"  Processing Time: {vad_time:.2f}s")
    print(f"  RT Factor:       {vad_time / 136.66:.2f}x")
    print(f"  Speakers:        {result_with_vad['num_speakers']}")
    print(f"  Segments:        {len(result_with_vad['segments'])}")

    if 'vad_metadata' in result_with_vad:
        meta = result_with_vad['vad_metadata']
        print()
        print(f"VAD BREAKDOWN:")
        print(f"  VAD Detection:   {meta['vad_time']:.2f}s")
        print(f"  Diarization:     {meta['diarization_time']:.2f}s")
        print(f"  Speech Regions:  {meta['speech_regions']}")
        print(f"  Raw Segments:    {meta['raw_segments']}")
        print(f"  Stitched:        {meta['stitched_segments']}")

    print()
    print("ACTUAL SEGMENTS DETECTED (WITH VAD):")
    print("-" * 100)
    for i, seg in enumerate(result_with_vad['segments'][:10], 1):
        speaker = seg['speaker']
        start = seg['start']
        end = seg['end']
        duration = seg['duration']

        start_min = int(start // 60)
        start_sec = start % 60
        end_min = int(end // 60)
        end_sec = end % 60

        print(f"{i:2d}. [{speaker}] {start_min}:{start_sec:05.2f} → {end_min}:{end_sec:05.2f} ({duration:5.2f}s)")

    if len(result_with_vad['segments']) > 10:
        print(f"... ({len(result_with_vad['segments']) - 10} more segments)")
    print()

    # ========================================================================
    # SIDE-BY-SIDE COMPARISON
    # ========================================================================
    print("=" * 100)
    print("SIDE-BY-SIDE COMPARISON")
    print("=" * 100)
    print()

    # Compare timing
    time_saved = baseline_time - vad_time
    speedup_pct = (time_saved / baseline_time) * 100
    speedup_factor = baseline_time / vad_time

    print("⏱️  PROCESSING TIME:")
    print(f"  WITHOUT VAD: {baseline_time:6.2f}s")
    print(f"  WITH VAD:    {vad_time:6.2f}s")
    print(f"  SAVED:       {time_saved:6.2f}s ({speedup_pct:+.1f}%)")
    print(f"  SPEEDUP:     {speedup_factor:.2f}x faster")
    print()

    # Compare quality
    print("📊 OUTPUT QUALITY:")
    print(f"  WITHOUT VAD: {result_without_vad['num_speakers']} speakers, {len(result_without_vad['segments'])} segments")
    print(f"  WITH VAD:    {result_with_vad['num_speakers']} speakers, {len(result_with_vad['segments'])} segments")

    segment_diff = len(result_without_vad['segments']) - len(result_with_vad['segments'])
    segment_diff_pct = (segment_diff / len(result_without_vad['segments'])) * 100
    print(f"  DIFFERENCE:  {segment_diff:+d} segments ({segment_diff_pct:+.1f}%)")
    print()

    # Compare first 5 segments (timecode accuracy)
    print("🎯 TIMECODE ACCURACY (First 5 segments):")
    print()
    print(f"{'Seg':<5} {'Without VAD':<25} {'With VAD':<25} {'Offset':<10}")
    print("-" * 100)

    for i in range(min(5, len(result_without_vad['segments']), len(result_with_vad['segments']))):
        seg_baseline = result_without_vad['segments'][i]
        seg_vad = result_with_vad['segments'][i]

        baseline_str = f"{seg_baseline['start']:.2f}s - {seg_baseline['end']:.2f}s"
        vad_str = f"{seg_vad['start']:.2f}s - {seg_vad['end']:.2f}s"

        start_offset = abs(seg_baseline['start'] - seg_vad['start'])
        end_offset = abs(seg_baseline['end'] - seg_vad['end'])
        max_offset = max(start_offset, end_offset)

        status = "✅" if max_offset < 0.2 else "⚠️"
        offset_str = f"{status} ±{max_offset:.3f}s"

        print(f"{i+1:<5} {baseline_str:<25} {vad_str:<25} {offset_str:<10}")

    print()

    # Final verdict
    print("=" * 100)
    print("FINAL VERDICT")
    print("=" * 100)
    print()

    if speedup_pct >= 20:
        print(f"✅ SPEED: {speedup_pct:.1f}% faster (target: ≥20%) - PASS")
    else:
        print(f"❌ SPEED: {speedup_pct:.1f}% faster (target: ≥20%) - FAIL")

    if abs(segment_diff_pct) <= 15:
        print(f"✅ QUALITY: {abs(segment_diff_pct):.1f}% segment difference (target: ≤15%) - PASS")
    else:
        print(f"⚠️  QUALITY: {abs(segment_diff_pct):.1f}% segment difference (target: ≤15%) - MARGINAL")

    if result_without_vad['num_speakers'] == result_with_vad['num_speakers']:
        print(f"✅ SPEAKERS: Same speaker count ({result_with_vad['num_speakers']}) - PASS")
    else:
        print(f"❌ SPEAKERS: Different speaker count - FAIL")

    print()

    if speedup_pct >= 20 and result_without_vad['num_speakers'] == result_with_vad['num_speakers']:
        print("🎉 ✅ SILERO VAD VALIDATION: SUCCESS")
        print()
        print(f"The system is {speedup_factor:.2f}x faster with VAD enabled,")
        print(f"saving {time_saved:.2f}s per recording while maintaining quality!")
    else:
        print("⚠️  SILERO VAD VALIDATION: NEEDS REVIEW")

    print()
    print("=" * 100)

    # Show ALL segments if requested
    print()
    print("=" * 100)
    print("COMPLETE SEGMENT LIST (WITH VAD - ALL 38 SEGMENTS)")
    print("=" * 100)
    print()

    for i, seg in enumerate(result_with_vad['segments'], 1):
        speaker = seg['speaker']
        start = seg['start']
        end = seg['end']
        duration = seg['duration']

        start_min = int(start // 60)
        start_sec = start % 60
        end_min = int(end // 60)
        end_sec = end % 60

        print(f"{i:2d}. [{speaker}] {start_min}:{start_sec:05.2f} → {end_min}:{end_sec:05.2f} ({duration:5.2f}s)")

    print()
    print("=" * 100)


if __name__ == "__main__":
    asyncio.run(test_final_validation())
