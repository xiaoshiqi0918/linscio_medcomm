"""add specialty_packages table (设计 2.2 软件端)

学科包状态表，用于 MedComm 桌面端本地跟踪下载/安装状态
崩溃恢复：status='downloading' AND download_started_at < NOW()-30分钟 → 重置为 not_installed

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-03-22

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'e5f6a7b8c9d0'
down_revision: Union[str, Sequence[str], None] = 'd4e5f6a7b8c9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'specialty_packages',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('specialty_id', sa.String(length=50), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('local_version', sa.String(length=20), nullable=True),
        sa.Column('remote_version', sa.String(length=20), nullable=True),
        sa.Column('status', sa.String(length=20), server_default='not_installed', nullable=True),
        sa.Column('download_progress', sa.Integer(), server_default='0', nullable=True),
        sa.Column('download_tmp_path', sa.Text(), nullable=True),
        sa.Column('download_offset', sa.Integer(), server_default='0', nullable=True),
        sa.Column('download_started_at', sa.DateTime(), nullable=True),
        sa.Column('last_checked_at', sa.DateTime(), nullable=True),
        sa.Column('installed_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('specialty_id', name='uq_specialty_packages_specialty_id')
    )
    op.create_index('ix_specialty_packages_specialty_id', 'specialty_packages', ['specialty_id'])


def downgrade() -> None:
    op.drop_index('ix_specialty_packages_specialty_id', table_name='specialty_packages')
    op.drop_table('specialty_packages')
