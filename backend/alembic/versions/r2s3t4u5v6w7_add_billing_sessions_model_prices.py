"""add billing_sessions, model_prices tables; llm_call_logs edge-case fields

Revision ID: r2s3t4u5v6w7
Revises: q1r2s3t4u5v6
Create Date: 2026-04-28
"""
from alembic import op
import sqlalchemy as sa

revision = "r2s3t4u5v6w7"
down_revision = "q1r2s3t4u5v6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── model_prices ──
    op.create_table(
        "model_prices",
        sa.Column("model", sa.String(100), primary_key=True),
        sa.Column("provider", sa.String(50), nullable=True),
        sa.Column("price_in_per_mtok", sa.Numeric(10, 6), nullable=False),
        sa.Column("price_out_per_mtok", sa.Numeric(10, 6), nullable=False),
        sa.Column("markup_ratio", sa.Numeric(6, 2), nullable=False, server_default="8.0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("effective_from", sa.DateTime(timezone=True), nullable=True),
        sa.Column("effective_to", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ── billing_sessions ──
    op.create_table(
        "billing_sessions",
        sa.Column("session_id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("business_type", sa.String(64), nullable=False),
        sa.Column("business_ref", sa.JSON(), nullable=True),
        sa.Column("idempotency_key", sa.String(64), nullable=True),
        sa.Column("estimated_cost", sa.Numeric(10, 4), nullable=False),
        sa.Column("actual_cost", sa.Numeric(10, 4), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("settled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_activity_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("idx_bs_user_status", "billing_sessions", ["user_id", "status"])
    op.create_index("idx_bs_status_activity", "billing_sessions", ["status", "last_activity_at"])
    try:
        op.create_unique_constraint("uq_bs_user_idempotency", "billing_sessions", ["user_id", "idempotency_key"])
    except Exception:
        pass

    # ── llm_call_logs: add billing_session_id + edge-case fields ──
    # Use batch mode for SQLite (no ALTER ADD CONSTRAINT support)
    with op.batch_alter_table("llm_call_logs") as batch_op:
        batch_op.add_column(sa.Column(
            "billing_session_id", sa.String(36),
            sa.ForeignKey("billing_sessions.session_id", name="fk_llm_billing_session"),
            nullable=True,
        ))
        batch_op.add_column(sa.Column("cost_billable", sa.Boolean(), nullable=False, server_default="true"))
        batch_op.add_column(sa.Column("tokens_in_reported", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("tokens_out_reported", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("token_source", sa.String(20), server_default="estimated"))
    op.create_index("idx_llm_billing_session", "llm_call_logs", ["billing_session_id"])

    # ── seed model_prices with current pricing ──
    op.execute("""
        INSERT INTO model_prices (model, provider, price_in_per_mtok, price_out_per_mtok, markup_ratio) VALUES
        ('gpt-4o',                   'openai',    2.500000, 10.000000, 8.00),
        ('gpt-4o-mini',              'openai',    0.150000,  0.600000, 8.00),
        ('gemini-3.1-pro-preview',   'google',    1.250000, 10.000000, 8.00),
        ('gemini-2.5-flash',         'google',    0.075000,  0.300000, 8.00),
        ('deepseek-chat',            'deepseek',  0.270000,  1.100000, 8.00),
        ('deepseek-reasoner',        'deepseek',  0.550000,  2.190000, 8.00),
        ('kimi-k2.5',               'moonshot',   0.550000,  2.000000, 8.00),
        ('kimi-k2-turbo-preview',   'moonshot',   0.200000,  0.600000, 8.00),
        ('qwen-plus',               'alibaba',    0.800000,  2.000000, 8.00),
        ('qwen-turbo',              'alibaba',    0.300000,  0.600000, 8.00),
        ('qwen-max',                'alibaba',    2.400000,  9.600000, 8.00),
        ('glm-4-flash',             'zhipu',      0.100000,  0.100000, 8.00),
        ('glm-4.7',                 'zhipu',      0.500000,  0.500000, 8.00)
        ON CONFLICT (model) DO NOTHING
    """)


def downgrade() -> None:
    op.drop_index("idx_llm_billing_session", table_name="llm_call_logs")
    op.drop_column("llm_call_logs", "token_source")
    op.drop_column("llm_call_logs", "tokens_out_reported")
    op.drop_column("llm_call_logs", "tokens_in_reported")
    op.drop_column("llm_call_logs", "cost_billable")
    op.drop_column("llm_call_logs", "billing_session_id")
    op.drop_constraint("uq_bs_user_idempotency", "billing_sessions", type_="unique")
    op.drop_index("idx_bs_status_activity", table_name="billing_sessions")
    op.drop_index("idx_bs_user_status", table_name="billing_sessions")
    op.drop_table("billing_sessions")
    op.drop_table("model_prices")
