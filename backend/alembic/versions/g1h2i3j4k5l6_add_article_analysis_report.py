"""add article analysis_report column

Revision ID: g1h2i3j4k5l6
Revises: a0b1c2d3e4f5
Create Date: 2026-04-08

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "g1h2i3j4k5l6"
down_revision: Union[str, Sequence[str], None] = "a0b1c2d3e4f5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("articles", sa.Column("analysis_report", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("articles", "analysis_report")
