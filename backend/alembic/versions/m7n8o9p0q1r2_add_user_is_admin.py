"""users 增加 is_admin 字段

Revision ID: m7n8o9p0q1r2
Revises: l6m7n8o9p0q1
Create Date: 2026-04-24
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "m7n8o9p0q1r2"
down_revision: Union[str, None] = "l6m7n8o9p0q1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    insp = sa.inspect(conn)
    if "is_admin" not in [c["name"] for c in insp.get_columns("users")]:
        op.add_column("users", sa.Column("is_admin", sa.Boolean(), server_default="false", nullable=True))


def downgrade() -> None:
    op.drop_column("users", "is_admin")
