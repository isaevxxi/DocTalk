"""Tests for WORM (Write-Once-Read-Many) functionality.

These tests verify that the note_versions table is immutable:
- INSERT is allowed (write-once)
- UPDATE is blocked (read-many)
- DELETE is blocked (read-many)
"""

import pytest
from sqlalchemy import select, update, delete
from sqlalchemy.exc import DBAPIError

from app.models import NoteVersion


# ============================================================================
# WORM Tests - Insert (Allowed)
# ============================================================================

@pytest.mark.asyncio
@pytest.mark.security
async def test_note_version_insert_works(
    db_session,
    test_tenant_1,
    test_note_tenant_1,
    set_tenant,
):
    """Verify INSERT into note_versions is allowed (write-once)."""
    from datetime import datetime, timezone
    from uuid import uuid4

    # Set tenant context
    await set_tenant(test_tenant_1.id)

    # Create a new note version (should work)
    new_version = NoteVersion(
        id=uuid4(),
        tenant_id=test_tenant_1.id,
        note_id=test_note_tenant_1.id,
        version=2,
        content="Updated SOAP note content",
        status="final",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db_session.add(new_version)
    await db_session.flush()

    # Verify it was inserted
    result = await db_session.execute(
        select(NoteVersion).where(NoteVersion.version == 2)
    )
    inserted = result.scalar_one_or_none()
    assert inserted is not None, "Insert failed"
    assert inserted.version == 2
    assert inserted.content == "Updated SOAP note content"


@pytest.mark.asyncio
@pytest.mark.security
async def test_note_version_multiple_inserts_work(
    db_session,
    test_tenant_1,
    test_note_tenant_1,
    set_tenant,
):
    """Verify multiple INSERTs work (write-once for each record)."""
    from datetime import datetime, timezone
    from uuid import uuid4

    # Set tenant context
    await set_tenant(test_tenant_1.id)

    # Create multiple versions
    versions_to_create = [
        NoteVersion(
            id=uuid4(),
            tenant_id=test_tenant_1.id,
            note_id=test_note_tenant_1.id,
            version=i,
            content=f"Version {i} content",
            status="draft" if i < 5 else "final",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        for i in range(2, 6)  # Create versions 2, 3, 4, 5
    ]

    for version in versions_to_create:
        db_session.add(version)

    await db_session.flush()

    # Verify all were inserted
    result = await db_session.execute(
        select(NoteVersion)
        .where(NoteVersion.note_id == test_note_tenant_1.id)
        .order_by(NoteVersion.version)
    )
    all_versions = result.scalars().all()

    # Should have original (v1) + 4 new versions = 5 total
    assert len(all_versions) >= 4, f"Expected at least 4 versions, got {len(all_versions)}"


# ============================================================================
# WORM Tests - Update (Blocked)
# ============================================================================

@pytest.mark.asyncio
@pytest.mark.security
async def test_note_version_update_blocked(
    db_session,
    test_tenant_1,
    test_note_version_tenant_1,
    set_tenant,
):
    """Verify UPDATE on note_versions is blocked by WORM trigger."""
    # Set tenant context
    await set_tenant(test_tenant_1.id)

    # Try to update the note version (should fail)
    with pytest.raises(DBAPIError) as exc_info:
        stmt = (
            update(NoteVersion)
            .where(NoteVersion.id == test_note_version_tenant_1.id)
            .values(content="HACKED - This should not work")
        )
        await db_session.execute(stmt)
        await db_session.flush()

    # Verify error message mentions WORM
    error_msg = str(exc_info.value).lower()
    assert "cannot update" in error_msg or "write-once" in error_msg or "worm" in error_msg, \
        f"Expected WORM error, got: {exc_info.value}"


@pytest.mark.asyncio
@pytest.mark.security
async def test_note_version_orm_update_blocked(
    db_session,
    test_tenant_1,
    test_note_version_tenant_1,
    set_tenant,
):
    """Verify ORM-style UPDATE is blocked by WORM trigger."""
    # Set tenant context
    await set_tenant(test_tenant_1.id)

    # Get the note version
    result = await db_session.execute(
        select(NoteVersion).where(NoteVersion.id == test_note_version_tenant_1.id)
    )
    version = result.scalar_one()

    # Try to modify it (should fail on flush)
    version.content = "HACKED - This should not work"

    with pytest.raises(DBAPIError) as exc_info:
        await db_session.flush()

    # Verify error message
    error_msg = str(exc_info.value).lower()
    assert "cannot update" in error_msg or "write-once" in error_msg or "worm" in error_msg


@pytest.mark.asyncio
@pytest.mark.security
async def test_note_version_status_change_blocked(
    db_session,
    test_tenant_1,
    test_note_version_tenant_1,
    set_tenant,
):
    """Verify even status changes are blocked (full immutability)."""
    # Set tenant context
    await set_tenant(test_tenant_1.id)

    # Try to change status from draft to final
    with pytest.raises(DBAPIError):
        stmt = (
            update(NoteVersion)
            .where(NoteVersion.id == test_note_version_tenant_1.id)
            .values(status="final")
        )
        await db_session.execute(stmt)
        await db_session.flush()


# ============================================================================
# WORM Tests - Delete (Blocked)
# ============================================================================

@pytest.mark.asyncio
@pytest.mark.security
async def test_note_version_delete_blocked(
    db_session,
    test_tenant_1,
    test_note_version_tenant_1,
    set_tenant,
):
    """Verify DELETE from note_versions is blocked by WORM trigger."""
    # Set tenant context
    await set_tenant(test_tenant_1.id)

    # Try to delete the note version (should fail)
    with pytest.raises(DBAPIError) as exc_info:
        stmt = delete(NoteVersion).where(NoteVersion.id == test_note_version_tenant_1.id)
        await db_session.execute(stmt)
        await db_session.flush()

    # Verify error message mentions WORM
    error_msg = str(exc_info.value).lower()
    assert "cannot delete" in error_msg or "write-once" in error_msg or "worm" in error_msg, \
        f"Expected WORM error, got: {exc_info.value}"


@pytest.mark.asyncio
@pytest.mark.security
async def test_note_version_orm_delete_blocked(
    db_session,
    test_tenant_1,
    test_note_version_tenant_1,
    set_tenant,
):
    """Verify ORM-style DELETE is blocked by WORM trigger."""
    # Set tenant context
    await set_tenant(test_tenant_1.id)

    # Get the note version
    result = await db_session.execute(
        select(NoteVersion).where(NoteVersion.id == test_note_version_tenant_1.id)
    )
    version = result.scalar_one()

    # Try to delete it (should fail on flush)
    await db_session.delete(version)

    with pytest.raises(DBAPIError) as exc_info:
        await db_session.flush()

    # Verify error message
    error_msg = str(exc_info.value).lower()
    assert "cannot delete" in error_msg or "write-once" in error_msg or "worm" in error_msg


@pytest.mark.asyncio
@pytest.mark.security
async def test_note_version_bulk_delete_blocked(
    db_session,
    test_tenant_1,
    test_note_tenant_1,
    test_note_version_tenant_1,
    set_tenant,
):
    """Verify bulk DELETE is blocked by WORM trigger."""
    # Set tenant context
    await set_tenant(test_tenant_1.id)

    # Verify we have at least one version to delete
    result = await db_session.execute(
        select(NoteVersion).where(NoteVersion.note_id == test_note_tenant_1.id)
    )
    versions = result.scalars().all()
    assert len(versions) > 0, "No versions exist to test bulk delete"

    # Try to delete all versions for a note (should fail)
    with pytest.raises(DBAPIError) as exc_info:
        stmt = delete(NoteVersion).where(NoteVersion.note_id == test_note_tenant_1.id)
        await db_session.execute(stmt)
        await db_session.flush()

    # Verify error message
    error_msg = str(exc_info.value).lower()
    assert "cannot delete" in error_msg or "write-once" in error_msg, "Wrong error type"


# ============================================================================
# WORM Tests - Verification After Failed Operations
# ============================================================================

@pytest.mark.asyncio
@pytest.mark.security
async def test_note_version_unchanged_after_failed_update(
    db_session,
    test_tenant_1,
    test_note_version_tenant_1,
    set_tenant,
):
    """Verify note version remains unchanged after failed UPDATE attempt."""
    # Set tenant context
    await set_tenant(test_tenant_1.id)

    # Get original content
    result = await db_session.execute(
        select(NoteVersion).where(NoteVersion.id == test_note_version_tenant_1.id)
    )
    original = result.scalar_one()
    original_content = original.content

    # Try to update (should fail and trigger rollback automatically)
    with pytest.raises(DBAPIError) as exc_info:
        stmt = (
            update(NoteVersion)
            .where(NoteVersion.id == test_note_version_tenant_1.id)
            .values(content="HACKED")
        )
        await db_session.execute(stmt)
        await db_session.flush()

    # Verify error message
    error_msg = str(exc_info.value).lower()
    assert "cannot update" in error_msg or "write-once" in error_msg, "Wrong error type"


@pytest.mark.asyncio
@pytest.mark.security
async def test_note_version_exists_after_failed_delete(
    db_session,
    test_tenant_1,
    test_note_version_tenant_1,
    set_tenant,
):
    """Verify note version still exists after failed DELETE attempt."""
    # Set tenant context
    await set_tenant(test_tenant_1.id)

    # Try to delete (should fail and trigger rollback automatically)
    with pytest.raises(DBAPIError) as exc_info:
        stmt = delete(NoteVersion).where(NoteVersion.id == test_note_version_tenant_1.id)
        await db_session.execute(stmt)
        await db_session.flush()

    # Verify error message
    error_msg = str(exc_info.value).lower()
    assert "cannot delete" in error_msg or "write-once" in error_msg, "Wrong error type"


# ============================================================================
# WORM Tests - Compliance Verification
# ============================================================================

@pytest.mark.asyncio
@pytest.mark.security
async def test_worm_compliance_audit_trail(
    db_session,
    test_tenant_1,
    test_note_tenant_1,
    set_tenant,
):
    """Verify WORM ensures complete audit trail (no modifications)."""
    from datetime import datetime, timezone
    from uuid import uuid4

    # Set tenant context
    await set_tenant(test_tenant_1.id)

    # Create a sequence of note versions
    versions = []
    for i in range(1, 4):
        version = NoteVersion(
            id=uuid4(),
            tenant_id=test_tenant_1.id,
            note_id=test_note_tenant_1.id,
            version=i + 10,  # Use high version numbers to avoid conflicts
            content=f"Compliance test version {i}",
            status="draft" if i < 3 else "final",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        db_session.add(version)
        versions.append(version)

    await db_session.flush()

    # Verify all versions exist
    result = await db_session.execute(
        select(NoteVersion)
        .where(NoteVersion.note_id == test_note_tenant_1.id)
        .where(NoteVersion.version >= 11)
        .order_by(NoteVersion.version)
    )
    stored_versions = result.scalars().all()
    assert len(stored_versions) == 3, "Not all versions stored"

    # Try to modify the first version (should fail)
    # We only test one modification attempt since each DBAPIError
    # would mark the transaction for rollback
    with pytest.raises(DBAPIError) as exc_info:
        stmt = (
            update(NoteVersion)
            .where(NoteVersion.id == versions[0].id)
            .values(content="TAMPERED")
        )
        await db_session.execute(stmt)
        await db_session.flush()

    # Verify error message
    error_msg = str(exc_info.value).lower()
    assert "cannot update" in error_msg or "write-once" in error_msg, "Wrong error type"
