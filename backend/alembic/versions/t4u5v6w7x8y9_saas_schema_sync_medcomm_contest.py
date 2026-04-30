"""sync medcomm/article/contest/schema drift for SaaS (submission_info, slots, presets, packs, user_rules)

Revision ID: t4u5v6w7x8y9
Revises: s3t4u5v6w7x8
"""
from alembic import op
import sqlalchemy as sa

revision = "t4u5v6w7x8y9"
down_revision = "s3t4u5v6w7x8"
branch_labels = None
depends_on = None


def _has_table(bind, name: str) -> bool:
    return name in sa.inspect(bind).get_table_names()


def _has_column(bind, table: str, col: str) -> bool:
    return any(c["name"] == col for c in sa.inspect(bind).get_columns(table))


def upgrade() -> None:
    bind = op.get_bind()

    if not _has_column(bind, "articles", "submission_info"):
        with op.batch_alter_table("articles") as batch_op:
            batch_op.add_column(sa.Column("submission_info", sa.JSON, nullable=True))

    if not _has_column(bind, "contest_packs", "word_count_includes"):
        with op.batch_alter_table("contest_packs") as batch_op:
            batch_op.add_column(sa.Column("word_count_includes", sa.JSON, nullable=True))

    if _has_table(bind, "article_image_slots"):
        slot_adds = []
        if not _has_column(bind, "article_image_slots", "style_preset_version"):
            slot_adds.append(sa.Column("style_preset_version", sa.Integer(), nullable=True))
        if not _has_column(bind, "article_image_slots", "image_provider"):
            slot_adds.append(sa.Column("image_provider", sa.String(30), nullable=True))
        if slot_adds:
            with op.batch_alter_table("article_image_slots") as batch_op:
                for col in slot_adds:
                    batch_op.add_column(col)

    if _has_table(bind, "painting_intent_examples") and not _has_column(bind, "painting_intent_examples", "preset_version"):
        with op.batch_alter_table("painting_intent_examples") as batch_op:
            batch_op.add_column(sa.Column("preset_version", sa.Integer(), nullable=True))

    preset_adds = []
    if _has_table(bind, "style_presets"):
        for name in ("default_composition", "default_lighting", "default_color"):
            if not _has_column(bind, "style_presets", name):
                preset_adds.append(sa.Column(name, sa.String(100), nullable=True))
    if preset_adds:
        with op.batch_alter_table("style_presets") as batch_op:
            for col in preset_adds:
                batch_op.add_column(col)

    if not _has_table(bind, "user_contest_rules"):
        op.create_table(
            "user_contest_rules",
            sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
            sa.Column("user_id", sa.Integer, nullable=False),
            sa.Column("name", sa.String(200), nullable=False),
            sa.Column("rules", sa.JSON, nullable=False),
            sa.Column("source", sa.String(20), nullable=False, server_default="manual"),
            sa.Column("is_active", sa.Boolean(), nullable=True),
            sa.Column("submitted_as_public", sa.Boolean(), nullable=True),
            sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
        )
        op.create_index("ix_user_contest_rules_user_id", "user_contest_rules", ["user_id"])


def downgrade() -> None:
    bind = op.get_bind()

    if _has_table(bind, "user_contest_rules"):
        op.drop_table("user_contest_rules")

    for tbl, cols in (
        ("style_presets", ("default_composition", "default_lighting", "default_color")),
        ("painting_intent_examples", ("preset_version",)),
        ("article_image_slots", ("image_provider", "style_preset_version")),
        ("contest_packs", ("word_count_includes",)),
        ("articles", ("submission_info",)),
    ):
        if not _has_table(bind, tbl):
            continue
        with op.batch_alter_table(tbl) as batch_op:
            for c in cols:
                if _has_column(bind, tbl, c):
                    batch_op.drop_column(c)
