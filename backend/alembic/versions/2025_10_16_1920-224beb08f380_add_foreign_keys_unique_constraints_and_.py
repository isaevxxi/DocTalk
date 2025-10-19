"""Add foreign keys, unique constraints, and indexes

Revision ID: 224beb08f380
Revises: 57ea3f761083
Create Date: 2025-10-16 19:20:44.123456+03:00

This migration adds:
1. Foreign key constraints to tenants table (data integrity)
2. Unique constraints (prevent duplicates)
3. Performance indexes (optimize queries)
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '224beb08f380'
down_revision: Union[str, None] = '57ea3f761083'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add foreign keys, unique constraints, and indexes."""

    # =========================================================================
    # 1. ADD FOREIGN KEY CONSTRAINTS TO TENANTS
    # =========================================================================

    # Users -> Tenants
    op.create_foreign_key(
        'fk_users_tenant_id',
        'users', 'tenants',
        ['tenant_id'], ['id'],
        ondelete='CASCADE'
    )

    # Patients -> Tenants
    op.create_foreign_key(
        'fk_patients_tenant_id',
        'patients', 'tenants',
        ['tenant_id'], ['id'],
        ondelete='CASCADE'
    )

    # Encounters -> Tenants
    op.create_foreign_key(
        'fk_encounters_tenant_id',
        'encounters', 'tenants',
        ['tenant_id'], ['id'],
        ondelete='CASCADE'
    )

    # Notes -> Tenants
    op.create_foreign_key(
        'fk_notes_tenant_id',
        'notes', 'tenants',
        ['tenant_id'], ['id'],
        ondelete='CASCADE'
    )

    # Note Versions -> Tenants
    op.create_foreign_key(
        'fk_note_versions_tenant_id',
        'note_versions', 'tenants',
        ['tenant_id'], ['id'],
        ondelete='CASCADE'
    )

    # Audit Events -> Tenants
    op.create_foreign_key(
        'fk_audit_events_tenant_id',
        'audit_events', 'tenants',
        ['tenant_id'], ['id'],
        ondelete='CASCADE'
    )

    # =========================================================================
    # 2. ADD UNIQUE CONSTRAINTS
    # =========================================================================

    # Users: email must be unique per tenant
    op.create_unique_constraint(
        'uq_users_tenant_email',
        'users',
        ['tenant_id', 'email']
    )

    # Patients: MRN must be unique per tenant (if present)
    op.create_index(
        'uq_patients_tenant_mrn',
        'patients',
        ['tenant_id', 'mrn'],
        unique=True,
        postgresql_where=sa.text('mrn IS NOT NULL')
    )

    # Note Versions: version must be unique per note
    op.create_unique_constraint(
        'uq_note_versions_note_version',
        'note_versions',
        ['note_id', 'version']
    )

    # =========================================================================
    # 3. ADD PERFORMANCE INDEXES
    # =========================================================================

    # Users: Optimize login queries (tenant + email)
    # Already covered by unique constraint above

    # Patients: Optimize patient lookup by MRN
    # Already covered by unique index above

    # Encounters: Optimize patient history queries
    op.create_index(
        'ix_encounters_patient_status',
        'encounters',
        ['patient_id', 'status']
    )

    # Encounters: Optimize scheduling queries
    op.create_index(
        'ix_encounters_scheduled_at',
        'encounters',
        ['scheduled_at']
    )

    # Notes: Optimize encounter notes lookup
    op.create_index(
        'ix_notes_encounter_status',
        'notes',
        ['encounter_id', 'status']
    )

    # Audit Events: Optimize audit trail queries
    op.create_index(
        'ix_audit_events_created_at',
        'audit_events',
        ['created_at']
    )


def downgrade() -> None:
    """Remove foreign keys, unique constraints, and indexes."""

    # =========================================================================
    # 1. DROP PERFORMANCE INDEXES
    # =========================================================================
    op.drop_index('ix_audit_events_created_at', table_name='audit_events')
    op.drop_index('ix_notes_encounter_status', table_name='notes')
    op.drop_index('ix_encounters_scheduled_at', table_name='encounters')
    op.drop_index('ix_encounters_patient_status', table_name='encounters')

    # =========================================================================
    # 2. DROP UNIQUE CONSTRAINTS
    # =========================================================================
    op.drop_constraint('uq_note_versions_note_version', 'note_versions', type_='unique')
    op.drop_index('uq_patients_tenant_mrn', table_name='patients')
    op.drop_constraint('uq_users_tenant_email', 'users', type_='unique')

    # =========================================================================
    # 3. DROP FOREIGN KEY CONSTRAINTS
    # =========================================================================
    op.drop_constraint('fk_audit_events_tenant_id', 'audit_events', type_='foreignkey')
    op.drop_constraint('fk_note_versions_tenant_id', 'note_versions', type_='foreignkey')
    op.drop_constraint('fk_notes_tenant_id', 'notes', type_='foreignkey')
    op.drop_constraint('fk_encounters_tenant_id', 'encounters', type_='foreignkey')
    op.drop_constraint('fk_patients_tenant_id', 'patients', type_='foreignkey')
    op.drop_constraint('fk_users_tenant_id', 'users', type_='foreignkey')
