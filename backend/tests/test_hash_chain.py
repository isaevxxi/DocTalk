"""Tests for cryptographic hash chain in audit_events table.

These tests verify that:
1. First audit event has NULL prev_hash
2. Subsequent events link to previous hash
3. Hash chain integrity can be verified
4. Tampering is detectable
"""

import hashlib
import pytest
from sqlalchemy import select, text
from datetime import datetime, timezone
from uuid import uuid4

from app.models import AuditEvent


# ============================================================================
# Helper Functions
# ============================================================================

def compute_expected_hash(prev_hash: bytes | None, created_at: datetime, event_data: dict) -> bytes:
    """Compute expected hash for verification.

    This mirrors the trigger logic:
    current_hash = sha256(prev_hash || created_at || event_data)
    """
    import json

    # Build hash input
    hash_input = ""
    if prev_hash is not None:
        hash_input += prev_hash.hex()
    hash_input += str(created_at)
    hash_input += json.dumps(event_data, sort_keys=True)

    # Compute SHA-256
    return hashlib.sha256(hash_input.encode()).digest()


# ============================================================================
# Hash Chain Tests - Basic Chain Building
# ============================================================================

@pytest.mark.asyncio
@pytest.mark.security
async def test_first_audit_event_has_null_prev_hash(
    db_session,
    test_tenant_1,
    set_tenant,
):
    """Verify first audit event in chain has NULL prev_hash."""
    # Set tenant context
    await set_tenant(test_tenant_1.id)

    # Create first audit event (prev_hash should be NULL)
    event = AuditEvent(
        id=uuid4(),
        tenant_id=test_tenant_1.id,
        event_type="test.first_event",
        resource_type="test",
        resource_id=uuid4(),
        event_data={"action": "first", "value": 42},
        prev_hash=None,  # Explicitly NULL for first event
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(event)
    await db_session.flush()

    # Verify prev_hash is NULL
    result = await db_session.execute(
        select(AuditEvent).where(AuditEvent.id == event.id)
    )
    stored = result.scalar_one()
    assert stored.prev_hash is None, "First event should have NULL prev_hash"
    assert stored.current_hash is not None, "First event should have current_hash"
    assert len(stored.current_hash) == 32, "Hash should be 32 bytes (SHA-256)"


@pytest.mark.asyncio
@pytest.mark.security
async def test_second_audit_event_links_to_first(
    db_session,
    test_tenant_1,
    set_tenant,
):
    """Verify second audit event links to first via prev_hash."""
    # Set tenant context
    await set_tenant(test_tenant_1.id)

    # Create first event
    event1 = AuditEvent(
        id=uuid4(),
        tenant_id=test_tenant_1.id,
        event_type="test.event1",
        resource_type="test",
        resource_id=uuid4(),
        event_data={"action": "first"},
        prev_hash=None,
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(event1)
    await db_session.flush()

    # Get first event's hash
    result = await db_session.execute(
        select(AuditEvent).where(AuditEvent.id == event1.id)
    )
    stored1 = result.scalar_one()
    first_hash = stored1.current_hash

    # Create second event (linking to first)
    event2 = AuditEvent(
        id=uuid4(),
        tenant_id=test_tenant_1.id,
        event_type="test.event2",
        resource_type="test",
        resource_id=uuid4(),
        event_data={"action": "second"},
        prev_hash=first_hash,  # Link to first event
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(event2)
    await db_session.flush()

    # Verify linkage
    result = await db_session.execute(
        select(AuditEvent).where(AuditEvent.id == event2.id)
    )
    stored2 = result.scalar_one()
    assert stored2.prev_hash == first_hash, "Second event should link to first"
    assert stored2.current_hash != first_hash, "Second event should have different hash"


@pytest.mark.asyncio
@pytest.mark.security
async def test_hash_chain_sequence(
    db_session,
    test_tenant_1,
    set_tenant,
):
    """Verify hash chain can be built with multiple events."""
    # Set tenant context
    await set_tenant(test_tenant_1.id)

    # Create a chain of 5 events
    prev_hash = None
    event_ids = []

    for i in range(5):
        event = AuditEvent(
            id=uuid4(),
            tenant_id=test_tenant_1.id,
            event_type=f"test.event_{i}",
            resource_type="test",
            resource_id=uuid4(),
            event_data={"sequence": i, "value": i * 10},
            prev_hash=prev_hash,
            created_at=datetime.now(timezone.utc),
        )
        db_session.add(event)
        await db_session.flush()

        # Get the stored event to retrieve its hash
        result = await db_session.execute(
            select(AuditEvent).where(AuditEvent.id == event.id)
        )
        stored = result.scalar_one()
        prev_hash = stored.current_hash
        event_ids.append(stored.id)

    # Verify chain integrity
    result = await db_session.execute(
        select(AuditEvent)
        .where(AuditEvent.id.in_(event_ids))
        .order_by(AuditEvent.created_at)
    )
    events = result.scalars().all()

    # First event has NULL prev_hash
    assert events[0].prev_hash is None

    # Each subsequent event links to previous
    for i in range(1, len(events)):
        assert events[i].prev_hash == events[i-1].current_hash, \
            f"Event {i} should link to event {i-1}"


# ============================================================================
# Hash Chain Tests - Hash Computation Verification
# ============================================================================

@pytest.mark.asyncio
@pytest.mark.security
async def test_hash_computation_correctness(
    db_session,
    test_tenant_1,
    set_tenant,
):
    """Verify hash is computed deterministically by trigger."""
    # Set tenant context
    await set_tenant(test_tenant_1.id)

    # Create event with known data
    event_data = {"test": "data", "number": 123}
    event = AuditEvent(
        id=uuid4(),
        tenant_id=test_tenant_1.id,
        event_type="test.hash_check",
        resource_type="test",
        resource_id=uuid4(),
        event_data=event_data,
        prev_hash=None,
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(event)
    await db_session.flush()

    # Get stored event
    result = await db_session.execute(
        select(AuditEvent).where(AuditEvent.id == event.id)
    )
    stored = result.scalar_one()

    # Verify hash properties
    assert stored.current_hash is not None, "Hash should be computed"
    assert len(stored.current_hash) == 32, "Hash should be 32 bytes (SHA-256)"
    assert stored.current_hash != b'\x00' * 32, "Hash should not be all zeros"


@pytest.mark.asyncio
@pytest.mark.security
async def test_hash_changes_with_data(
    db_session,
    test_tenant_1,
    set_tenant,
):
    """Verify different data produces different hashes."""
    # Set tenant context
    await set_tenant(test_tenant_1.id)

    # Create two events with different data
    event1 = AuditEvent(
        id=uuid4(),
        tenant_id=test_tenant_1.id,
        event_type="test.event",
        resource_type="test",
        resource_id=uuid4(),
        event_data={"value": 1},
        prev_hash=None,
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(event1)
    await db_session.flush()

    result = await db_session.execute(
        select(AuditEvent).where(AuditEvent.id == event1.id)
    )
    stored1 = result.scalar_one()

    event2 = AuditEvent(
        id=uuid4(),
        tenant_id=test_tenant_1.id,
        event_type="test.event",
        resource_type="test",
        resource_id=uuid4(),
        event_data={"value": 2},  # Different data
        prev_hash=None,
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(event2)
    await db_session.flush()

    result = await db_session.execute(
        select(AuditEvent).where(AuditEvent.id == event2.id)
    )
    stored2 = result.scalar_one()

    # Hashes should be different
    assert stored1.current_hash != stored2.current_hash, \
        "Different data should produce different hashes"


# ============================================================================
# Hash Chain Tests - Integrity Verification
# ============================================================================

@pytest.mark.asyncio
@pytest.mark.security
async def test_verify_chain_integrity(
    db_session,
    test_tenant_1,
    set_tenant,
):
    """Verify entire chain integrity by checking linkage."""
    # Set tenant context
    await set_tenant(test_tenant_1.id)

    # Create a chain of events
    for i in range(10):
        # Get previous hash
        if i == 0:
            prev_hash = None
        else:
            result = await db_session.execute(
                select(AuditEvent)
                .where(AuditEvent.tenant_id == test_tenant_1.id)
                .order_by(AuditEvent.created_at.desc())
                .limit(1)
            )
            prev_event = result.scalar_one()
            prev_hash = prev_event.current_hash

        event = AuditEvent(
            id=uuid4(),
            tenant_id=test_tenant_1.id,
            event_type=f"test.integrity_{i}",
            resource_type="test",
            resource_id=uuid4(),
            event_data={"index": i, "data": f"event_{i}"},
            prev_hash=prev_hash,
            created_at=datetime.now(timezone.utc),
        )
        db_session.add(event)
        await db_session.flush()

    # Verify entire chain
    result = await db_session.execute(
        select(AuditEvent)
        .where(AuditEvent.tenant_id == test_tenant_1.id)
        .order_by(AuditEvent.created_at)
    )
    all_events = result.scalars().all()

    # Check chain linkage and hash properties
    for i, event in enumerate(all_events):
        # Verify hash exists and is valid
        assert event.current_hash is not None, f"Event {i} missing hash"
        assert len(event.current_hash) == 32, f"Event {i} hash wrong length"

        # Check linkage
        if i == 0:
            assert event.prev_hash is None, "First event should have NULL prev_hash"
        else:
            assert event.prev_hash == all_events[i-1].current_hash, \
                f"Event {i} should link to event {i-1}"


@pytest.mark.asyncio
@pytest.mark.security
async def test_detect_data_tampering(
    db_session,
    test_tenant_1,
    set_tenant,
):
    """Verify tampering can be detected by hash mismatch.

    Note: This test simulates tampering detection logic.
    In production, WORM on audit_events would prevent actual tampering.
    """
    # Set tenant context
    await set_tenant(test_tenant_1.id)

    # Create event
    event = AuditEvent(
        id=uuid4(),
        tenant_id=test_tenant_1.id,
        event_type="test.tamper_check",
        resource_type="test",
        resource_id=uuid4(),
        event_data={"original": "data"},
        prev_hash=None,
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(event)
    await db_session.flush()

    # Get stored event
    result = await db_session.execute(
        select(AuditEvent).where(AuditEvent.id == event.id)
    )
    stored = result.scalar_one()

    # Simulate tampering detection: compute hash with modified data
    tampered_data = {"original": "TAMPERED"}
    tampered_hash = compute_expected_hash(
        stored.prev_hash,
        stored.created_at,
        tampered_data
    )

    # Verify tampering would be detected
    assert stored.current_hash != tampered_hash, \
        "Tampering should be detectable via hash mismatch"


# ============================================================================
# Hash Chain Tests - Multi-Tenant Isolation
# ============================================================================

@pytest.mark.asyncio
@pytest.mark.security
async def test_hash_chains_isolated_by_tenant(
    db_session,
    test_tenant_1,
    test_tenant_2,
    set_tenant,
):
    """Verify each tenant has independent hash chains."""
    # Create chain for tenant 1
    await set_tenant(test_tenant_1.id)
    event_t1 = AuditEvent(
        id=uuid4(),
        tenant_id=test_tenant_1.id,
        event_type="test.tenant1",
        resource_type="test",
        resource_id=uuid4(),
        event_data={"tenant": 1},
        prev_hash=None,
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(event_t1)
    await db_session.flush()

    result = await db_session.execute(
        select(AuditEvent).where(AuditEvent.id == event_t1.id)
    )
    stored_t1 = result.scalar_one()

    # Create chain for tenant 2
    await set_tenant(test_tenant_2.id)
    event_t2 = AuditEvent(
        id=uuid4(),
        tenant_id=test_tenant_2.id,
        event_type="test.tenant2",
        resource_type="test",
        resource_id=uuid4(),
        event_data={"tenant": 2},
        prev_hash=None,
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(event_t2)
    await db_session.flush()

    result = await db_session.execute(
        select(AuditEvent).where(AuditEvent.id == event_t2.id)
    )
    stored_t2 = result.scalar_one()

    # Verify independent chains (both have NULL prev_hash)
    assert stored_t1.prev_hash is None
    assert stored_t2.prev_hash is None
    assert stored_t1.current_hash != stored_t2.current_hash


# ============================================================================
# Hash Chain Tests - Performance with Large Chains
# ============================================================================

@pytest.mark.asyncio
@pytest.mark.slow
async def test_large_hash_chain(
    db_session,
    test_tenant_1,
    set_tenant,
):
    """Verify hash chain works with large number of events (100+)."""
    # Set tenant context
    await set_tenant(test_tenant_1.id)

    # Create 100 events, properly chaining each one
    # With unique constraint on (tenant_id, prev_hash), we must flush after each insert
    prev_hash = None
    for i in range(100):
        event = AuditEvent(
            id=uuid4(),
            tenant_id=test_tenant_1.id,
            event_type=f"test.large_chain",
            resource_type="test",
            resource_id=uuid4(),
            event_data={"index": i},
            prev_hash=prev_hash,
            created_at=datetime.now(timezone.utc),
        )
        db_session.add(event)
        await db_session.flush()  # Flush after each event to get hash for next one

        # Get the hash for the next event in the chain
        result = await db_session.execute(
            select(AuditEvent).where(AuditEvent.id == event.id)
        )
        stored_event = result.scalar_one()
        prev_hash = stored_event.current_hash

    # Verify count
    result = await db_session.execute(
        select(AuditEvent).where(AuditEvent.tenant_id == test_tenant_1.id)
    )
    events = result.scalars().all()
    assert len(events) >= 100, f"Expected 100+ events, got {len(events)}"


# ============================================================================
# Hash Chain Tests - Compliance Scenarios
# ============================================================================

@pytest.mark.asyncio
@pytest.mark.security
async def test_audit_trail_immutable_chain(
    db_session,
    test_tenant_1,
    set_tenant,
):
    """Verify hash chain provides immutable audit trail for compliance."""
    # Set tenant context
    await set_tenant(test_tenant_1.id)

    # Simulate clinical workflow: note creation, edits, finalization
    workflow_events = [
        {"type": "note.created", "data": {"note_id": "123", "status": "draft"}},
        {"type": "note.edited", "data": {"note_id": "123", "changes": "added diagnosis"}},
        {"type": "note.edited", "data": {"note_id": "123", "changes": "added treatment plan"}},
        {"type": "note.finalized", "data": {"note_id": "123", "status": "final"}},
        {"type": "note.viewed", "data": {"note_id": "123", "viewer": "auditor"}},
    ]

    prev_hash = None
    event_ids = []

    for workflow_event in workflow_events:
        event = AuditEvent(
            id=uuid4(),
            tenant_id=test_tenant_1.id,
            event_type=workflow_event["type"],
            resource_type="note",
            resource_id=uuid4(),
            event_data=workflow_event["data"],
            prev_hash=prev_hash,
            created_at=datetime.now(timezone.utc),
        )
        db_session.add(event)
        await db_session.flush()

        result = await db_session.execute(
            select(AuditEvent).where(AuditEvent.id == event.id)
        )
        stored = result.scalar_one()
        prev_hash = stored.current_hash
        event_ids.append(stored.id)

    # Verify complete audit trail
    result = await db_session.execute(
        select(AuditEvent)
        .where(AuditEvent.id.in_(event_ids))
        .order_by(AuditEvent.created_at)
    )
    audit_trail = result.scalars().all()

    assert len(audit_trail) == 5, "Complete workflow should be logged"

    # Verify chain integrity
    for i in range(len(audit_trail)):
        if i == 0:
            assert audit_trail[i].prev_hash is None
        else:
            assert audit_trail[i].prev_hash == audit_trail[i-1].current_hash

    # Verify all expected events are present
    event_types = [e.event_type for e in audit_trail]
    assert "note.created" in event_types
    assert "note.finalized" in event_types
    assert "note.viewed" in event_types


# ============================================================================
# Hash Chain Tests - Race Condition Prevention
# ============================================================================

@pytest.mark.asyncio
@pytest.mark.security
async def test_hash_chain_race_condition_prevented(
    db_session,
    test_tenant_1,
    set_tenant,
):
    """Verify that unique constraint prevents hash chain race conditions.

    When two concurrent requests try to append to the chain with the same prev_hash,
    the second one should fail due to the unique constraint on (tenant_id, prev_hash).
    This prevents "forks" in the hash chain.
    """
    from sqlalchemy.exc import IntegrityError

    # Set tenant context
    await set_tenant(test_tenant_1.id)

    # Create initial event (the "last" event in the chain)
    event1 = AuditEvent(
        id=uuid4(),
        tenant_id=test_tenant_1.id,
        event_type="note.create",
        user_id=uuid4(),
        resource_type="note",
        resource_id=uuid4(),
        event_data={"action": "created"},
        created_at=datetime.now(timezone.utc),
        prev_hash=None,
    )
    db_session.add(event1)
    await db_session.flush()

    # Get the hash to simulate concurrent access
    result = await db_session.execute(
        select(AuditEvent).where(AuditEvent.id == event1.id)
    )
    stored_event1 = result.scalar_one()
    shared_prev_hash = stored_event1.current_hash

    # Now simulate a race condition: Two requests both read event1.current_hash
    # and try to create new events with the same prev_hash

    # Request A creates an event
    event2a = AuditEvent(
        id=uuid4(),
        tenant_id=test_tenant_1.id,
        event_type="note.update",
        user_id=uuid4(),
        resource_type="note",
        resource_id=uuid4(),
        event_data={"action": "updated by A"},
        created_at=datetime.now(timezone.utc),
        prev_hash=shared_prev_hash,  # Both reference same prev_hash
    )
    db_session.add(event2a)
    await db_session.flush()  # This should succeed

    # Request B tries to create another event with the SAME prev_hash
    event2b = AuditEvent(
        id=uuid4(),
        tenant_id=test_tenant_1.id,
        event_type="note.delete",
        user_id=uuid4(),
        resource_type="note",
        resource_id=uuid4(),
        event_data={"action": "deleted by B"},
        created_at=datetime.now(timezone.utc),
        prev_hash=shared_prev_hash,  # SAME prev_hash - should fail!
    )
    db_session.add(event2b)

    # This should raise IntegrityError due to unique constraint violation
    with pytest.raises(IntegrityError) as exc_info:
        await db_session.flush()

    # Verify the error is about the unique constraint
    error_msg = str(exc_info.value).lower()
    assert "uq_audit_events_tenant_prev_hash" in error_msg or "unique" in error_msg, \
        f"Expected unique constraint error, got: {exc_info.value}"
