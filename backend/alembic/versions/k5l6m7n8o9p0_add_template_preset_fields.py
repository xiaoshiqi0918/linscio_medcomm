"""content_templates 增加预设配置字段

Revision ID: k5l6m7n8o9p0
Revises: j4k5l6m7n8o9
Create Date: 2026-04-17
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "k5l6m7n8o9p0"
down_revision: Union[str, Sequence[str], None] = "j4k5l6m7n8o9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("content_templates", sa.Column("target_word_count", sa.Integer(), nullable=True))
    op.add_column("content_templates", sa.Column("target_audience", sa.String(30), nullable=True))
    op.add_column("content_templates", sa.Column("reading_level", sa.String(30), nullable=True))
    op.add_column("content_templates", sa.Column("skip_sections", sa.JSON(), nullable=True))
    op.add_column("content_templates", sa.Column("updated_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("content_templates", "updated_at")
    op.drop_column("content_templates", "skip_sections")
    op.drop_column("content_templates", "reading_level")
    op.drop_column("content_templates", "target_audience")
    op.drop_column("content_templates", "target_word_count")
