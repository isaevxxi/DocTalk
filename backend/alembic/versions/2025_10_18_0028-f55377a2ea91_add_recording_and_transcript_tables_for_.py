"""Add Recording and Transcript tables for audio pipeline

Revision ID: f55377a2ea91
Revises: 3da916c98460
Create Date: 2025-10-18 00:28:56.365311+03:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'f55377a2ea91'
down_revision: Union[str, None] = '3da916c98460'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade database schema."""
    # Create recording_status enum
    op.execute("CREATE TYPE recording_status AS ENUM ('uploading', 'pending_transcription', 'processing', 'completed', 'failed')")

    # Create transcript_status enum
    op.execute("CREATE TYPE transcript_status AS ENUM ('processing', 'completed', 'failed')")

    # Define enum objects for use in table creation (with create_type=False to avoid re-creation)
    recording_status_enum = postgresql.ENUM('uploading', 'pending_transcription', 'processing', 'completed', 'failed', name='recording_status', create_type=False)
    transcript_status_enum = postgresql.ENUM('processing', 'completed', 'failed', name='transcript_status', create_type=False)

    # Create recordings table
    op.create_table(
        'recordings',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('tenant_id', sa.UUID(), nullable=False),
        sa.Column('encounter_id', sa.UUID(), nullable=False),
        sa.Column('storage_key', sa.String(length=500), nullable=False),
        sa.Column('storage_bucket', sa.String(length=100), nullable=False, server_default='audio-recordings'),
        sa.Column('file_format', sa.String(length=20), nullable=False),
        sa.Column('file_size_bytes', sa.BigInteger(), nullable=False),
        sa.Column('duration_sec', sa.Float(), nullable=True),
        sa.Column('status', recording_status_enum, nullable=False, server_default='uploading'),
        sa.Column('error_message', sa.String(length=1000), nullable=True),
        sa.Column('retry_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('transcription_started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('transcription_completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('original_filename', sa.String(length=255), nullable=True),
        sa.Column('content_type', sa.String(length=100), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['encounter_id'], ['encounters.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('storage_key')
    )

    # Create indexes on recordings
    op.create_index('ix_recordings_encounter_id', 'recordings', ['encounter_id'])
    op.create_index('ix_recordings_status', 'recordings', ['status'])
    op.create_index('ix_recordings_tenant_id', 'recordings', ['tenant_id'])

    # Create transcripts table
    op.create_table(
        'transcripts',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('tenant_id', sa.UUID(), nullable=False),
        sa.Column('recording_id', sa.UUID(), nullable=False),
        sa.Column('asr_engine', sa.String(length=100), nullable=False),
        sa.Column('asr_model_version', sa.String(length=100), nullable=True),
        sa.Column('status', transcript_status_enum, nullable=False, server_default='processing'),
        sa.Column('plain_text', sa.Text(), nullable=True),
        sa.Column('raw_output', sa.dialects.postgresql.JSONB(), nullable=True),
        sa.Column('processing_time_sec', sa.Float(), nullable=True),
        sa.Column('average_confidence', sa.Float(), nullable=True),
        sa.Column('language_detected', sa.String(length=10), nullable=True),
        sa.Column('error_message', sa.String(length=1000), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_corrected', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('corrected_text', sa.Text(), nullable=True),
        sa.Column('correction_metadata', sa.dialects.postgresql.JSONB(), nullable=True),
        sa.Column('corrected_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('corrected_by', sa.UUID(), nullable=True),
        sa.ForeignKeyConstraint(['corrected_by'], ['users.id'], ondelete='SET NULL'),
        sa.Column('physician_rating', sa.Integer(), nullable=True),
        sa.Column('physician_feedback', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['recording_id'], ['recordings.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

    # Create indexes on transcripts
    op.create_index('ix_transcripts_recording_id', 'transcripts', ['recording_id'])
    op.create_index('ix_transcripts_asr_engine', 'transcripts', ['asr_engine'])
    op.create_index('ix_transcripts_status', 'transcripts', ['status'])
    op.create_index('ix_transcripts_tenant_id', 'transcripts', ['tenant_id'])

    # Enable RLS on new tables
    op.execute("ALTER TABLE recordings ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE recordings FORCE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY tenant_isolation ON recordings
        FOR ALL
        USING (tenant_id = NULLIF(current_setting('app.tenant_id', TRUE), '')::UUID)
    """)

    op.execute("ALTER TABLE transcripts ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE transcripts FORCE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY tenant_isolation ON transcripts
        FOR ALL
        USING (tenant_id = NULLIF(current_setting('app.tenant_id', TRUE), '')::UUID)
    """)


def downgrade() -> None:
    """Downgrade database schema."""
    # Drop RLS policies
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON transcripts")
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON recordings")

    # Drop tables
    op.drop_index('ix_transcripts_tenant_id', table_name='transcripts')
    op.drop_index('ix_transcripts_status', table_name='transcripts')
    op.drop_index('ix_transcripts_asr_engine', table_name='transcripts')
    op.drop_index('ix_transcripts_recording_id', table_name='transcripts')
    op.drop_table('transcripts')

    op.drop_index('ix_recordings_tenant_id', table_name='recordings')
    op.drop_index('ix_recordings_status', table_name='recordings')
    op.drop_index('ix_recordings_encounter_id', table_name='recordings')
    op.drop_table('recordings')

    # Drop enums
    op.execute("DROP TYPE IF EXISTS transcript_status")
    op.execute("DROP TYPE IF EXISTS recording_status")
