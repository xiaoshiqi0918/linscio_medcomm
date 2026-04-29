"""add user admin_note and last_login_at columns

Revision ID: q1r2s3t4u5v6
Revises: p0q1r2s3t4u5
Create Date: 2026-04-25 15:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = "q1r2s3t4u5v6"
down_revision = "p0q1r2s3t4u5"
branch_labels = None
depends_on = None


def _has_column(table: str, column: str) -> bool:
    conn = op.get_bind()
    insp = sa.inspect(conn)
    return column in [c["name"] for c in insp.get_columns(table)]


def upgrade() -> None:
    if not _has_column("users", "admin_note"):
        op.add_column("users", sa.Column("admin_note", sa.Text(), nullable=True))
    if not _has_column("users", "last_login_at"):
        op.add_column("users", sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "last_login_at")
    op.drop_column("users", "admin_note")
