"""add_performance_indexes_manual

Revision ID: 536769940aaf
Revises: a9367592e5da
Create Date: 2025-10-19 04:38:55.051471+03:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '536769940aaf'
down_revision: Union[str, None] = 'a9367592e5da'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add performance indexes for recordings and transcripts tables."""
    # Recordings table indexes
    op.create_index(
        'idx_recordings_encounter_status',
        'recordings',
        ['encounter_id', 'status'],
        unique=False
    )
    op.create_index(
        'idx_recordings_tenant_status',
        'recordings',
        ['tenant_id', 'status', 'created_at'],
        unique=False
    )

    # Transcripts table indexes
    op.create_index(
        'idx_transcripts_recording_engine',
        'transcripts',
        ['recording_id', 'asr_engine'],
        unique=False
    )
    op.create_index(
        'idx_transcripts_corrected',
        'transcripts',
        ['is_corrected', 'corrected_at'],
        unique=False
    )


def downgrade() -> None:
    """Remove performance indexes."""
    # Drop transcripts indexes
    op.drop_index('idx_transcripts_corrected', table_name='transcripts')
    op.drop_index('idx_transcripts_recording_engine', table_name='transcripts')

    # Drop recordings indexes
    op.drop_index('idx_recordings_tenant_status', table_name='recordings')
    op.drop_index('idx_recordings_encounter_status', table_name='recordings')
