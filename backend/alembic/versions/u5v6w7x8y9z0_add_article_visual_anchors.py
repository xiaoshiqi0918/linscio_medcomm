"""add article_visual_anchors table for cross-section image consistency

Revision ID: u5v6w7x8y9z0
Revises: t4u5v6w7x8y9
"""
from alembic import op
import sqlalchemy as sa


revision = "u5v6w7x8y9z0"
down_revision = "t4u5v6w7x8y9"
branch_labels = None
depends_on = None


def _has_table(bind, name: str) -> bool:
    return name in sa.inspect(bind).get_table_names()


def upgrade() -> None:
    bind = op.get_bind()
    if _has_table(bind, "article_visual_anchors"):
        return

    op.create_table(
        "article_visual_anchors",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "article_id",
            sa.Integer,
            sa.ForeignKey("articles.id"),
            nullable=False,
            unique=True,
        ),
        sa.Column("characters", sa.JSON, nullable=True),
        sa.Column("style_lock", sa.JSON, nullable=True),
        sa.Column("base_seed", sa.Integer, nullable=True),
        sa.Column("anchor_image_path", sa.String(500), nullable=True),
        sa.Column("anchor_source", sa.String(20), nullable=True),
        sa.Column("auto_extracted_at", sa.DateTime, nullable=True),
        sa.Column("last_modified_by", sa.String(20), nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index(
        "ix_article_visual_anchors_article_id",
        "article_visual_anchors",
        ["article_id"],
    )


def downgrade() -> None:
    bind = op.get_bind()
    if not _has_table(bind, "article_visual_anchors"):
        return
    op.drop_index(
        "ix_article_visual_anchors_article_id", table_name="article_visual_anchors"
    )
    op.drop_table("article_visual_anchors")
