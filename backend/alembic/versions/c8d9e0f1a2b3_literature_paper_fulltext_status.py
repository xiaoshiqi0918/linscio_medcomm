"""literature_papers.fulltext_status 全文可用状态

Revision ID: c8d9e0f1a2b3
Revises: f2a3b4c5d6e7
Create Date: 2026-03-31

full: 已有可检索全文（PDF 解析或开放获取正文已入 paper_chunks）
pending: 待解析（有 PDF 路径或 PMID/DOI 可尝试拉取 OA）
no_fulltext: 当前无全文（需用户补传 PDF 或换一篇有 OA 的文献）
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "c8d9e0f1a2b3"
down_revision: Union[str, None] = "f2a3b4c5d6e7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "literature_papers",
        sa.Column("fulltext_status", sa.String(length=32), nullable=True),
    )
    op.execute(
        """
        UPDATE literature_papers
        SET fulltext_status = 'full'
        WHERE id IN (SELECT DISTINCT paper_id FROM paper_chunks WHERE paper_id IS NOT NULL)
        """
    )
    op.execute(
        """
        UPDATE literature_papers
        SET fulltext_status = 'pending'
        WHERE fulltext_status IS NULL
          AND (
            (pdf_path IS NOT NULL AND TRIM(COALESCE(pdf_path, '')) != '')
            OR (pmid IS NOT NULL AND TRIM(COALESCE(pmid, '')) != '')
            OR (doi IS NOT NULL AND TRIM(COALESCE(doi, '')) != '')
          )
        """
    )
    op.execute(
        """
        UPDATE literature_papers
        SET fulltext_status = 'no_fulltext'
        WHERE fulltext_status IS NULL
        """
    )


def downgrade() -> None:
    op.drop_column("literature_papers", "fulltext_status")
