#!/usr/bin/env python3
"""
Vocabulary Size Performance Test
Tests processing time with different vocabulary sizes: 0, 50, 150, 280 words
"""

import asyncio
import json
import sys
import time
from pathlib import Path

# Add app to path
sys.path.insert(0, str(Path(__file__).parent))

from app.services.transcription import WhisperService


async def test_vocabulary_size(audio_file: str, vocab_file: str | None, test_name: str):
    """Test transcription with specific vocabulary file."""
    print(f"\n{'='*60}")
    print(f"Test: {test_name}")
    print(f"Vocabulary: {vocab_file if vocab_file else 'None (baseline)'}")
    print(f"{'='*60}")

    # Read audio file
    with open(audio_file, "rb") as f:
        audio_data = f.read()

    # Create service with specific vocabulary
    if vocab_file:
        # Temporarily override vocabulary file path
        original_vocab_file = WhisperService.MEDICAL_VOCAB_FILE
        WhisperService.MEDICAL_VOCAB_FILE = Path(vocab_file)

    try:
        # Initialize service (this loads vocabulary)
        init_start = time.time()
        service = WhisperService()
        init_time = time.time() - init_start

        vocab_count = 0
        if service.medical_hotwords:
            vocab_count = len(service.medical_hotwords.split())

        print(f"✓ Service initialized in {init_time:.3f}s")
        print(f"✓ Vocabulary loaded: {vocab_count} terms")

        # Run transcription
        trans_start = time.time()
        result = await service.transcribe(audio_data, language="ru")
        trans_time = time.time() - trans_start

        print(f"✓ Transcription completed in {trans_time:.3f}s")
        print(f"✓ Audio duration: {result['duration']:.2f}s")
        print(f"✓ Real-time factor: {trans_time / result['duration']:.2f}x")
        print(f"✓ Plain text: {result['text'][:100]}...")

        return {
            "test_name": test_name,
            "vocab_file": vocab_file if vocab_file else "None",
            "vocab_size": vocab_count,
            "init_time": init_time,
            "transcription_time": trans_time,
            "audio_duration": result["duration"],
            "real_time_factor": trans_time / result["duration"],
            "plain_text": result["text"],
        }

    finally:
        if vocab_file:
            # Restore original vocabulary file
            WhisperService.MEDICAL_VOCAB_FILE = original_vocab_file


async def main():
    """Run all vocabulary size tests."""
    audio_file = "test_doc.mp3"

    if not Path(audio_file).exists():
        print(f"Error: Audio file '{audio_file}' not found")
        return

    # Define tests
    tests = [
        ("Baseline (No Vocabulary)", None),
        ("Small Vocabulary (50 words)", "medical_vocabulary_ru_50.txt"),
        ("Medium Vocabulary (150 words)", "medical_vocabulary_ru_150.txt"),
        ("Large Vocabulary (280 words)", "medical_vocabulary_ru.txt"),
    ]

    results = []

    for test_name, vocab_file in tests:
        try:
            result = await test_vocabulary_size(audio_file, vocab_file, test_name)
            results.append(result)

            # Wait between tests to ensure clean state
            await asyncio.sleep(2)

        except Exception as e:
            print(f"\n✗ Test failed: {e}")
            import traceback
            traceback.print_exc()

    # Print summary
    print(f"\n\n{'='*60}")
    print("PERFORMANCE SUMMARY")
    print(f"{'='*60}\n")

    print(f"{'Test':<35} {'Vocab':<8} {'Trans Time':<12} {'RT Factor':<10} {'Speedup':<10}")
    print(f"{'-'*35} {'-'*8} {'-'*12} {'-'*10} {'-'*10}")

    baseline_time = None
    for result in results:
        test_name = result["test_name"]
        vocab_size = result["vocab_size"]
        trans_time = result["transcription_time"]
        rt_factor = result["real_time_factor"]

        if baseline_time is None:
            baseline_time = trans_time
            speedup = "baseline"
        else:
            speedup_factor = trans_time / baseline_time
            speedup = f"{speedup_factor:.2f}x"

        print(f"{test_name:<35} {vocab_size:<8} {trans_time:<12.2f}s {rt_factor:<10.2f}x {speedup:<10}")

    # Save detailed results to JSON
    output_file = "vocabulary_performance_results.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"\n✓ Detailed results saved to {output_file}")

    # Performance analysis
    print(f"\n{'='*60}")
    print("ANALYSIS")
    print(f"{'='*60}\n")

    if len(results) >= 2:
        baseline = results[0]
        for i in range(1, len(results)):
            test = results[i]
            overhead = test["transcription_time"] - baseline["transcription_time"]
            overhead_pct = (overhead / baseline["transcription_time"]) * 100
            time_per_word = overhead / test["vocab_size"] if test["vocab_size"] > 0 else 0

            print(f"{test['test_name']}:")
            print(f"  - Vocabulary size: {test['vocab_size']} words")
            print(f"  - Overhead: +{overhead:.2f}s ({overhead_pct:.1f}%)")
            print(f"  - Time per word: ~{time_per_word*1000:.2f}ms")
            print()


if __name__ == "__main__":
    asyncio.run(main())
