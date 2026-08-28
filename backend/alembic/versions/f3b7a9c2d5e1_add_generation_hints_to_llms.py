"""add generation_hints to llms

Per-model sampling defaults (#388, closes the #136-A item). The column holds the
sampling FACTS captured from a model's base repo (a whitelisted subset of
generation_config.json, the context window, the thinking flag), never the
resolved defaults: src.database.generation_hints resolves ``curated > hf >
fallback`` at read time. Existing rows get NULL = "no hints" = today's
constants, so nothing changes for a catalog that predates the capture.

Revision ID: f3b7a9c2d5e1
Revises: d1a4f7c39b52
Create Date: 2026-08-28

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'f3b7a9c2d5e1'
down_revision: Union[str, Sequence[str], None] = 'd1a4f7c39b52'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('llms', sa.Column('generation_hints', sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column('llms', 'generation_hints')
