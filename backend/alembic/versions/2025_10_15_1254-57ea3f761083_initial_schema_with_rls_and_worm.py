"""Initial schema with RLS and WORM

Revision ID: 57ea3f761083
Revises:
Create Date: 2025-10-15 12:54:14.490974+03:00

This migration creates:
1. All core tables (tenants, users, patients, encounters, notes, note_versions, audit_events)
2. Row-Level Security (RLS) policies for tenant isolation
3. WORM (Write-Once-Read-Many) trigger for note_versions
4. Hash chain trigger for audit_events
5. API views with SECURITY INVOKER for controlled access

Compliance: 152-FZ (data protection), 323-FZ (medical records), Order 965n (telemedicine)
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '57ea3f761083'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade database schema."""

    # =========================================================================
    # 1. CREATE ENUMS
    # =========================================================================

    # Create enums using raw SQL to avoid SQLAlchemy caching issues
    op.execute("CREATE TYPE user_role AS ENUM ('physician', 'admin', 'staff')")
    op.execute("CREATE TYPE patient_sex AS ENUM ('male', 'female', 'other', 'unknown')")
    op.execute("CREATE TYPE encounter_type AS ENUM ('in_person', 'telemed', 'phone')")
    op.execute("CREATE TYPE encounter_status AS ENUM ('scheduled', 'in_progress', 'completed', 'cancelled', 'no_show')")
    op.execute("CREATE TYPE note_status AS ENUM ('draft', 'final', 'amended', 'archived')")

    # Define enum objects for use in table creation (with create_type=False to avoid re-creation)
    user_role_enum = postgresql.ENUM('physician', 'admin', 'staff', name='user_role', create_type=False)
    patient_sex_enum = postgresql.ENUM('male', 'female', 'other', 'unknown', name='patient_sex', create_type=False)
    encounter_type_enum = postgresql.ENUM('in_person', 'telemed', 'phone', name='encounter_type', create_type=False)
    encounter_status_enum = postgresql.ENUM('scheduled', 'in_progress', 'completed', 'cancelled', 'no_show', name='encounter_status', create_type=False)
    note_status_enum = postgresql.ENUM('draft', 'final', 'amended', 'archived', name='note_status', create_type=False)

    # =========================================================================
    # 2. CREATE TABLES
    # =========================================================================

    # Tenants (no tenant_id since it IS the tenant)
    op.create_table(
        'tenants',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('name', sa.String(255), nullable=False, comment='Organization name'),
        sa.Column('slug', sa.String(100), nullable=False, unique=True, comment='URL-safe identifier'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true', comment='Whether tenant is active'),
        sa.Column('data_localization_country', sa.String(2), nullable=False, server_default='RU', comment='Data localization country code'),
        sa.Column('retention_years', sa.Integer(), nullable=False, server_default='7', comment='Data retention period (years)'),
        sa.Column('contact_email', sa.String(255), nullable=True, comment='Primary contact email'),
        sa.Column('contact_phone', sa.String(50), nullable=True, comment='Primary contact phone'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('updated_by', postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_index('ix_tenants_slug', 'tenants', ['slug'])

    # Users
    op.create_table(
        'users',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False, comment='Tenant ID for RLS isolation'),
        sa.Column('email', sa.String(255), nullable=False, comment='Email address (used for login)'),
        sa.Column('password_hash', sa.String(255), nullable=False, comment='Bcrypt password hash'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('full_name', sa.String(255), nullable=False),
        sa.Column('role', user_role_enum, nullable=False, server_default='physician', comment='User role for RBAC'),
        sa.Column('phone', sa.String(50), nullable=True),
        sa.Column('medical_license_number', sa.String(100), nullable=True, comment='Medical license number (323-FZ requirement)'),
        sa.Column('specialty', sa.String(100), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('updated_by', postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_index('ix_users_tenant_id', 'users', ['tenant_id'])
    op.create_index('ix_users_email', 'users', ['email'])

    # Patients
    op.create_table(
        'patients',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('full_name', sa.String(255), nullable=False, comment='Patient full name (PII)'),
        sa.Column('date_of_birth', sa.Date(), nullable=False, comment='Patient date of birth (PII)'),
        sa.Column('sex', patient_sex_enum, nullable=False, server_default='unknown'),
        sa.Column('mrn', sa.String(100), nullable=True, comment='Medical Record Number (external system ID)'),
        sa.Column('phone', sa.String(50), nullable=True, comment='Primary contact phone (PII)'),
        sa.Column('email', sa.String(255), nullable=True, comment='Contact email (PII)'),
        sa.Column('address', sa.Text(), nullable=True, comment='Full address (PII)'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('notes', sa.Text(), nullable=True, comment='Administrative notes'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('updated_by', postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_index('ix_patients_tenant_id', 'patients', ['tenant_id'])
    op.create_index('ix_patients_mrn', 'patients', ['mrn'])

    # Encounters
    op.create_table(
        'encounters',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('patient_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('physician_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('encounter_type', encounter_type_enum, nullable=False, server_default='in_person'),
        sa.Column('status', encounter_status_enum, nullable=False, server_default='scheduled'),
        sa.Column('scheduled_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('chief_complaint', sa.String(500), nullable=True),
        sa.Column('diagnosis', sa.Text(), nullable=True),
        sa.Column('consent_recorded', sa.Boolean(), nullable=False, server_default='false', comment='965n requirement'),
        sa.Column('recording_path', sa.String(500), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('updated_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(['patient_id'], ['patients.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['physician_id'], ['users.id'], ondelete='RESTRICT'),
    )
    op.create_index('ix_encounters_tenant_id', 'encounters', ['tenant_id'])
    op.create_index('ix_encounters_patient_id', 'encounters', ['patient_id'])
    op.create_index('ix_encounters_physician_id', 'encounters', ['physician_id'])

    # Notes
    op.create_table(
        'notes',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('encounter_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('content', sa.Text(), nullable=False, comment='SOAP note content'),
        sa.Column('status', note_status_enum, nullable=False, server_default='draft'),
        sa.Column('current_version', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('finalized_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('finalized_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('amendment_reason', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('updated_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(['encounter_id'], ['encounters.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_notes_tenant_id', 'notes', ['tenant_id'])
    op.create_index('ix_notes_encounter_id', 'notes', ['encounter_id'])

    # Note Versions (WORM table)
    op.create_table(
        'note_versions',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('note_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('status', note_status_enum, nullable=False),
        sa.Column('change_summary', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('updated_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(['note_id'], ['notes.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_note_versions_tenant_id', 'note_versions', ['tenant_id'])
    op.create_index('ix_note_versions_note_id', 'note_versions', ['note_id'])

    # Audit Events (with hash chain)
    op.create_table(
        'audit_events',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('event_type', sa.String(100), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('resource_type', sa.String(100), nullable=False),
        sa.Column('resource_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('event_data', postgresql.JSONB(), nullable=False, server_default='{}'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('prev_hash', sa.LargeBinary(32), nullable=True, comment='Hash of previous audit event'),
        sa.Column('current_hash', sa.LargeBinary(32), nullable=False, comment='SHA-256 hash'),
        sa.Column('ip_address', sa.String(45), nullable=True),
        sa.Column('user_agent', sa.String(500), nullable=True),
    )
    op.create_index('ix_audit_events_tenant_id', 'audit_events', ['tenant_id'])
    op.create_index('ix_audit_events_event_type', 'audit_events', ['event_type'])
    op.create_index('ix_audit_events_user_id', 'audit_events', ['user_id'])
    op.create_index('ix_audit_events_resource_id', 'audit_events', ['resource_id'])
    op.create_index('ix_audit_events_tenant_created_at', 'audit_events', ['tenant_id', 'created_at'])
    op.create_index('ix_audit_events_user_created_at', 'audit_events', ['user_id', 'created_at'])
    op.create_index('ix_audit_events_resource', 'audit_events', ['resource_type', 'resource_id'])

    # =========================================================================
    # 3. ENABLE ROW-LEVEL SECURITY (RLS)
    # =========================================================================

    op.execute('ALTER TABLE users ENABLE ROW LEVEL SECURITY')
    op.execute('ALTER TABLE patients ENABLE ROW LEVEL SECURITY')
    op.execute('ALTER TABLE encounters ENABLE ROW LEVEL SECURITY')
    op.execute('ALTER TABLE notes ENABLE ROW LEVEL SECURITY')
    op.execute('ALTER TABLE note_versions ENABLE ROW LEVEL SECURITY')
    op.execute('ALTER TABLE audit_events ENABLE ROW LEVEL SECURITY')

    # =========================================================================
    # 4. CREATE RLS POLICIES
    # =========================================================================

    # Users RLS policies
    op.execute("""
        CREATE POLICY users_tenant_isolation ON users
        USING (tenant_id = current_setting('app.tenant_id')::UUID)
        WITH CHECK (tenant_id = current_setting('app.tenant_id')::UUID)
    """)

    # Patients RLS policies
    op.execute("""
        CREATE POLICY patients_tenant_isolation ON patients
        USING (tenant_id = current_setting('app.tenant_id')::UUID)
        WITH CHECK (tenant_id = current_setting('app.tenant_id')::UUID)
    """)

    # Encounters RLS policies
    op.execute("""
        CREATE POLICY encounters_tenant_isolation ON encounters
        USING (tenant_id = current_setting('app.tenant_id')::UUID)
        WITH CHECK (tenant_id = current_setting('app.tenant_id')::UUID)
    """)

    # Notes RLS policies
    op.execute("""
        CREATE POLICY notes_tenant_isolation ON notes
        USING (tenant_id = current_setting('app.tenant_id')::UUID)
        WITH CHECK (tenant_id = current_setting('app.tenant_id')::UUID)
    """)

    # Note Versions RLS policies
    op.execute("""
        CREATE POLICY note_versions_tenant_isolation ON note_versions
        USING (tenant_id = current_setting('app.tenant_id')::UUID)
        WITH CHECK (tenant_id = current_setting('app.tenant_id')::UUID)
    """)

    # Audit Events RLS policies
    op.execute("""
        CREATE POLICY audit_events_tenant_isolation ON audit_events
        USING (tenant_id = current_setting('app.tenant_id')::UUID)
        WITH CHECK (tenant_id = current_setting('app.tenant_id')::UUID)
    """)

    # =========================================================================
    # 5. CREATE WORM TRIGGER FOR NOTE_VERSIONS
    # =========================================================================

    op.execute("""
        CREATE OR REPLACE FUNCTION prevent_note_version_modification()
        RETURNS TRIGGER AS $$
        BEGIN
            -- Allow INSERT
            IF (TG_OP = 'INSERT') THEN
                RETURN NEW;
            END IF;

            -- Block UPDATE
            IF (TG_OP = 'UPDATE') THEN
                RAISE EXCEPTION 'UPDATE not allowed on note_versions (WORM table)';
            END IF;

            -- Block DELETE
            IF (TG_OP = 'DELETE') THEN
                RAISE EXCEPTION 'DELETE not allowed on note_versions (WORM table)';
            END IF;

            RETURN NULL;
        END;
        $$ LANGUAGE plpgsql;
    """)

    op.execute("""
        CREATE TRIGGER note_versions_worm_protection
        BEFORE UPDATE OR DELETE ON note_versions
        FOR EACH ROW
        EXECUTE FUNCTION prevent_note_version_modification();
    """)

    # =========================================================================
    # 6. CREATE HASH CHAIN TRIGGER FOR AUDIT_EVENTS
    # =========================================================================

    op.execute("""
        CREATE OR REPLACE FUNCTION compute_audit_event_hash()
        RETURNS TRIGGER AS $$
        DECLARE
            prev_event_hash BYTEA;
            hash_input TEXT;
        BEGIN
            -- Get the hash of the previous event for this tenant
            SELECT current_hash INTO prev_event_hash
            FROM audit_events
            WHERE tenant_id = NEW.tenant_id
            ORDER BY created_at DESC, id DESC
            LIMIT 1;

            -- Store prev_hash (NULL for first event)
            NEW.prev_hash := prev_event_hash;

            -- Compute hash: sha256(prev_hash || created_at || event_data)
            hash_input := COALESCE(encode(prev_event_hash, 'hex'), '') ||
                         NEW.created_at::TEXT ||
                         NEW.event_data::TEXT;

            NEW.current_hash := digest(hash_input, 'sha256');

            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)

    op.execute("""
        CREATE TRIGGER audit_events_hash_chain
        BEFORE INSERT ON audit_events
        FOR EACH ROW
        EXECUTE FUNCTION compute_audit_event_hash();
    """)

    # =========================================================================
    # 7. CREATE API VIEWS WITH SECURITY INVOKER
    # =========================================================================

    # API view for users
    op.execute("""
        CREATE VIEW api_users
        WITH (security_invoker=true) AS
        SELECT
            id, tenant_id, email, full_name, role, phone,
            medical_license_number, specialty, is_active,
            created_at, updated_at
        FROM users;
    """)

    # API view for patients
    op.execute("""
        CREATE VIEW api_patients
        WITH (security_invoker=true) AS
        SELECT
            id, tenant_id, full_name, date_of_birth, sex, mrn,
            phone, email, is_active, created_at, updated_at
        FROM patients;
    """)

    # API view for encounters
    op.execute("""
        CREATE VIEW api_encounters
        WITH (security_invoker=true) AS
        SELECT
            id, tenant_id, patient_id, physician_id, encounter_type,
            status, scheduled_at, started_at, completed_at,
            chief_complaint, diagnosis, consent_recorded,
            created_at, updated_at
        FROM encounters;
    """)

    # API view for notes
    op.execute("""
        CREATE VIEW api_notes
        WITH (security_invoker=true) AS
        SELECT
            id, tenant_id, encounter_id, content, status,
            current_version, finalized_at, finalized_by,
            created_at, updated_at
        FROM notes;
    """)


def downgrade() -> None:
    """Downgrade database schema."""

    # =========================================================================
    # 1. DROP API VIEWS
    # =========================================================================
    op.execute('DROP VIEW IF EXISTS api_notes')
    op.execute('DROP VIEW IF EXISTS api_encounters')
    op.execute('DROP VIEW IF EXISTS api_patients')
    op.execute('DROP VIEW IF EXISTS api_users')

    # =========================================================================
    # 2. DROP TRIGGERS AND FUNCTIONS
    # =========================================================================
    op.execute('DROP TRIGGER IF EXISTS audit_events_hash_chain ON audit_events')
    op.execute('DROP FUNCTION IF EXISTS compute_audit_event_hash()')
    op.execute('DROP TRIGGER IF EXISTS note_versions_worm_protection ON note_versions')
    op.execute('DROP FUNCTION IF EXISTS prevent_note_version_modification()')

    # =========================================================================
    # 3. DROP RLS POLICIES
    # =========================================================================
    op.execute('DROP POLICY IF EXISTS audit_events_tenant_isolation ON audit_events')
    op.execute('DROP POLICY IF EXISTS note_versions_tenant_isolation ON note_versions')
    op.execute('DROP POLICY IF EXISTS notes_tenant_isolation ON notes')
    op.execute('DROP POLICY IF EXISTS encounters_tenant_isolation ON encounters')
    op.execute('DROP POLICY IF EXISTS patients_tenant_isolation ON patients')
    op.execute('DROP POLICY IF EXISTS users_tenant_isolation ON users')

    # =========================================================================
    # 4. DISABLE ROW-LEVEL SECURITY
    # =========================================================================
    op.execute('ALTER TABLE audit_events DISABLE ROW LEVEL SECURITY')
    op.execute('ALTER TABLE note_versions DISABLE ROW LEVEL SECURITY')
    op.execute('ALTER TABLE notes DISABLE ROW LEVEL SECURITY')
    op.execute('ALTER TABLE encounters DISABLE ROW LEVEL SECURITY')
    op.execute('ALTER TABLE patients DISABLE ROW LEVEL SECURITY')
    op.execute('ALTER TABLE users DISABLE ROW LEVEL SECURITY')

    # =========================================================================
    # 5. DROP TABLES
    # =========================================================================
    op.drop_table('audit_events')
    op.drop_table('note_versions')
    op.drop_table('notes')
    op.drop_table('encounters')
    op.drop_table('patients')
    op.drop_table('users')
    op.drop_table('tenants')

    # =========================================================================
    # 6. DROP ENUMS
    # =========================================================================
    op.execute('DROP TYPE IF EXISTS note_status')
    op.execute('DROP TYPE IF EXISTS encounter_status')
    op.execute('DROP TYPE IF EXISTS encounter_type')
    op.execute('DROP TYPE IF EXISTS patient_sex')
    op.execute('DROP TYPE IF EXISTS user_role')
