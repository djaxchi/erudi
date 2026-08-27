"""add profiling_version to hardware_profiles

The hardware profile is written once at first boot and read forever after, so a
correction to detection or scoring never reaches a machine that already has a
row. #365 fixed a 448 GB/s card being profiled at 13 GB/s (NVML was read for the
idle clock), and the corrected build still served the stored 13.

Stamping the profiling revision on the row lets startup notice the numbers came
from logic we have since replaced and redo them. Existing rows get NULL, which
never equals the current version, so every install re-profiles exactly once on
the first boot after upgrading.

Revision ID: d1a4f7c39b52
Revises: a7c5e2d9f4b1
Create Date: 2026-08-26

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'd1a4f7c39b52'
down_revision: Union[str, Sequence[str], None] = 'a7c5e2d9f4b1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'hardware_profiles',
        sa.Column('profiling_version', sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('hardware_profiles', 'profiling_version')
