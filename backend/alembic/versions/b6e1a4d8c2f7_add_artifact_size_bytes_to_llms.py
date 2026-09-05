"""add artifact_size_bytes to llms

The real size of a model artifact, in bytes: for a catalog row the files the
downloader would fetch from the quant repo (captured at snapshot time, from
the same repo_info call that feeds the Size line), for an installed row the
measured on-disk footprint written at download completion. The frontend reads
it before its per-parameter estimate, which misses a VLM's vision tower by
25-35 % (Qwen2.5-VL-3B: "~2.3 GB" shown against 3.09 GB downloaded). BIGINT
because model artifacts exceed 2^31 bytes. Existing rows get NULL = unknown,
so the estimate stands until the next snapshot or download fills it in.

Revision ID: b6e1a4d8c2f7
Revises: f3b7a9c2d5e1
Create Date: 2026-08-29

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b6e1a4d8c2f7"
down_revision: Union[str, Sequence[str], None] = "f3b7a9c2d5e1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("llms", sa.Column("artifact_size_bytes", sa.BigInteger(), nullable=True))


def downgrade() -> None:
    op.drop_column("llms", "artifact_size_bytes")
