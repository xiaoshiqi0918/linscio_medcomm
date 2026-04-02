"""add_image_prompt_templates

Revision ID: 7a8b9c0d1e2f
Revises: 5445fadf6db6
Create Date: 2026-03-22

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '7a8b9c0d1e2f'
down_revision: Union[str, Sequence[str], None] = '5445fadf6db6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('image_prompt_templates',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('name', sa.String(length=200), nullable=True),
        sa.Column('content_format', sa.String(length=30), nullable=True),
        sa.Column('style', sa.String(length=30), nullable=True),
        sa.Column('prompt_template', sa.Text(), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('is_system', sa.Boolean(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    op.drop_table('image_prompt_templates')
