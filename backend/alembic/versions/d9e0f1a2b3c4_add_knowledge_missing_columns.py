"""add is_system, specialty, source to knowledge_docs and specialty to knowledge_chunks

These columns were added to the ORM models but missed from the migration chain.

Revision ID: d9e0f1a2b3c4
Revises: c8d9e0f1a2b3
Create Date: 2026-04-02

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d9e0f1a2b3c4"
down_revision: Union[str, Sequence[str], None] = "c8d9e0f1a2b3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _col_exists(table: str, column: str) -> bool:
    """Check if a column already exists (safety for re-runs on existing DBs)."""
    bind = op.get_bind()
    result = bind.execute(sa.text(f"PRAGMA table_info('{table}')"))
    return any(row[1] == column for row in result)


def upgrade() -> None:
    if not _col_exists("knowledge_docs", "is_system"):
        op.add_column(
            "knowledge_docs",
            sa.Column("is_system", sa.Boolean(), nullable=True, server_default=sa.text("0")),
        )
    if not _col_exists("knowledge_docs", "specialty"):
        op.add_column(
            "knowledge_docs",
            sa.Column("specialty", sa.String(length=50), nullable=True),
        )
        op.create_index("ix_knowledge_docs_specialty", "knowledge_docs", ["specialty"])
    if not _col_exists("knowledge_docs", "source"):
        op.add_column(
            "knowledge_docs",
            sa.Column("source", sa.String(length=20), nullable=True, server_default="user"),
        )
    if not _col_exists("knowledge_chunks", "specialty"):
        op.add_column(
            "knowledge_chunks",
            sa.Column("specialty", sa.String(length=50), nullable=True),
        )
        op.create_index("ix_knowledge_chunks_specialty", "knowledge_chunks", ["specialty"])


def downgrade() -> None:
    op.drop_index("ix_knowledge_chunks_specialty", table_name="knowledge_chunks")
    op.drop_column("knowledge_chunks", "specialty")
    op.drop_column("knowledge_docs", "source")
    op.drop_index("ix_knowledge_docs_specialty", table_name="knowledge_docs")
    op.drop_column("knowledge_docs", "specialty")
    op.drop_column("knowledge_docs", "is_system")
