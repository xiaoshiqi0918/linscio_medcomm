"""add medpic_generations table

Revision ID: a0b1c2d3e4f5
Revises: d9e0f1a2b3c4
Create Date: 2026-04-04

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a0b1c2d3e4f5"
down_revision: Union[str, Sequence[str], None] = "d9e0f1a2b3c4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "medpic_generations",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer, default=1),
        sa.Column("variant_id", sa.String(30), nullable=True),
        sa.Column("scene", sa.String(30)),
        sa.Column("style", sa.String(50)),
        sa.Column("hardware_tier", sa.String(20)),
        sa.Column("topic", sa.Text),
        sa.Column("specialty", sa.String(50), nullable=True),
        sa.Column("positive_prompt", sa.Text),
        sa.Column("negative_prompt", sa.Text, nullable=True),
        sa.Column("seed", sa.Integer, nullable=True),
        sa.Column("seed_mode", sa.String(20), nullable=True),
        sa.Column("model_id", sa.String(50), nullable=True),
        sa.Column("loras", sa.JSON, nullable=True),
        sa.Column("width", sa.Integer, nullable=True),
        sa.Column("height", sa.Integer, nullable=True),
        sa.Column("output_width", sa.Integer, nullable=True),
        sa.Column("output_height", sa.Integer, nullable=True),
        sa.Column("base_image_path", sa.String(500)),
        sa.Column("composed_image_path", sa.String(500), nullable=True),
        sa.Column("upscaled_image_path", sa.String(500), nullable=True),
        sa.Column("ipadapter_weight", sa.Float, nullable=True),
        sa.Column("character_preset", sa.String(50), nullable=True),
        sa.Column("reference_image_path", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_medpic_gen_scene", "medpic_generations", ["scene"])
    op.create_index("ix_medpic_gen_created", "medpic_generations", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_medpic_gen_created", table_name="medpic_generations")
    op.drop_index("ix_medpic_gen_scene", table_name="medpic_generations")
    op.drop_table("medpic_generations")
