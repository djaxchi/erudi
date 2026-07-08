"""conversations survive model deletion (llm_id nullable, FK SET NULL)

Revision ID: b8e3d5a1c7f2
Revises: c7e4b9a1d2f8
Create Date: 2026-07-08 12:00:00.000000

Makes conversations.llm_id NULLABLE and switches its foreign key from
ON DELETE CASCADE to ON DELETE SET NULL, so a conversation survives the
deletion of its model instead of being destroyed with it (#225, #208). The
baseline created the FK without an explicit name, so PostgreSQL assigned it the
default 'conversations_llm_id_fkey'; this drops that constraint and recreates it
by the same name with the new rule.

Downgrade restores NOT NULL + ON DELETE CASCADE. Re-adding NOT NULL cannot
coexist with orphaned rows (llm_id IS NULL, left behind after a model was
deleted), so the downgrade first DELETES every such conversation. That row loss
is intentional and irreversible -- it is the cost of reverting to the old
strict-binding schema.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b8e3d5a1c7f2'
down_revision: Union[str, Sequence[str], None] = 'c7e4b9a1d2f8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# PostgreSQL's default name for the unnamed baseline FK on conversations.llm_id.
_FK_NAME = "conversations_llm_id_fkey"


def upgrade() -> None:
    """llm_id becomes nullable; its FK switches CASCADE -> SET NULL."""
    op.drop_constraint(_FK_NAME, "conversations", type_="foreignkey")
    op.alter_column("conversations", "llm_id", existing_type=sa.Integer(), nullable=True)
    op.create_foreign_key(
        _FK_NAME, "conversations", "llms",
        ["llm_id"], ["id"], ondelete="SET NULL",
    )


def downgrade() -> None:
    """Restore NOT NULL + ON DELETE CASCADE. Orphaned conversations (llm_id
    IS NULL) block the NOT NULL re-add, so they are deleted first -- an
    intentional, irreversible data loss when reverting to strict binding."""
    op.execute("DELETE FROM conversations WHERE llm_id IS NULL")
    op.drop_constraint(_FK_NAME, "conversations", type_="foreignkey")
    op.alter_column("conversations", "llm_id", existing_type=sa.Integer(), nullable=False)
    op.create_foreign_key(
        _FK_NAME, "conversations", "llms",
        ["llm_id"], ["id"], ondelete="CASCADE",
    )
