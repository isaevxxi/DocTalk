"""Pytest configuration and fixtures for DocTalk tests."""

import asyncio
from datetime import datetime, timezone
from typing import AsyncGenerator
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.config import settings
from app.models.base import Base
from app.models import Tenant, User, Patient, Encounter, Note, NoteVersion, AuditEvent


# ============================================================================
# Async Event Loop Configuration
# ============================================================================

@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


# ============================================================================
# Database Engine and Session Fixtures
# ============================================================================

@pytest_asyncio.fixture(scope="session")
async def test_engine():
    """Create test database engine."""
    # First, connect as superuser to set up test role and database
    admin_url = "postgresql+asyncpg://doktalk_user:password@localhost:5432/doktalk_test"
    admin_engine = create_async_engine(admin_url, isolation_level="AUTOCOMMIT")

    async with admin_engine.connect() as conn:
        # Create non-superuser test role (doktalk_user is superuser, so RLS won't work with it)
        # Check if role exists first
        result = await conn.execute(text("SELECT 1 FROM pg_roles WHERE rolname = 'doktalk_test_user'"))
        role_exists = result.scalar()

        if not role_exists:
            await conn.execute(text("CREATE ROLE doktalk_test_user WITH LOGIN PASSWORD 'test_pass' NOSUPERUSER"))
            print("=== Created non-superuser role: doktalk_test_user ===")
        else:
            print("=== Using existing non-superuser role: doktalk_test_user ===")

    await admin_engine.dispose()

    # Now create engine using the non-superuser role for actual testing
    test_db_url = "postgresql+asyncpg://doktalk_test_user:test_pass@localhost:5432/doktalk_test"
    engine = create_async_engine(
        test_db_url,
        echo=False,
        pool_pre_ping=True,
    )

    yield engine

    await engine.dispose()


@pytest_asyncio.fixture(scope="session")
async def setup_test_db(test_engine):
    """Create all tables in test database."""
    print("\n=== SETUP_TEST_DB: Starting database setup ===")

    # Grant necessary privileges to test user
    # We need to do this as superuser first
    admin_url = "postgresql+asyncpg://doktalk_user:password@localhost:5432/doktalk_test"
    admin_engine = create_async_engine(admin_url)

    async with admin_engine.begin() as conn:
        # Drop and recreate schema
        await conn.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
        await conn.execute(text("CREATE SCHEMA public"))
        await conn.execute(text("GRANT ALL ON SCHEMA public TO doktalk_test_user"))
        await conn.execute(text("GRANT ALL ON ALL TABLES IN SCHEMA public TO doktalk_test_user"))
        await conn.execute(text("GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO doktalk_test_user"))
        await conn.execute(text("ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO doktalk_test_user"))
        await conn.execute(text("ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO doktalk_test_user"))
        # Enable pgcrypto extension (requires superuser)
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS pgcrypto"))

    await admin_engine.dispose()

    # Now set up tables using the test user connection
    async with test_engine.begin() as conn:

        # Create enum types first (matching model definitions)
        await conn.execute(text("CREATE TYPE user_role AS ENUM ('physician', 'admin', 'staff')"))
        await conn.execute(text("CREATE TYPE patient_sex AS ENUM ('male', 'female', 'other', 'unknown')"))
        await conn.execute(text("CREATE TYPE encounter_type AS ENUM ('in_person', 'telemed', 'phone')"))
        await conn.execute(text("CREATE TYPE encounter_status AS ENUM ('scheduled', 'in_progress', 'completed', 'cancelled', 'no_show')"))
        await conn.execute(text("CREATE TYPE note_status AS ENUM ('draft', 'final', 'amended', 'archived')"))

        # Create all tables
        await conn.run_sync(Base.metadata.create_all)

        # Enable RLS on all multi-tenant tables
        tables_with_rls = ["users", "patients", "encounters", "notes", "note_versions", "audit_events"]
        for table in tables_with_rls:
            await conn.execute(text(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY"))
            # FORCE RLS so table owner (doktalk_user) is also subject to policies
            await conn.execute(text(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY"))
            # Use NULLIF to safely handle empty string - NULL = anything always returns FALSE
            await conn.execute(text(f"""
                CREATE POLICY tenant_isolation ON {table}
                FOR ALL
                USING (tenant_id = NULLIF(current_setting('app.tenant_id', TRUE), '')::UUID)
            """))
            print(f"=== RLS enabled and policy created for {table} ===")

        # Create WORM trigger on note_versions
        # Split into separate statements for asyncpg
        await conn.execute(text("""
            CREATE OR REPLACE FUNCTION prevent_note_version_modification()
            RETURNS TRIGGER AS $$
            BEGIN
                IF TG_OP = 'UPDATE' THEN
                    RAISE EXCEPTION 'Cannot UPDATE note_versions - Write-Once-Read-Many table';
                ELSIF TG_OP = 'DELETE' THEN
                    RAISE EXCEPTION 'Cannot DELETE from note_versions - Write-Once-Read-Many table';
                END IF;
                RETURN NULL;
            END;
            $$ LANGUAGE plpgsql
        """))

        await conn.execute(text("""
            CREATE TRIGGER enforce_worm_note_versions
            BEFORE UPDATE OR DELETE ON note_versions
            FOR EACH ROW
            EXECUTE FUNCTION prevent_note_version_modification()
        """))

        # Create hash chain trigger on audit_events
        # Split into separate statements for asyncpg
        await conn.execute(text("""
            CREATE OR REPLACE FUNCTION compute_audit_hash()
            RETURNS TRIGGER AS $$
            DECLARE
                hash_input TEXT;
            BEGIN
                -- Compute hash: sha256(prev_hash || created_at || event_data)
                hash_input := COALESCE(encode(NEW.prev_hash, 'hex'), '') ||
                              NEW.created_at::TEXT ||
                              NEW.event_data::TEXT;
                NEW.current_hash := digest(hash_input, 'sha256');
                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql
        """))

        await conn.execute(text("""
            CREATE TRIGGER compute_hash_chain
            BEFORE INSERT ON audit_events
            FOR EACH ROW
            EXECUTE FUNCTION compute_audit_hash()
        """))

    print("=== SETUP_TEST_DB: Database setup complete, yielding control to tests ===")
    yield
    print("=== SETUP_TEST_DB: Tests complete, cleaning up database ===")

    # Cleanup after all tests
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def db_session(test_engine, setup_test_db) -> AsyncGenerator[AsyncSession, None]:
    """Create a new database session for each test."""
    # Create session factory
    async_session = async_sessionmaker(
        test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with async_session() as session:
        # Start a nested transaction using SAVEPOINT
        transaction = await session.begin()

        yield session

        # Rollback the nested transaction after test (cleans up all data)
        await transaction.rollback()


# ============================================================================
# Tenant Context Fixture
# ============================================================================

@pytest_asyncio.fixture
async def set_tenant(db_session):
    """Helper fixture to set tenant context.

    Security Note:
    PostgreSQL's SET command does not support parameterized queries ($1, $2, etc).
    However, this is safe from SQL injection because:
    1. tenant_id parameter is type-checked as UUID by Python
    2. UUID.__str__() always returns RFC 4122 format (8-4-4-4-12 hex chars)
    3. No user input can reach this code path with non-UUID values

    In production code, the tenant_id should come from authenticated JWT claims,
    which are cryptographically verified before reaching this point.
    """
    async def _set_tenant(tenant_id: UUID):
        # Use SET (not SET LOCAL) to ensure it persists across savepoints
        tenant_id_str = str(tenant_id)  # UUID.__str__() always returns valid UUID format
        await db_session.execute(
            text(f"SET app.tenant_id = '{tenant_id_str}'")
        )
        # Flush to ensure the setting takes effect
        await db_session.flush()
    return _set_tenant


# ============================================================================
# Test Data Fixtures - Tenants
# ============================================================================

@pytest_asyncio.fixture
async def test_tenant_1(db_session) -> Tenant:
    """Create first test tenant."""
    tenant = Tenant(
        id=uuid4(),
        name="Central Clinic",
        slug="central-clinic",
        is_active=True,
        data_localization_country="RU",
        retention_years=7,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db_session.add(tenant)
    await db_session.flush()
    return tenant


@pytest_asyncio.fixture
async def test_tenant_2(db_session) -> Tenant:
    """Create second test tenant."""
    tenant = Tenant(
        id=uuid4(),
        name="Regional Hospital",
        slug="regional-hospital",
        is_active=True,
        data_localization_country="RU",
        retention_years=7,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db_session.add(tenant)
    await db_session.flush()
    return tenant


# ============================================================================
# Test Data Fixtures - Users
# ============================================================================

@pytest_asyncio.fixture
async def test_user_tenant_1(db_session, test_tenant_1) -> User:
    """Create test user in tenant 1."""
    # Set tenant context for fixture creation (type-safe, see set_tenant fixture for security notes)
    tenant_id_str = str(test_tenant_1.id)
    await db_session.execute(
        text(f"SET app.tenant_id = '{tenant_id_str}'")
    )

    user = User(
        id=uuid4(),
        tenant_id=test_tenant_1.id,
        email="doctor1@central-clinic.ru",
        full_name="Dr. Ivan Petrov",
        password_hash="$2b$12$test_hash_here_not_real_password",
        role="physician",  # Plain string to match database enum
        is_active=True,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db_session.add(user)
    await db_session.flush()

    # Clear tenant context after fixture creation (set to empty string)
    await db_session.execute(
        text("SET app.tenant_id = ''")
    )

    # Expunge from session to force re-query with new RLS context
    db_session.expunge(user)

    return user


@pytest_asyncio.fixture
async def test_user_tenant_2(db_session, test_tenant_2) -> User:
    """Create test user in tenant 2."""
    # Set tenant context for fixture creation (type-safe, see set_tenant fixture for security notes)
    tenant_id_str = str(test_tenant_2.id)
    await db_session.execute(
        text(f"SET app.tenant_id = '{tenant_id_str}'")
    )

    user = User(
        id=uuid4(),
        tenant_id=test_tenant_2.id,
        email="doctor2@regional-hospital.ru",
        full_name="Dr. Maria Ivanova",
        password_hash="$2b$12$test_hash_here_not_real_password",
        role="physician",  # Plain string to match database enum
        is_active=True,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db_session.add(user)
    await db_session.flush()

    # Clear tenant context after fixture creation (set to empty string)
    await db_session.execute(
        text("SET app.tenant_id = ''")
    )

    # Expunge from session to force re-query with new RLS context
    db_session.expunge(user)

    return user


# ============================================================================
# Test Data Fixtures - Patients
# ============================================================================

@pytest_asyncio.fixture
async def test_patient_tenant_1(db_session, test_tenant_1) -> Patient:
    """Create test patient in tenant 1."""
    # Set tenant context for fixture creation (type-safe, see set_tenant fixture for security notes)
    tenant_id_str = str(test_tenant_1.id)
    await db_session.execute(
        text(f"SET app.tenant_id = '{tenant_id_str}'")
    )

    patient = Patient(
        id=uuid4(),
        tenant_id=test_tenant_1.id,
        mrn="MRN001",
        full_name="Alexey Sokolov",
        date_of_birth=datetime(1980, 5, 15),
        sex="male",
        phone="+79161234567",
        email="alexey@example.com",
        address="Moscow, Lenina St. 10",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db_session.add(patient)
    await db_session.flush()

    # Clear tenant context after fixture creation (set to empty string)
    await db_session.execute(
        text("SET app.tenant_id = ''")
    )

    # Expunge from session to force re-query with new RLS context
    db_session.expunge(patient)

    return patient


@pytest_asyncio.fixture
async def test_patient_tenant_2(db_session, test_tenant_2) -> Patient:
    """Create test patient in tenant 2."""
    # Set tenant context for fixture creation (type-safe, see set_tenant fixture for security notes)
    tenant_id_str = str(test_tenant_2.id)
    await db_session.execute(
        text(f"SET app.tenant_id = '{tenant_id_str}'")
    )

    patient = Patient(
        id=uuid4(),
        tenant_id=test_tenant_2.id,
        mrn="MRN002",
        full_name="Elena Volkova",
        date_of_birth=datetime(1990, 3, 20),
        sex="female",
        phone="+79267654321",
        email="elena@example.com",
        address="St. Petersburg, Nevsky Ave. 50",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db_session.add(patient)
    await db_session.flush()

    # Clear tenant context after fixture creation (set to empty string)
    await db_session.execute(
        text("SET app.tenant_id = ''")
    )

    # Expunge from session to force re-query with new RLS context
    db_session.expunge(patient)

    return patient


# ============================================================================
# Test Data Fixtures - Encounters
# ============================================================================

@pytest_asyncio.fixture
async def test_encounter_tenant_1(
    db_session, test_tenant_1, test_patient_tenant_1, test_user_tenant_1
) -> Encounter:
    """Create test encounter in tenant 1."""
    # Set tenant context for fixture creation (type-safe, see set_tenant fixture for security notes)
    tenant_id_str = str(test_tenant_1.id)
    await db_session.execute(
        text(f"SET app.tenant_id = '{tenant_id_str}'")
    )

    encounter = Encounter(
        id=uuid4(),
        tenant_id=test_tenant_1.id,
        patient_id=test_patient_tenant_1.id,
        physician_id=test_user_tenant_1.id,
        encounter_type="in_person",  # Plain string to match database enum
        status="scheduled",  # Plain string to match database enum
        scheduled_at=datetime.now(timezone.utc),
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db_session.add(encounter)
    await db_session.flush()

    # Clear tenant context after fixture creation (set to empty string)
    await db_session.execute(
        text("SET app.tenant_id = ''")
    )

    # Expunge from session to force re-query with new RLS context
    db_session.expunge(encounter)

    return encounter


# ============================================================================
# Test Data Fixtures - Notes
# ============================================================================

@pytest_asyncio.fixture
async def test_note_tenant_1(
    db_session, test_tenant_1, test_encounter_tenant_1
) -> Note:
    """Create test note in tenant 1."""
    # Set tenant context for fixture creation (type-safe, see set_tenant fixture for security notes)
    tenant_id_str = str(test_tenant_1.id)
    await db_session.execute(
        text(f"SET app.tenant_id = '{tenant_id_str}'")
    )

    note = Note(
        id=uuid4(),
        tenant_id=test_tenant_1.id,
        encounter_id=test_encounter_tenant_1.id,
        content="S: Patient complains of headache\nO: BP 120/80\nA: Tension headache\nP: Rest and hydration",
        status="draft",  # Plain string to match database enum
        current_version=1,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db_session.add(note)
    await db_session.flush()

    # Clear tenant context after fixture creation (set to empty string)
    await db_session.execute(
        text("SET app.tenant_id = ''")
    )

    # Expunge from session to force re-query with new RLS context
    db_session.expunge(note)

    return note


@pytest_asyncio.fixture
async def test_note_version_tenant_1(
    db_session, test_tenant_1, test_note_tenant_1
) -> NoteVersion:
    """Create test note version in tenant 1."""
    # Set tenant context for fixture creation (type-safe, see set_tenant fixture for security notes)
    tenant_id_str = str(test_tenant_1.id)
    await db_session.execute(
        text(f"SET app.tenant_id = '{tenant_id_str}'")
    )

    note_version = NoteVersion(
        id=uuid4(),
        tenant_id=test_tenant_1.id,
        note_id=test_note_tenant_1.id,
        version=1,
        content=test_note_tenant_1.content,
        status="draft",  # Plain string to match database enum
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db_session.add(note_version)
    await db_session.flush()

    # Clear tenant context after fixture creation (set to empty string)
    await db_session.execute(
        text("SET app.tenant_id = ''")
    )

    # Expunge from session to force re-query with new RLS context
    db_session.expunge(note_version)

    return note_version
