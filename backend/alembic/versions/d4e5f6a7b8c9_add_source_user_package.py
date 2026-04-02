"""add source user/package to medical_terms and writing_examples

设计 2.2：source='user' 用户自建；source='package' 学科包导入
学科包更新时只删 source='package' 记录，不覆盖用户数据

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-03-22

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'd4e5f6a7b8c9'
down_revision: Union[str, Sequence[str], None] = 'c3d4e5f6a7b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'medical_terms',
        sa.Column('source', sa.String(length=20), nullable=True, server_default='user')
    )
    op.add_column(
        'writing_examples',
        sa.Column('source', sa.String(length=20), nullable=True, server_default='user')
    )


def downgrade() -> None:
    op.drop_column('writing_examples', 'source')
    op.drop_column('medical_terms', 'source')
