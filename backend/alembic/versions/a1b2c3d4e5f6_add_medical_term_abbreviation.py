"""add medical_term abbreviation and specialty

Revision ID: a1b2c3d4e5f6
Revises: 7a8b9c0d1e2f
Create Date: 2026-03-22

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = '7a8b9c0d1e2f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('medical_terms', sa.Column('abbreviation', sa.String(length=30), nullable=True))
    op.add_column('medical_terms', sa.Column('specialty', sa.String(length=50), nullable=True))


def downgrade() -> None:
    op.drop_column('medical_terms', 'specialty')
    op.drop_column('medical_terms', 'abbreviation')
