"""drop finetuning hardware score columns

Revision ID: c7e4b9a1d2f8
Revises: a1b2c3d4e5f6
Create Date: 2026-07-03 12:00:00.000000

Drops hardware_profiles.global_finetuning_score and .global_finetuning_label:
local fine-tuning was removed as a product feature (#99/#107) but its hardware
score kept flowing through the whole stack (#199). On a persisted (pre-existing)
database this destroys the two columns and their values -- the data loss is
intentional; the runner snapshots the cluster (pg_dump) before applying so it is
recoverable from db-backups/. On a fresh database the baseline creates the
columns and this revision immediately drops them again. The downgrade re-adds
both columns (backfilling existing rows via a temporary server_default) so the
revision is reversible.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c7e4b9a1d2f8'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Drop the leftover fine-tuning score and label columns."""
    op.drop_column('hardware_profiles', 'global_finetuning_label')
    op.drop_column('hardware_profiles', 'global_finetuning_score')


def downgrade() -> None:
    """Re-add the fine-tuning columns as the baseline defined them (NOT NULL, no
    server default), backfilling any existing rows through a temporary default."""
    op.add_column(
        'hardware_profiles',
        sa.Column('global_finetuning_score', sa.Float(), nullable=False, server_default='0'),
    )
    op.add_column(
        'hardware_profiles',
        sa.Column('global_finetuning_label', sa.String(), nullable=False, server_default='Unknown'),
    )
    op.alter_column('hardware_profiles', 'global_finetuning_score', server_default=None)
    op.alter_column('hardware_profiles', 'global_finetuning_label', server_default=None)
