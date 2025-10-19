"""Add unique constraint on audit_events to prevent hash chain race conditions

Revision ID: 3da916c98460
Revises: 224beb08f380
Create Date: 2025-10-17 20:08:52.958512+03:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3da916c98460'
down_revision: Union[str, None] = '224beb08f380'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade database schema."""
    # Add unique constraint to prevent hash chain race conditions
    # This ensures no two audit events can reference the same prev_hash within a tenant
    # Prevents "forks" in the hash chain when concurrent requests append events
    op.create_unique_constraint(
        'uq_audit_events_tenant_prev_hash',
        'audit_events',
        ['tenant_id', 'prev_hash'],
        postgresql_nulls_not_distinct=False  # Allow multiple NULL prev_hash (one per tenant)
    )


def downgrade() -> None:
    """Downgrade database schema."""
    # Remove the unique constraint
    op.drop_constraint(
        'uq_audit_events_tenant_prev_hash',
        'audit_events',
        type_='unique'
    )
