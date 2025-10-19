"""Add speaker_mapping and diarization_metadata fields only

Revision ID: a9367592e5da
Revises: f55377a2ea91
Create Date: 2025-10-19 03:48:00.000000+03:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'a9367592e5da'
down_revision: Union[str, None] = 'f55377a2ea91'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add speaker_mapping and diarization_metadata to transcripts table."""
    op.add_column(
        'transcripts',
        sa.Column(
            'speaker_mapping',
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment="""
        Mapping of pyannote speaker labels to semantic labels.
        Example: {"SPEAKER_00": "SPEAKER_0", "SPEAKER_01": "SPEAKER_1"}
        Can be manually updated to: {"SPEAKER_00": "DOCTOR", "SPEAKER_01": "PATIENT"}
        """
        )
    )
    op.add_column(
        'transcripts',
        sa.Column(
            'diarization_metadata',
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment="""
        Speaker diarization metadata:
        - num_speakers: int (number of speakers detected)
        - diarization_time_sec: float (processing time for diarization)
        - speaker_segments: list[dict] (raw diarization segments with timestamps)
        - diarization_engine: str (e.g., "pyannote-audio-3.1")
        Example: {
            "num_speakers": 2,
            "diarization_time_sec": 175.5,
            "diarization_engine": "pyannote-audio-3.1",
            "speaker_segments": [
                {"start": 0.0, "end": 5.5, "speaker": "SPEAKER_00"},
                {"start": 6.5, "end": 13.8, "speaker": "SPEAKER_01"}
            ]
        }
        """
        )
    )


def downgrade() -> None:
    """Remove speaker_mapping and diarization_metadata from transcripts table."""
    op.drop_column('transcripts', 'diarization_metadata')
    op.drop_column('transcripts', 'speaker_mapping')
