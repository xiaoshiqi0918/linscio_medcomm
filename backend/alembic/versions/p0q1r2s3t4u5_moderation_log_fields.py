"""content_moderation_logs: align fields with three-layer moderation spec

Replace content_type/content_hash/result/risk_labels/confidence/provider/raw_response
with stage/rule_level/matched_rule/snippet/action_taken/meta.

Revision ID: p0q1r2s3t4u5
Revises: o9p0q1r2s3t4
Create Date: 2026-04-25
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "p0q1r2s3t4u5"
down_revision: Union[str, None] = "o9p0q1r2s3t4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add new columns
    op.add_column("content_moderation_logs", sa.Column("stage", sa.String(20), nullable=True))
    op.add_column("content_moderation_logs", sa.Column("rule_level", sa.String(20), nullable=True))
    op.add_column("content_moderation_logs", sa.Column("matched_rule", sa.String(128), nullable=True))
    op.add_column("content_moderation_logs", sa.Column("snippet", sa.Text(), nullable=True))
    op.add_column("content_moderation_logs", sa.Column("action_taken", sa.String(32), nullable=True, server_default="blocked"))
    op.add_column("content_moderation_logs", sa.Column("meta", sa.JSON(), nullable=True))

    # Migrate existing data: map old columns → new columns
    op.execute("""
        UPDATE content_moderation_logs SET
            stage = COALESCE(content_type, 'generation'),
            rule_level = CASE
                WHEN result = 'block' THEN 'block'
                WHEN result = 'warn' THEN 'warn'
                ELSE 'info'
            END,
            action_taken = CASE
                WHEN result = 'block' THEN 'blocked'
                WHEN result = 'warn' THEN 'passed_with_warning'
                ELSE 'pass'
            END
        WHERE stage IS NULL
    """)

    # Make stage/rule_level NOT NULL now that data is migrated
    op.alter_column("content_moderation_logs", "stage", nullable=False, server_default="generation")
    op.alter_column("content_moderation_logs", "rule_level", nullable=False, server_default="info")

    # Drop old columns
    op.drop_column("content_moderation_logs", "content_type")
    op.drop_column("content_moderation_logs", "content_hash")
    op.drop_column("content_moderation_logs", "result")
    op.drop_column("content_moderation_logs", "risk_labels")
    op.drop_column("content_moderation_logs", "confidence")
    op.drop_column("content_moderation_logs", "provider")
    op.drop_column("content_moderation_logs", "raw_response")

    # Drop old index, create new one
    try:
        op.drop_index("idx_moderation_result", table_name="content_moderation_logs")
    except Exception:
        pass
    op.create_index("idx_moderation_stage", "content_moderation_logs", ["stage", "rule_level", "created_at"])


def downgrade() -> None:
    op.drop_index("idx_moderation_stage", table_name="content_moderation_logs")

    op.add_column("content_moderation_logs", sa.Column("content_type", sa.String(32), nullable=True))
    op.add_column("content_moderation_logs", sa.Column("content_hash", sa.String(64), nullable=True))
    op.add_column("content_moderation_logs", sa.Column("result", sa.String(20), nullable=True, server_default="pass"))
    op.add_column("content_moderation_logs", sa.Column("risk_labels", sa.JSON(), nullable=True))
    op.add_column("content_moderation_logs", sa.Column("confidence", sa.Numeric(5, 4), nullable=True))
    op.add_column("content_moderation_logs", sa.Column("provider", sa.String(50), nullable=True))
    op.add_column("content_moderation_logs", sa.Column("raw_response", sa.JSON(), nullable=True))

    op.drop_column("content_moderation_logs", "meta")
    op.drop_column("content_moderation_logs", "action_taken")
    op.drop_column("content_moderation_logs", "snippet")
    op.drop_column("content_moderation_logs", "matched_rule")
    op.drop_column("content_moderation_logs", "rule_level")
    op.drop_column("content_moderation_logs", "stage")

    op.create_index("idx_moderation_result", "content_moderation_logs", ["result", "created_at"])
