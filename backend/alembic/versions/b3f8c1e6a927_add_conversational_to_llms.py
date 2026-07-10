"""add conversational to llms

Revision ID: b3f8c1e6a927
Revises: e5a7c3b91d0f
Create Date: 2026-07-10 10:00:00.000000

Adds llms.conversational (#182): True = instruction-tuned / chat model (the
official variant users want), False = a non-conversational release. Set at
discovery from HuggingFace's `conversational` tag (with an instruct-suffix
backstop). Recommendations lead with conversational models and the catalog lists
sort them first, since most users just want to chat and don't know the IT-vs-base
distinction. Nullable: existing rows backfill to NULL (unknown) and are re-set on
the next catalog resync; NULL is treated as "fall back to the name heuristic".
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b3f8c1e6a927'
down_revision: Union[str, Sequence[str], None] = 'e5a7c3b91d0f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add the nullable conversational flag (NULL = unknown until next resync)."""
    op.add_column("llms", sa.Column("conversational", sa.Boolean(), nullable=True))


def downgrade() -> None:
    """Drop the conversational column."""
    op.drop_column("llms", "conversational")
