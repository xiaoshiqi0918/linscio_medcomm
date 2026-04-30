"""add contest packs, painting intent, image slots, article contest fields

Revision ID: s3t4u5v6w7x8
Revises: abd15048dbf2
Create Date: 2026-04-29

与其它环境兼容：`init_db()` 中的 `metadata.create_all` 可能已抢先创建赛制相关表但未给 `articles`
增列；本脚本对「表已存在」「列已有」两种情况均幂等处理。
"""
from alembic import op
import sqlalchemy as sa

revision = "s3t4u5v6w7x8"
down_revision = "abd15048dbf2"
branch_labels = None
depends_on = None


def _has_table(bind, name: str) -> bool:
    return name in sa.inspect(bind).get_table_names()


def _has_column(bind, table: str, col: str) -> bool:
    return any(c["name"] == col for c in sa.inspect(bind).get_columns(table))


def _ensure_index(bind, ix_name: str, table_name: str, columns: tuple[str, ...]):
    ix = sa.inspect(bind).get_indexes(table_name)
    if any(ix_name == x["name"] for x in ix):
        return
    op.create_index(ix_name, table_name, list(columns))


def upgrade() -> None:
    bind = op.get_bind()

    if not _has_table(bind, "contest_packs"):
        op.create_table(
            "contest_packs",
            sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
            sa.Column("name", sa.String(200), nullable=False),
            sa.Column("organizer", sa.String(200), nullable=True),
            sa.Column("level", sa.String(30), nullable=True),
            sa.Column("source_url", sa.Text, nullable=True),
            sa.Column("source_note", sa.Text, nullable=True),
            sa.Column("is_active", sa.Boolean, default=True),
            sa.Column("word_limit", sa.Integer, nullable=True),
            sa.Column("font", sa.String(100), nullable=True),
            sa.Column("file_format", sa.String(50), nullable=True),
            sa.Column("naming_template", sa.String(500), nullable=True),
            sa.Column("deadline", sa.DateTime, nullable=True),
            sa.Column("ai_disclosure", sa.String(20), nullable=True),
            sa.Column("image_format", sa.String(50), nullable=True),
            sa.Column("layout_preference", sa.String(30), nullable=True),
            sa.Column("extra_rules", sa.JSON, nullable=True),
            sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
        )

    if not _has_table(bind, "contest_rules"):
        op.create_table(
            "contest_rules",
            sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
            sa.Column("contest_pack_id", sa.Integer, nullable=True),
            sa.Column("article_id", sa.Integer, nullable=True),
            sa.Column("rule_key", sa.String(100), nullable=False),
            sa.Column("rule_value", sa.Text, nullable=True),
            sa.Column("source", sa.String(20), nullable=False, server_default="manual"),
            sa.Column("confidence", sa.String(20), nullable=True),
            sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        )
        _ensure_index(bind, "ix_contest_rules_pack_id", "contest_rules", ("contest_pack_id",))
        _ensure_index(bind, "ix_contest_rules_article_id", "contest_rules", ("article_id",))

    if not _has_table(bind, "style_presets"):
        op.create_table(
            "style_presets",
            sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
            sa.Column("name", sa.String(50), nullable=False, unique=True),
            sa.Column("display_name", sa.String(100), nullable=False),
            sa.Column("description", sa.Text, nullable=True),
            sa.Column("prompt_template_zh", sa.JSON, nullable=True),
            sa.Column("prompt_template_en", sa.JSON, nullable=True),
            sa.Column("negative_words", sa.JSON, nullable=True),
            sa.Column("quality_tags_zh", sa.Text, nullable=True),
            sa.Column("quality_tags_en", sa.Text, nullable=True),
            sa.Column("medium_zh", sa.String(100), nullable=True),
            sa.Column("medium_en", sa.String(100), nullable=True),
            sa.Column("version", sa.Integer, default=1),
            sa.Column("is_active", sa.Boolean, default=True),
            sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
        )

    if not _has_table(bind, "painting_intent_examples"):
        op.create_table(
            "painting_intent_examples",
            sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
            sa.Column("topic_category", sa.String(50), nullable=False),
            sa.Column("style_preset_id", sa.Integer, nullable=True),
            sa.Column("intent_text", sa.Text, nullable=False),
            sa.Column("scene_description", sa.Text, nullable=True),
            sa.Column("is_active", sa.Boolean, default=True),
            sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        )
        _ensure_index(bind, "ix_painting_intent_topic", "painting_intent_examples", ("topic_category",))
        _ensure_index(bind, "ix_painting_intent_style", "painting_intent_examples", ("style_preset_id",))

    if not _has_table(bind, "negative_word_sets"):
        op.create_table(
            "negative_word_sets",
            sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
            sa.Column("category", sa.String(30), nullable=False),
            sa.Column("scope", sa.String(20), nullable=False, server_default="global"),
            sa.Column("topic_category", sa.String(50), nullable=True),
            sa.Column("words_zh", sa.JSON, nullable=True),
            sa.Column("words_en", sa.JSON, nullable=True),
            sa.Column("is_active", sa.Boolean, default=True),
            sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
        )

    if not _has_table(bind, "article_image_slots"):
        op.create_table(
            "article_image_slots",
            sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
            sa.Column("article_id", sa.Integer, sa.ForeignKey("articles.id"), nullable=False),
            sa.Column("section_id", sa.Integer, sa.ForeignKey("article_sections.id"), nullable=True),
            sa.Column("order_num", sa.Integer, default=1),
            sa.Column("intent_text", sa.Text, nullable=True),
            sa.Column("aspect_ratio", sa.String(10), nullable=True),
            sa.Column("style_preset_id", sa.Integer, nullable=True),
            sa.Column("prompt_zh", sa.Text, nullable=True),
            sa.Column("prompt_en", sa.Text, nullable=True),
            sa.Column("negative_words", sa.Text, nullable=True),
            sa.Column("image_path", sa.String(500), nullable=True),
            sa.Column("image_status", sa.String(20), server_default="empty"),
            sa.Column("user_adjustments", sa.JSON, nullable=True),
            sa.Column("prompt_version", sa.Integer, default=0),
            sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
        )
        _ensure_index(bind, "ix_image_slots_article", "article_image_slots", ("article_id",))
        _ensure_index(bind, "ix_image_slots_section", "article_image_slots", ("section_id",))

    cols_to_add = []
    if not _has_column(bind, "articles", "contest_pack_id"):
        cols_to_add.append(("contest_pack_id", sa.Integer, {"nullable": True}))
    if not _has_column(bind, "articles", "contest_rule_source"):
        cols_to_add.append(("contest_rule_source", sa.String(20), {"nullable": True}))
    if not _has_column(bind, "articles", "contest_custom_rules"):
        cols_to_add.append(("contest_custom_rules", sa.JSON, {"nullable": True}))
    if not _has_column(bind, "articles", "ai_declaration"):
        cols_to_add.append(("ai_declaration", sa.JSON, {"nullable": True}))

    if cols_to_add:
        with op.batch_alter_table("articles") as batch_op:
            for name, typ, kw in cols_to_add:
                batch_op.add_column(sa.Column(name, typ, **kw))


def downgrade() -> None:
    bind = op.get_bind()
    cols = []
    for c in ("ai_declaration", "contest_custom_rules", "contest_rule_source", "contest_pack_id"):
        if _has_column(bind, "articles", c):
            cols.append(c)
    if cols:
        with op.batch_alter_table("articles") as batch_op:
            for c in cols:
                batch_op.drop_column(c)

    for t in ("article_image_slots", "negative_word_sets", "painting_intent_examples", "style_presets", "contest_rules", "contest_packs"):
        if _has_table(bind, t):
            op.drop_table(t)
