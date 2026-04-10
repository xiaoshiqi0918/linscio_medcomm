"""literature_papers.open_access_url — 存储检索来源的 OA PDF 链接

Revision ID: h2i3j4k5l6m7
Revises: g1h2i3j4k5l6
Create Date: 2026-04-09
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "h2i3j4k5l6m7"
down_revision: Union[str, Sequence[str], None] = "g1h2i3j4k5l6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "literature_papers",
        sa.Column("open_access_url", sa.Text(), nullable=True, server_default=""),
    )


def downgrade() -> None:
    op.drop_column("literature_papers", "open_access_url")
