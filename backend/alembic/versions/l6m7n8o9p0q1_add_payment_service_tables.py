"""支付中台: payment_orders / refund_records / reconciliation_logs

Revision ID: l6m7n8o9p0q1
Revises: k5l6m7n8o9p0
Create Date: 2026-04-23
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "l6m7n8o9p0q1"
down_revision: Union[str, None] = "k5l6m7n8o9p0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "payment_orders",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("order_no", sa.String(64), unique=True, nullable=False),
        sa.Column("channel_code", sa.String(32), nullable=False),
        sa.Column("channel_order_id", sa.String(128), nullable=True),
        sa.Column("amount_yuan", sa.Numeric(10, 2), nullable=False),
        sa.Column("credits_to_add", sa.Numeric(10, 4), nullable=False),
        sa.Column("bonus_credits", sa.Numeric(10, 4), server_default="0"),
        sa.Column("pay_method", sa.String(20), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="created"),
        sa.Column("notify_raw", sa.JSON(), nullable=True),
        sa.Column("client_ip", sa.String(64), nullable=True),
        sa.Column("user_agent", sa.String(256), nullable=True),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expired_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("refunded_amount", sa.Numeric(10, 2), server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("idx_po_user_created", "payment_orders", ["user_id", "created_at"])
    op.create_index("idx_po_status", "payment_orders", ["status"])
    op.create_index("idx_po_channel", "payment_orders", ["channel_code", "status"])

    op.create_table(
        "refund_records",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("order_id", sa.Integer(), sa.ForeignKey("payment_orders.id"), nullable=False),
        sa.Column("refund_no", sa.String(64), unique=True, nullable=False),
        sa.Column("channel_refund_id", sa.String(128), nullable=True),
        sa.Column("refund_amount_yuan", sa.Numeric(10, 2), nullable=False),
        sa.Column("credits_deducted", sa.Numeric(10, 4), nullable=False, server_default="0"),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("operator", sa.String(64), nullable=True, server_default="system"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("idx_refund_order", "refund_records", ["order_id"])

    op.create_table(
        "reconciliation_logs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("bill_date", sa.Date(), nullable=False),
        sa.Column("channel_code", sa.String(32), nullable=False),
        sa.Column("total_orders", sa.Integer(), server_default="0"),
        sa.Column("matched_orders", sa.Integer(), server_default="0"),
        sa.Column("mismatched_orders", sa.Integer(), server_default="0"),
        sa.Column("total_amount", sa.Numeric(12, 2), server_default="0"),
        sa.Column("matched_amount", sa.Numeric(12, 2), server_default="0"),
        sa.Column("diff_amount", sa.Numeric(12, 2), server_default="0"),
        sa.Column("details", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("idx_recon_date_channel", "reconciliation_logs", ["bill_date", "channel_code"])


def downgrade() -> None:
    op.drop_table("reconciliation_logs")
    op.drop_table("refund_records")
    op.drop_table("payment_orders")
