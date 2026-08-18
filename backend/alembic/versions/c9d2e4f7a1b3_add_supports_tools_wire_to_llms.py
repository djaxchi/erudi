"""add supports_tools_wire to llms

Revision ID: c9d2e4f7a1b3
Revises: b3f8c1e6a927
Create Date: 2026-08-18 10:00:00.000000

Adds llms.supports_tools_wire (#298): the VERIFIED tool-call wire capability.
supports_tools only says the chat template declares tools; this column says the
active engine's local server actually parses the model's tool-call output into
a structured call (a per-model wire property — the #273 matrix showed e.g.
Qwen3-4B-2507 declares tools but matches no mlx-vlm parser, so its answer is
swallowed, #295). Detected at download finalization and backfilled post-ready
for models downloaded before this change. Nullable: existing rows backfill to
NULL (unverified); KB routing goes agentic only on an explicit True.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c9d2e4f7a1b3'
down_revision: Union[str, Sequence[str], None] = 'b3f8c1e6a927'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add the nullable wire-capability flag (NULL = unverified)."""
    op.add_column("llms", sa.Column("supports_tools_wire", sa.Boolean(), nullable=True))


def downgrade() -> None:
    """Drop the supports_tools_wire column."""
    op.drop_column("llms", "supports_tools_wire")
