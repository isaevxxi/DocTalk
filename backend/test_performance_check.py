#!/usr/bin/env python3
"""Quick performance test - Verify processing time is optimal."""

import asyncio
import time
from pathlib import Path

from app.services.diarization import get_diarization_service
from app.services.transcription import get_whisper_service


async def test_performance():
    """Test performance of complete pipeline."""

    # Load test audio
    audio_file = Path("test_long_record.mp3")
    with open(audio_file, "rb") as f:
        audio_data = f.read()

    file_size_mb = len(audio_data) / 1024 / 1024

    print("=" * 80)
    print("PERFORMANCE VERIFICATION TEST")
    print("=" * 80)
    print(f"Audio File: {audio_file.name} ({file_size_mb:.2f} MB)")
    print()

    # Start total timer
    total_start = time.time()

    # ========================================================================
    # TRANSCRIPTION (Whisper)
    # ========================================================================
    print("⏱️  Running Whisper transcription...")
    whisper_start = time.time()
    whisper_service = get_whisper_service()
    transcription_result = await whisper_service.transcribe(audio_data, language="ru")
    whisper_elapsed = time.time() - whisper_start

    audio_duration = transcription_result['duration']
    transcription_time = transcription_result['processing_time']
    rt_factor_whisper = transcription_time / audio_duration

    print(f"✅ Whisper complete: {whisper_elapsed:.2f}s")
    print(f"   Audio duration: {audio_duration:.2f}s")
    print(f"   Processing time: {transcription_time:.2f}s")
    print(f"   RT factor: {rt_factor_whisper:.2f}x")
    print()

    # ========================================================================
    # DIARIZATION (Pyannote + Silero VAD)
    # ========================================================================
    print("⏱️  Running diarization (VAD + Pyannote)...")
    diarization_start = time.time()
    diarization_service = get_diarization_service()
    diarization_result = await diarization_service.diarize(audio_data, num_speakers=2)
    diarization_elapsed = time.time() - diarization_start

    if 'vad_metadata' in diarization_result:
        meta = diarization_result['vad_metadata']
        vad_time = meta['vad_time']
        diar_time = meta['diarization_time']
        speech_regions = meta['speech_regions']

        print(f"✅ Diarization complete: {diarization_elapsed:.2f}s")
        print(f"   VAD time: {vad_time:.2f}s")
        print(f"   Diarization time: {diar_time:.2f}s")
        print(f"   Speech regions: {speech_regions}")
        print(f"   RT factor: {diarization_elapsed / audio_duration:.2f}x")
        print()

    # ========================================================================
    # TOTAL PERFORMANCE
    # ========================================================================
    total_elapsed = time.time() - total_start
    total_rt_factor = total_elapsed / audio_duration

    print("=" * 80)
    print("PERFORMANCE SUMMARY")
    print("=" * 80)
    print(f"Audio Duration:      {audio_duration:.2f}s")
    print(f"Transcription Time:  {transcription_time:.2f}s  (RT factor: {rt_factor_whisper:.2f}x)")
    print(f"Diarization Time:    {diarization_elapsed:.2f}s  (RT factor: {diarization_elapsed / audio_duration:.2f}x)")
    print(f"Total Processing:    {total_elapsed:.2f}s  (RT factor: {total_rt_factor:.2f}x)")
    print()

    # Performance targets
    print("PERFORMANCE TARGETS:")
    print(f"  Transcription: {'✅ PASS' if rt_factor_whisper < 0.3 else '❌ FAIL'} (target: <0.3x RT)")
    print(f"  Diarization:   {'✅ PASS' if diarization_elapsed / audio_duration < 0.35 else '❌ FAIL'} (target: <0.35x RT)")
    print(f"  Total:         {'✅ PASS' if total_rt_factor < 0.6 else '⚠️  WARNING'} (target: <0.6x RT)")
    print()

    # Based on 136.7s audio from previous tests
    if audio_duration > 130:
        print("COMPARISON TO PREVIOUS BENCHMARKS:")
        print(f"  Previous best: ~35.59s total processing")
        print(f"  Current:       {total_elapsed:.2f}s")
        print(f"  Improvement:   {((35.59 - total_elapsed) / 35.59 * 100):.1f}%")

    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(test_performance())
