"""add category to llms

Revision ID: a1b2c3d4e5f6
Revises: f2107afc82f6
Create Date: 2026-06-27 19:30:00.000000

Adds llms.category: capability bucket (general / code / reasoning / math /
vision / medical / function / safety) derived at discovery from pipeline_tag +
card tags + slug. Drives the categorized catalog sections in the UI (#122).
Existing rows backfill to 'general'; the next catalog resync re-classifies
remote (local=0) rows.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = 'f2107afc82f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add the NOT NULL category column, backfilling existing rows to 'general',
    then drop the server default so the column matches the SQLAlchemy model."""
    op.add_column(
        "llms",
        sa.Column("category", sa.String(), nullable=False, server_default="general"),
    )
    op.alter_column("llms", "category", server_default=None)


def downgrade() -> None:
    """Drop the category column."""
    op.drop_column("llms", "category")
