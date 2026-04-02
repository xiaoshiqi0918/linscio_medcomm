"""add_example_source_medical_reviewed

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-03-22

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c3d4e5f6a7b8'
down_revision: Union[str, Sequence[str], None] = 'b2c3d4e5f6a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('writing_examples', sa.Column('source_doc', sa.String(length=200), nullable=True))
    op.add_column('writing_examples', sa.Column('medical_reviewed', sa.Integer(), nullable=True, server_default='0'))


def downgrade() -> None:
    op.drop_column('writing_examples', 'medical_reviewed')
    op.drop_column('writing_examples', 'source_doc')
