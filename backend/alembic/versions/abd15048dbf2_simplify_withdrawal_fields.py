"""simplify_withdrawal_fields

Revision ID: abd15048dbf2
Revises: r2s3t4u5v6w7
Create Date: 2026-04-29 01:32:03.724170

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'abd15048dbf2'
down_revision: Union[str, Sequence[str], None] = 'r2s3t4u5v6w7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(name: str) -> bool:
    from alembic import op as _op
    conn = _op.get_bind()
    insp = sa.inspect(conn)
    return name in insp.get_table_names()


def upgrade() -> None:
    if not _table_exists("withdrawal_logs"):
        return
    op.add_column('withdrawal_logs', sa.Column('platform_account', sa.String(length=32), nullable=True))
    op.add_column('withdrawal_logs', sa.Column('wechat_phone', sa.String(length=20), nullable=True))
    op.drop_column('withdrawal_logs', 'bank_account')
    op.drop_column('withdrawal_logs', 'id_card')
    op.drop_column('withdrawal_logs', 'real_name')


def downgrade() -> None:
    if not _table_exists("withdrawal_logs"):
        return
    op.add_column('withdrawal_logs', sa.Column('real_name', sa.VARCHAR(length=64), autoincrement=False, nullable=True))
    op.add_column('withdrawal_logs', sa.Column('id_card', sa.VARCHAR(length=32), autoincrement=False, nullable=True))
    op.add_column('withdrawal_logs', sa.Column('bank_account', sa.VARCHAR(length=64), autoincrement=False, nullable=True))
    op.drop_column('withdrawal_logs', 'wechat_phone')
    op.drop_column('withdrawal_logs', 'platform_account')
