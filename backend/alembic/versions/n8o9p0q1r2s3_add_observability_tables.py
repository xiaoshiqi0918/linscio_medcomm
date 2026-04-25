"""tasks / streaming_sessions / admin_audit_logs / llm_call_logs / content_moderation_logs

Revision ID: n8o9p0q1r2s3
Revises: m7n8o9p0q1r2
Create Date: 2026-04-25
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "n8o9p0q1r2s3"
down_revision: Union[str, None] = "m7n8o9p0q1r2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── tasks ──────────────────────────────────────────────
    op.create_table(
        "tasks",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("task_id", sa.String(64), unique=True, nullable=False, index=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("task_type", sa.String(32), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.Column("result", sa.JSON(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("idx_tasks_user_status", "tasks", ["user_id", "status", "created_at"])

    # ── streaming_sessions ─────────────────────────────────
    op.create_table(
        "streaming_sessions",
        sa.Column("session_id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("article_id", sa.Integer(), nullable=True),
        sa.Column("section_id", sa.Integer(), nullable=True),
        sa.Column("task_type", sa.String(64), nullable=False),
        sa.Column("estimated_cost", sa.Numeric(10, 4), nullable=False),
        sa.Column("actual_tokens_in", sa.Integer(), server_default="0"),
        sa.Column("actual_tokens_out", sa.Integer(), server_default="0"),
        sa.Column("actual_cost", sa.Numeric(10, 4), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="streaming"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_heartbeat_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("idx_streaming_status_heartbeat", "streaming_sessions", ["status", "last_heartbeat_at"])

    # ── admin_audit_logs ───────────────────────────────────
    op.create_table(
        "admin_audit_logs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("admin_id", sa.Integer(), nullable=False),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("target_user_id", sa.Integer(), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # ── llm_call_logs ──────────────────────────────────────
    op.create_table(
        "llm_call_logs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("article_id", sa.Integer(), nullable=True),
        sa.Column("section_id", sa.Integer(), nullable=True),
        sa.Column("task_type", sa.String(64), nullable=False),
        sa.Column("model", sa.String(100), nullable=False),
        sa.Column("provider", sa.String(50), nullable=True),
        sa.Column("tokens_in", sa.Integer(), server_default="0"),
        sa.Column("tokens_out", sa.Integer(), server_default="0"),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="success"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("meta", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("idx_llm_call_user_created", "llm_call_logs", ["user_id", "created_at"])
    op.create_index("idx_llm_call_model", "llm_call_logs", ["model", "created_at"])

    # ── content_moderation_logs ────────────────────────────
    op.create_table(
        "content_moderation_logs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("article_id", sa.Integer(), nullable=True),
        sa.Column("section_id", sa.Integer(), nullable=True),
        sa.Column("content_type", sa.String(32), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=True),
        sa.Column("result", sa.String(20), nullable=False, server_default="pass"),
        sa.Column("risk_labels", sa.JSON(), nullable=True),
        sa.Column("confidence", sa.Numeric(5, 4), nullable=True),
        sa.Column("provider", sa.String(50), nullable=True),
        sa.Column("raw_response", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("idx_moderation_user", "content_moderation_logs", ["user_id", "created_at"])
    op.create_index("idx_moderation_result", "content_moderation_logs", ["result", "created_at"])

    # ── paper_chunks: search_vector tsvector + GIN（仅 PG）
    # 此列由 fts5.py 中 _ensure_fts_tables_pg() 动态创建，此处做声明式保障
    try:
        op.add_column("paper_chunks", sa.Column("search_vector", sa.Text(), nullable=True))
    except Exception:
        pass

    try:
        op.add_column("knowledge_chunks", sa.Column("search_vector", sa.Text(), nullable=True))
    except Exception:
        pass


def downgrade() -> None:
    try:
        op.drop_column("knowledge_chunks", "search_vector")
    except Exception:
        pass
    try:
        op.drop_column("paper_chunks", "search_vector")
    except Exception:
        pass
    op.drop_table("content_moderation_logs")
    op.drop_table("llm_call_logs")
    op.drop_table("admin_audit_logs")
    op.drop_table("streaming_sessions")
    op.drop_table("tasks")
