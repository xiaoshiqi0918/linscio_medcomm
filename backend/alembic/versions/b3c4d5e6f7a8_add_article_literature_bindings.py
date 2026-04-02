"""add article_literature_bindings

Revision ID: b3c4d5e6f7a8
Revises: f1a2b3c4d5e6
Create Date: 2026-03-24
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b3c4d5e6f7a8"
down_revision: Union[str, Sequence[str], None] = "f1a2b3c4d5e6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "article_literature_bindings",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("article_id", sa.Integer(), nullable=False),
        sa.Column("section_id", sa.Integer(), nullable=True),
        sa.Column("paper_id", sa.Integer(), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=True, server_default="100"),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["article_id"], ["articles.id"]),
        sa.ForeignKeyConstraint(["section_id"], ["article_sections.id"]),
        sa.ForeignKeyConstraint(["paper_id"], ["literature_papers.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("article_id", "section_id", "paper_id", name="uq_article_section_paper"),
    )
    op.create_index("idx_bindings_article", "article_literature_bindings", ["article_id"])
    op.create_index("idx_bindings_section", "article_literature_bindings", ["section_id"])
    op.create_index("idx_bindings_paper", "article_literature_bindings", ["paper_id"])


def downgrade() -> None:
    op.drop_index("idx_bindings_paper", table_name="article_literature_bindings")
    op.drop_index("idx_bindings_section", table_name="article_literature_bindings")
    op.drop_index("idx_bindings_article", table_name="article_literature_bindings")
    op.drop_table("article_literature_bindings")
