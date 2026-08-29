"""add language to user_settings

Issue #385: the interface language is an app-wide setting persisted next to
the web-search default. The column is NOT NULL with a server default of
'en' so a row created before this revision (and any row inserted without
the field) reads as English, which is also the frontend's fallback
language. Validity of the code (en/fr/es/zh) is enforced by the entity
validator and the API schema, not by the database.

Revision ID: e8b4d2f6a193
Revises: d1a4f7c39b52
Create Date: 2026-08-27

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'e8b4d2f6a193'
down_revision: Union[str, Sequence[str], None] = 'd1a4f7c39b52'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'user_settings',
        sa.Column('language', sa.String(length=8), nullable=False, server_default='en'),
    )


def downgrade() -> None:
    op.drop_column('user_settings', 'language')
