#!/usr/bin/env python3
"""Test health check functionality."""

import asyncio

from app.services.health import HealthCheckService


async def test_health_checks():
    """Test individual health checks."""

    health_service = HealthCheckService()

    print("=" * 80)
    print("HEALTH CHECK FUNCTIONALITY TEST")
    print("=" * 80)
    print()

    # Test Whisper health check
    print("⏱️  Testing Whisper health check...")
    whisper_health = await health_service.check_whisper()
    print(f"   Status: {whisper_health.status.value}")
    print(f"   Response time: {whisper_health.response_time_ms:.2f}ms")
    if whisper_health.details:
        print(f"   Model: {whisper_health.details.get('model')}")
        print(f"   Device: {whisper_health.details.get('device')}")
    print()

    # Test Diarization health check
    print("⏱️  Testing Diarization health check...")
    diarization_health = await health_service.check_diarization()
    print(f"   Status: {diarization_health.status.value}")
    print(f"   Response time: {diarization_health.response_time_ms:.2f}ms")
    if diarization_health.details:
        print(f"   Enabled: {diarization_health.details.get('enabled')}")
        if diarization_health.details.get('enabled'):
            print(f"   Model: {diarization_health.details.get('model')}")
    print()

    print("=" * 80)
    print("✅ Health check functionality test complete!")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(test_health_checks())
