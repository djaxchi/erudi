"""drop training_jobs table

Revision ID: 7bc061d58b4e
Revises: 5ac171e299c6
Create Date: 2026-06-21 17:38:54.716365

Drops the ``training_jobs`` table: the local fine-tuning feature was never
implemented (dead code) and has been removed (TrainingJob entity, training
domain, file_processor). On a persisted (pre-existing) database this destroys
the table and its rows — the runner snapshots the cluster (pg_dump) before
applying, so it is recoverable from db-backups/. On a fresh database the
baseline creates the table and this revision immediately drops it again.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7bc061d58b4e'
down_revision: Union[str, Sequence[str], None] = '5ac171e299c6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Drop the dead training_jobs table."""
    op.drop_index(op.f('ix_training_jobs_id'), table_name='training_jobs')
    op.drop_table('training_jobs')


def downgrade() -> None:
    """Recreate training_jobs as defined by the baseline revision."""
    op.create_table(
        'training_jobs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('llm_id', sa.Integer(), nullable=True),
        sa.Column('status', sa.String(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('progress', sa.Float(), nullable=True),
        sa.Column('time_elapsed', sa.Float(), nullable=True),
        sa.Column('time_left', sa.Float(), nullable=True),
        sa.ForeignKeyConstraint(['llm_id'], ['llms.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_training_jobs_id'), 'training_jobs', ['id'], unique=False)
