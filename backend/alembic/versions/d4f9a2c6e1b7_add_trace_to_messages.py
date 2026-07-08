"""add trace to messages

Revision ID: d4f9a2c6e1b7
Revises: b8e3d5a1c7f2
Create Date: 2026-07-08 15:00:00.000000

Adds messages.trace: a nullable JSON column holding an assistant turn's ordered
non-answer stream events (thinking / tool_call / tool_result, plus a truncated
marker when the serialized trace is capped at 32 KB). Persisted post-stream so
reopening a conversation can replay the collapsed reasoning/trace panel exactly
like the live turn (#90). Existing rows and every user/error message keep a NULL
trace. The downgrade drops the column.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd4f9a2c6e1b7'
down_revision: Union[str, Sequence[str], None] = 'b8e3d5a1c7f2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add the nullable JSON trace column to messages."""
    op.add_column("messages", sa.Column("trace", sa.JSON(), nullable=True))


def downgrade() -> None:
    """Drop the trace column."""
    op.drop_column("messages", "trace")
