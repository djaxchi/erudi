"""param_size nullable on llms

Revision ID: e5a7c3b91d0f
Revises: d4f9a2c6e1b7
Create Date: 2026-07-08 10:00:00.000000

Makes llms.param_size nullable so a genuinely unmeasured size can be stored as
NULL (unknown) rather than a plausible constant (#201). A defaulted number was
indistinguishable from a measured one downstream, so a frontier model with no
measurable size rated as a comfortable 7B fit. Existing rows keep their current
value (possibly a stale default); the fix only stops new discoveries from
laundering an unknown size, and the next catalog resync re-measures remote rows.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e5a7c3b91d0f'
down_revision: Union[str, Sequence[str], None] = 'd4f9a2c6e1b7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Drop the NOT NULL constraint on llms.param_size (NULL = size unknown)."""
    op.alter_column("llms", "param_size", existing_type=sa.Float(), nullable=True)


def downgrade() -> None:
    """Restore NOT NULL, backfilling any NULL rows to a neutral placeholder so the
    constraint can be re-applied (the original unknown information is lost)."""
    op.execute("UPDATE llms SET param_size = 4.0 WHERE param_size IS NULL")
    op.alter_column("llms", "param_size", existing_type=sa.Float(), nullable=False)
