"""Tests for Row-Level Security (RLS) policies.

These tests verify that the RLS policies correctly isolate tenant data
and prevent cross-tenant access.
"""

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import InternalError

from app.models import User, Patient, Encounter, Note, NoteVersion, AuditEvent


# ============================================================================
# RLS Tests - Users Table
# ============================================================================

@pytest.mark.asyncio
@pytest.mark.security
@pytest.mark.rls
async def test_rls_users_isolated_by_tenant(
    db_session,
    test_tenant_1,
    test_tenant_2,
    test_user_tenant_1,
    test_user_tenant_2,
    set_tenant,
):
    """Verify RLS prevents seeing other tenant's users."""
    # Set context to tenant 1
    await set_tenant(test_tenant_1.id)

    # Query users - should only see tenant 1's users
    result = await db_session.execute(select(User))
    users = result.scalars().all()

    # Assertions
    assert len(users) == 1, f"Expected 1 user, got {len(users)}"
    assert all(u.tenant_id == test_tenant_1.id for u in users), "Found user from wrong tenant"
    assert users[0].id == test_user_tenant_1.id, "Wrong user returned"
    assert not any(u.tenant_id == test_tenant_2.id for u in users), "Tenant 2 user visible"


@pytest.mark.asyncio
@pytest.mark.security
@pytest.mark.rls
async def test_rls_users_switch_tenant_context(
    db_session,
    test_tenant_1,
    test_tenant_2,
    test_user_tenant_1,
    test_user_tenant_2,
    set_tenant,
):
    """Verify switching tenant context changes visible users."""
    # First, set context to tenant 1
    await set_tenant(test_tenant_1.id)
    result = await db_session.execute(select(User))
    users_t1 = result.scalars().all()
    assert len(users_t1) == 1
    assert users_t1[0].tenant_id == test_tenant_1.id

    # Switch to tenant 2
    await set_tenant(test_tenant_2.id)
    result = await db_session.execute(select(User))
    users_t2 = result.scalars().all()
    assert len(users_t2) == 1
    assert users_t2[0].tenant_id == test_tenant_2.id

    # Verify we see different users
    assert users_t1[0].id != users_t2[0].id


# ============================================================================
# RLS Tests - Patients Table
# ============================================================================

@pytest.mark.asyncio
@pytest.mark.security
@pytest.mark.rls
async def test_rls_patients_isolated_by_tenant(
    db_session,
    test_tenant_1,
    test_tenant_2,
    test_patient_tenant_1,
    test_patient_tenant_2,
    set_tenant,
):
    """Verify RLS prevents seeing other tenant's patients."""
    # Set context to tenant 1
    await set_tenant(test_tenant_1.id)

    # Query patients - should only see tenant 1's patients
    result = await db_session.execute(select(Patient))
    patients = result.scalars().all()

    # Assertions
    assert len(patients) == 1, f"Expected 1 patient, got {len(patients)}"
    assert all(p.tenant_id == test_tenant_1.id for p in patients), "Found patient from wrong tenant"
    assert patients[0].id == test_patient_tenant_1.id, "Wrong patient returned"
    assert not any(p.tenant_id == test_tenant_2.id for p in patients), "Tenant 2 patient visible"


@pytest.mark.asyncio
@pytest.mark.security
@pytest.mark.rls
async def test_rls_patients_by_mrn(
    db_session,
    test_tenant_1,
    test_patient_tenant_1,
    set_tenant,
):
    """Verify RLS works with WHERE clause filtering."""
    # Set context to tenant 1
    await set_tenant(test_tenant_1.id)

    # Query by MRN
    result = await db_session.execute(
        select(Patient).where(Patient.mrn == "MRN001")
    )
    patient = result.scalar_one_or_none()

    # Should find the patient
    assert patient is not None, "Patient not found"
    assert patient.id == test_patient_tenant_1.id
    assert patient.mrn == "MRN001"


# ============================================================================
# RLS Tests - Cross-Tenant Access Prevention
# ============================================================================

@pytest.mark.asyncio
@pytest.mark.security
@pytest.mark.rls
async def test_rls_cross_tenant_insert_blocked(
    db_session,
    test_tenant_1,
    test_tenant_2,
    set_tenant,
):
    """Verify cannot insert records for other tenants."""
    # Set context to tenant 1
    await set_tenant(test_tenant_1.id)

    # Try to insert user for tenant 2 (should be actively blocked by RLS)
    from datetime import datetime, timezone
    from uuid import uuid4
    from sqlalchemy.exc import ProgrammingError

    malicious_user = User(
        id=uuid4(),
        tenant_id=test_tenant_2.id,  # Wrong tenant!
        email="hacker@malicious.com",
        full_name="Hacker",
        password_hash="$2b$12$hashed",
        role="physician",
        is_active=True,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db_session.add(malicious_user)

    # RLS should actively block this INSERT with InsufficientPrivilegeError
    with pytest.raises(ProgrammingError, match="row-level security policy"):
        await db_session.flush()


@pytest.mark.asyncio
@pytest.mark.security
@pytest.mark.rls
async def test_rls_cross_tenant_update_blocked(
    db_session,
    test_tenant_1,
    test_tenant_2,
    test_user_tenant_2,
    set_tenant,
):
    """Verify cannot update records from other tenants."""
    # Set context to tenant 1
    await set_tenant(test_tenant_1.id)

    # Try to update tenant 2's user (should not find it)
    result = await db_session.execute(
        select(User).where(User.id == test_user_tenant_2.id)
    )
    user = result.scalar_one_or_none()

    # Should not find the user (RLS blocks it)
    assert user is None, "Found user from wrong tenant!"


@pytest.mark.asyncio
@pytest.mark.security
@pytest.mark.rls
async def test_rls_cross_tenant_delete_blocked(
    db_session,
    test_tenant_1,
    test_tenant_2,
    test_patient_tenant_2,
    set_tenant,
):
    """Verify cannot delete records from other tenants."""
    # Set context to tenant 1
    await set_tenant(test_tenant_1.id)

    # Try to delete tenant 2's patient
    from sqlalchemy import delete
    stmt = delete(Patient).where(Patient.id == test_patient_tenant_2.id)
    result = await db_session.execute(stmt)

    # Should affect 0 rows (RLS blocks it)
    assert result.rowcount == 0, "Deleted patient from wrong tenant!"

    # Verify patient still exists in tenant 2
    await set_tenant(test_tenant_2.id)
    result = await db_session.execute(
        select(Patient).where(Patient.id == test_patient_tenant_2.id)
    )
    patient = result.scalar_one_or_none()
    assert patient is not None, "Patient was deleted!"


# ============================================================================
# RLS Tests - No Tenant Context
# ============================================================================

@pytest.mark.asyncio
@pytest.mark.security
@pytest.mark.rls
async def test_rls_without_tenant_context_returns_empty(
    db_session,
    test_user_tenant_1,
    test_patient_tenant_1,
):
    """Verify queries return empty results without tenant context."""
    # Don't set tenant context (no SET app.tenant_id)

    # DEBUG: Check what tenant_id the database sees
    result = await db_session.execute(text("SELECT current_setting('app.tenant_id', TRUE) as tenant_id"))
    tenant_id_value = result.scalar()
    print(f"\nDEBUG: current tenant_id setting = '{tenant_id_value}'")

    # DEBUG: Check if RLS is enabled
    result = await db_session.execute(text("SELECT relrowsecurity, relforcerowsecurity FROM pg_class WHERE relname = 'users'"))
    rls_status = result.fetchone()
    print(f"DEBUG: users table RLS status: relrowsecurity={rls_status[0] if rls_status else None}, relforcerowsecurity={rls_status[1] if rls_status else None}")

    # DEBUG: Check if policy exists
    result = await db_session.execute(text("SELECT COUNT(*) FROM pg_policies WHERE tablename = 'users'"))
    policy_count = result.scalar()
    print(f"DEBUG: Number of policies on users table: {policy_count}")

    # DEBUG: Check current user and if they bypass RLS
    result = await db_session.execute(text("SELECT current_user, usesuper FROM pg_user WHERE usename = current_user"))
    user_info = result.fetchone()
    print(f"DEBUG: Connected as user='{user_info[0]}', superuser={user_info[1]}")

    # Query users - should return empty
    result = await db_session.execute(select(User))
    users = result.scalars().all()
    print(f"DEBUG: Found {len(users)} users: {[u.email for u in users]}")
    assert len(users) == 0, "Users visible without tenant context!"

    # Query patients - should return empty
    result = await db_session.execute(select(Patient))
    patients = result.scalars().all()
    assert len(patients) == 0, "Patients visible without tenant context!"


@pytest.mark.asyncio
@pytest.mark.security
@pytest.mark.rls
async def test_rls_invalid_tenant_id_returns_empty(
    db_session,
    test_user_tenant_1,
    set_tenant,
):
    """Verify queries return empty with non-existent tenant ID."""
    from uuid import UUID

    # Set context to non-existent tenant
    fake_tenant_id = UUID("88888888-8888-8888-8888-888888888888")
    await set_tenant(fake_tenant_id)

    # Query users - should return empty
    result = await db_session.execute(select(User))
    users = result.scalars().all()
    assert len(users) == 0, "Users visible with invalid tenant!"


# ============================================================================
# RLS Tests - Encounters
# ============================================================================

@pytest.mark.asyncio
@pytest.mark.security
@pytest.mark.rls
async def test_rls_encounters_isolated_by_tenant(
    db_session,
    test_tenant_1,
    test_encounter_tenant_1,
    set_tenant,
):
    """Verify RLS works on encounters table."""
    # Set context to tenant 1
    await set_tenant(test_tenant_1.id)

    # Query encounters
    result = await db_session.execute(select(Encounter))
    encounters = result.scalars().all()

    # Should see only tenant 1's encounters
    assert len(encounters) == 1
    assert encounters[0].tenant_id == test_tenant_1.id
    assert encounters[0].id == test_encounter_tenant_1.id


# ============================================================================
# RLS Tests - Notes
# ============================================================================

@pytest.mark.asyncio
@pytest.mark.security
@pytest.mark.rls
async def test_rls_notes_isolated_by_tenant(
    db_session,
    test_tenant_1,
    test_note_tenant_1,
    set_tenant,
):
    """Verify RLS works on notes table."""
    # Set context to tenant 1
    await set_tenant(test_tenant_1.id)

    # Query notes
    result = await db_session.execute(select(Note))
    notes = result.scalars().all()

    # Should see only tenant 1's notes
    assert len(notes) == 1
    assert notes[0].tenant_id == test_tenant_1.id
    assert notes[0].id == test_note_tenant_1.id


# ============================================================================
# RLS Tests - Note Versions
# ============================================================================

@pytest.mark.asyncio
@pytest.mark.security
@pytest.mark.rls
async def test_rls_note_versions_isolated_by_tenant(
    db_session,
    test_tenant_1,
    test_note_version_tenant_1,
    set_tenant,
):
    """Verify RLS works on note_versions table."""
    # Set context to tenant 1
    await set_tenant(test_tenant_1.id)

    # Query note versions
    result = await db_session.execute(select(NoteVersion))
    versions = result.scalars().all()

    # Should see only tenant 1's note versions
    assert len(versions) == 1
    assert versions[0].tenant_id == test_tenant_1.id
    assert versions[0].id == test_note_version_tenant_1.id


# ============================================================================
# RLS Tests - Join Queries
# ============================================================================

@pytest.mark.asyncio
@pytest.mark.security
@pytest.mark.rls
async def test_rls_join_queries_respect_isolation(
    db_session,
    test_tenant_1,
    test_patient_tenant_1,
    test_encounter_tenant_1,
    set_tenant,
):
    """Verify RLS works with JOIN queries."""
    # Set context to tenant 1
    await set_tenant(test_tenant_1.id)

    # Query with JOIN
    result = await db_session.execute(
        select(Patient, Encounter)
        .join(Encounter, Patient.id == Encounter.patient_id)
    )
    rows = result.all()

    # Should see joined data
    assert len(rows) == 1
    patient, encounter = rows[0]
    assert patient.tenant_id == test_tenant_1.id
    assert encounter.tenant_id == test_tenant_1.id
    assert encounter.patient_id == patient.id
