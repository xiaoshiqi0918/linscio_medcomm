"""llm_call_logs: add session_id, cost_usd, cost_credits, task index

Revision ID: o9p0q1r2s3t4
Revises: n8o9p0q1r2s3
Create Date: 2026-04-25
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "o9p0q1r2s3t4"
down_revision: Union[str, None] = "n8o9p0q1r2s3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("llm_call_logs", sa.Column("session_id", sa.String(36), nullable=True))
    op.add_column("llm_call_logs", sa.Column("cost_usd", sa.Numeric(10, 6), nullable=True))
    op.add_column("llm_call_logs", sa.Column("cost_credits", sa.Numeric(10, 4), nullable=True))
    op.create_index("idx_llm_call_task", "llm_call_logs", ["task_type", "created_at"])


def downgrade() -> None:
    op.drop_index("idx_llm_call_task", table_name="llm_call_logs")
    op.drop_column("llm_call_logs", "cost_credits")
    op.drop_column("llm_call_logs", "cost_usd")
    op.drop_column("llm_call_logs", "session_id")
