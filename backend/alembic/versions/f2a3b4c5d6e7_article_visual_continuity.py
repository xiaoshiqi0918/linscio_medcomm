"""article visual continuity + series seed base

Revision ID: f2a3b4c5d6e7
Revises: b3c4d5e6f7a8
Create Date: 2026-03-31

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f2a3b4c5d6e7"
down_revision: Union[str, Sequence[str], None] = "b3c4d5e6f7a8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("articles", sa.Column("visual_continuity_prompt", sa.Text(), nullable=True))
    op.add_column("articles", sa.Column("image_series_seed_base", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("articles", "image_series_seed_base")
    op.drop_column("articles", "visual_continuity_prompt")
