"""add auto_update_enabled to user_settings

The automatic-update preference is an app-wide setting persisted next to the
web-search default and the interface language. The column is NOT NULL with a
server default of true so an install that predates this revision keeps
downloading and installing updates exactly as it did: the setting only exists
to let someone refuse them.

Revision ID: a9f4c1b7e206
Revises: b6e1a4d8c2f7
Create Date: 2026-09-05

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a9f4c1b7e206'
down_revision: Union[str, Sequence[str], None] = 'b6e1a4d8c2f7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'user_settings',
        sa.Column('auto_update_enabled', sa.Boolean(), nullable=False, server_default=sa.true()),
    )


def downgrade() -> None:
    op.drop_column('user_settings', 'auto_update_enabled')
