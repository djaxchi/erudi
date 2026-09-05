"""web search settings and conversation flag

Revision ID: a7c5e2d9f4b1
Revises: c9d2e4f7a1b3
Create Date: 2026-08-19 10:00:00.000000

Issue #310: the web_search agent tool ships with two toggles.

1. ``user_settings`` — a NEW singleton table (mirrors startup_variables)
   holding the GLOBAL web-search default, off by default: a web search
   egresses the user's query, so the local-first product keeps it opt-in.
2. ``conversations.web_search_enabled`` — the per-conversation toggle,
   nullable-free with a server default of false so existing rows backfill
   to off. The application copies the global default at conversation
   creation; afterwards the conversation owns its flag (a later global
   change never retro-affects existing conversations).
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a7c5e2d9f4b1"
down_revision: Union[str, Sequence[str], None] = "c9d2e4f7a1b3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create the user_settings singleton and the per-conversation flag."""
    op.create_table(
        "user_settings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column(
            "web_search_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_user_settings_id"), "user_settings", ["id"], unique=False)
    op.add_column(
        "conversations",
        sa.Column(
            "web_search_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )


def downgrade() -> None:
    """Drop the conversation flag and the user_settings table."""
    op.drop_column("conversations", "web_search_enabled")
    op.drop_index(op.f("ix_user_settings_id"), table_name="user_settings")
    op.drop_table("user_settings")
