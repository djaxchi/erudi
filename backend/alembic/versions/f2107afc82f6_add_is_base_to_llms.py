"""add is_base to llms

Revision ID: f2107afc82f6
Revises: 7bc061d58b4e
Create Date: 2026-06-25 22:13:51.106206

Adds llms.is_base: True = curated foundation/base model (discovered from a
FOUNDATION_ORG), False = derived/community quant. Drives the Base vs Community
split and "Models For You" recommendations in the UI (#86). Existing rows
backfill to False; the next catalog resync re-marks remote (local=0) rows.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f2107afc82f6'
down_revision: Union[str, Sequence[str], None] = '7bc061d58b4e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add the NOT NULL is_base column, backfilling existing rows to False, then
    drop the server default so the column matches the SQLAlchemy model exactly."""
    op.add_column(
        "llms",
        sa.Column("is_base", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.alter_column("llms", "is_base", server_default=None)


def downgrade() -> None:
    """Drop the is_base column."""
    op.drop_column("llms", "is_base")
