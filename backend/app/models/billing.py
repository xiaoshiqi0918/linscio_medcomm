"""
计费 / 任务 / 可观测性模型 — 仅 SaaS 模式创建和使用。
"""
from datetime import datetime, date
from decimal import Decimal
import uuid

from sqlalchemy import (
    Column, String, Boolean, Text, DateTime, Date, Integer, Numeric,
    ForeignKey, Index, UniqueConstraint, func, JSON,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from app.models import Base


class UsageLog(Base):
    """积分消费流水"""
    __tablename__ = "usage_logs"
    __table_args__ = (
        Index("idx_usage_user_created", "user_id", "created_at"),
        Index("idx_usage_operation", "operation", "created_at"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    article_id = Column(Integer, nullable=True)
    section_id = Column(Integer, nullable=True)
    operation = Column(String(64), nullable=False)
    cost = Column(Numeric(10, 4), nullable=False)
    breakdown = Column(JSON, nullable=True)
    meta = Column(JSON, nullable=True)
    aborted = Column(Boolean, default=False, server_default="false")
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class RechargeLog(Base):
    """充值记录"""
    __tablename__ = "recharge_logs"
    __table_args__ = (
        Index("idx_recharge_user", "user_id", "created_at"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    order_no = Column(String(64), unique=True, nullable=False)
    out_trade_no = Column(String(64), nullable=True)
    amount_yuan = Column(Numeric(10, 2), nullable=False)
    credits_added = Column(Numeric(10, 4), nullable=False)
    bonus_credits = Column(Numeric(10, 4), default=0, server_default="0")
    status = Column(String(20), nullable=False)
    payment_method = Column(String(20), nullable=True)
    paid_at = Column(DateTime(timezone=True), nullable=True)
    refunded_at = Column(DateTime(timezone=True), nullable=True)
    refund_amount = Column(Numeric(10, 2), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class UserBalanceSnapshot(Base):
    """每日余额快照"""
    __tablename__ = "user_balance_snapshots"
    __table_args__ = (
        UniqueConstraint("user_id", "snapshot_date"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    snapshot_date = Column(Date, nullable=False)
    credits = Column(Numeric(10, 4), nullable=True)
    gift_credits = Column(Numeric(10, 4), nullable=True)
    promo_credits = Column(Numeric(10, 4), nullable=True)
    frozen_credits = Column(Numeric(10, 4), nullable=True)


class CompensationVoucher(Base):
    """质量补偿券"""
    __tablename__ = "compensation_vouchers"
    __table_args__ = (
        Index("idx_voucher_user", "user_id", "status"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    discount_rate = Column(Numeric(3, 2), nullable=False, server_default="0.50")
    max_uses = Column(Integer, nullable=False, server_default="3")
    used_count = Column(Integer, nullable=False, server_default="0")
    status = Column(String(20), nullable=False, server_default="active")
    reason = Column(Text, nullable=True)
    issued_by = Column(String(64), nullable=True, server_default="system")
    expire_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


# ── 兑换码 ────────────────────────────────────────────────────

class RedeemCode(Base):
    """积分兑换码（由管理员批量生成，用户输入兑换）"""
    __tablename__ = "redeem_codes"
    __table_args__ = (
        Index("idx_redeem_status", "status"),
        Index("idx_redeem_batch", "batch_id"),
        Index("idx_redeem_tier", "tier", "status"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(32), unique=True, nullable=False, index=True)
    tier = Column(Integer, nullable=False)
    credits = Column(Numeric(10, 4), nullable=False)
    bonus_credits = Column(Numeric(10, 4), default=0, server_default="0")
    status = Column(String(16), nullable=False, server_default="unused")
    batch_id = Column(String(32), nullable=True)
    created_by = Column(Integer, nullable=True)
    used_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    used_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


# ── 支付中台模型 ──────────────────────────────────────────────

class PaymentOrder(Base):
    """支付订单（替代/扩展 RechargeLog）"""
    __tablename__ = "payment_orders"
    __table_args__ = (
        Index("idx_po_user_created", "user_id", "created_at"),
        Index("idx_po_status", "status"),
        Index("idx_po_channel", "channel_code", "status"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    order_no = Column(String(64), unique=True, nullable=False)
    channel_code = Column(String(32), nullable=False)
    channel_order_id = Column(String(128), nullable=True)
    amount_yuan = Column(Numeric(10, 2), nullable=False)
    credits_to_add = Column(Numeric(10, 4), nullable=False)
    bonus_credits = Column(Numeric(10, 4), default=0, server_default="0")
    pay_method = Column(String(20), nullable=True)
    status = Column(String(20), nullable=False, server_default="created")
    notify_raw = Column(JSON, nullable=True)
    client_ip = Column(String(64), nullable=True)
    user_agent = Column(String(256), nullable=True)
    paid_at = Column(DateTime(timezone=True), nullable=True)
    expired_at = Column(DateTime(timezone=True), nullable=True)
    closed_at = Column(DateTime(timezone=True), nullable=True)
    refunded_amount = Column(Numeric(10, 2), default=0, server_default="0")
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class RefundRecord(Base):
    """退款记录"""
    __tablename__ = "refund_records"
    __table_args__ = (
        Index("idx_refund_order", "order_id"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    order_id = Column(Integer, ForeignKey("payment_orders.id"), nullable=False)
    refund_no = Column(String(64), unique=True, nullable=False)
    channel_refund_id = Column(String(128), nullable=True)
    refund_amount_yuan = Column(Numeric(10, 2), nullable=False)
    credits_deducted = Column(Numeric(10, 4), nullable=False, default=0, server_default="0")
    reason = Column(Text, nullable=True)
    status = Column(String(20), nullable=False, server_default="pending")
    operator = Column(String(64), nullable=True, server_default="system")
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)


class LicenseCode(Base):
    """客户端授权码"""
    __tablename__ = "license_codes"
    __table_args__ = (
        Index("idx_license_user", "owner_id"),
        UniqueConstraint("code", name="uq_license_code"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(32), nullable=False, unique=True, index=True)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    credit_type = Column(String(20), nullable=False, server_default="credits")
    credits_cost = Column(Numeric(10, 4), nullable=False, default=0)
    source = Column(String(20), nullable=False, server_default="redeem")
    is_used = Column(Boolean, default=False, server_default="false")
    used_by = Column(String(100), nullable=True)
    used_at = Column(DateTime(timezone=True), nullable=True)
    device_id = Column(String(128), nullable=True)
    device_info = Column(JSON, nullable=True)
    activated_at = Column(DateTime(timezone=True), nullable=True)
    last_unbound_at = Column(DateTime(timezone=True), nullable=True)
    note = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class DownloadLog(Base):
    """客户端下载记录"""
    __tablename__ = "download_logs"
    __table_args__ = (
        Index("idx_dl_user_created", "user_id", "created_at"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    product_id = Column(String(50), nullable=False, server_default="medcomm")
    version = Column(String(20), nullable=False)
    platform = Column(String(30), nullable=False)
    filename = Column(String(200), nullable=True)
    license_code_id = Column(Integer, nullable=True)
    client_ip = Column(String(45), nullable=True)
    user_agent = Column(String(300), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class ReconciliationLog(Base):
    """对账记录"""
    __tablename__ = "reconciliation_logs"
    __table_args__ = (
        Index("idx_recon_date_channel", "bill_date", "channel_code"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    bill_date = Column(Date, nullable=False)
    channel_code = Column(String(32), nullable=False)
    total_orders = Column(Integer, default=0)
    matched_orders = Column(Integer, default=0)
    mismatched_orders = Column(Integer, default=0)
    total_amount = Column(Numeric(12, 2), default=0)
    matched_amount = Column(Numeric(12, 2), default=0)
    diff_amount = Column(Numeric(12, 2), default=0)
    details = Column(JSON, nullable=True)
    status = Column(String(20), nullable=False, server_default="pending")
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


# ── 任务追踪 ──────────────────────────────────────────────────

class TaskRecord(Base):
    """异步任务追踪（文献分析、导出等长耗时操作）"""
    __tablename__ = "tasks"
    __table_args__ = (
        Index("idx_tasks_user_status", "user_id", "status", "created_at"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(String(64), unique=True, nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    task_type = Column(String(32), nullable=False)
    status = Column(String(20), nullable=False, server_default="pending")
    payload = Column(JSON, nullable=True)
    result = Column(JSON, nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)


# ── SSE 流式会话追踪 ──────────────────────────────────────────

class StreamingSession(Base):
    """SSE 流式生成会话，用于中断扣费结算"""
    __tablename__ = "streaming_sessions"
    __table_args__ = (
        Index("idx_streaming_status_heartbeat", "status", "last_heartbeat_at"),
    )

    session_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    article_id = Column(Integer, nullable=True)
    section_id = Column(Integer, nullable=True)
    task_type = Column(String(64), nullable=False)
    estimated_cost = Column(Numeric(10, 4), nullable=False)
    actual_tokens_in = Column(Integer, default=0, server_default="0")
    actual_tokens_out = Column(Integer, default=0, server_default="0")
    actual_cost = Column(Numeric(10, 4), nullable=True)
    status = Column(String(20), nullable=False, server_default="streaming")
    started_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)
    last_heartbeat_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


# ── 管理员操作审计 ─────────────────────────────────────────────

class AdminAuditLog(Base):
    """后台管理员操作审计日志"""
    __tablename__ = "admin_audit_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    admin_id = Column(Integer, nullable=False)
    action = Column(String(64), nullable=False)
    target_user_id = Column(Integer, nullable=True)
    payload = Column(JSON, nullable=True)
    reason = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


# ── 模型定价 ───────────────────────────────────────────────────

class ModelPrice(Base):
    """LLM 模型定价表 — 数据库驱动，改价无需发版"""
    __tablename__ = "model_prices"

    model = Column(String(100), primary_key=True)
    provider = Column(String(50), nullable=True)
    price_in_per_mtok = Column(Numeric(10, 6), nullable=False)
    price_out_per_mtok = Column(Numeric(10, 6), nullable=False)
    markup_ratio = Column(Numeric(6, 2), nullable=False, server_default="8.0")
    is_active = Column(Boolean, nullable=False, server_default="true")
    effective_from = Column(DateTime(timezone=True), nullable=True)
    effective_to = Column(DateTime(timezone=True), nullable=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


# ── 计费会话 ───────────────────────────────────────────────────

class BillingSession(Base):
    """计费会话 — 一个用户感知的原子操作（生成/分析/翻译/润色等）"""
    __tablename__ = "billing_sessions"
    __table_args__ = (
        Index("idx_bs_user_status", "user_id", "status"),
        Index("idx_bs_status_activity", "status", "last_activity_at"),
        UniqueConstraint("user_id", "idempotency_key", name="uq_bs_user_idempotency"),
    )

    session_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    business_type = Column(String(64), nullable=False)
    business_ref = Column(JSON, nullable=True)
    idempotency_key = Column(String(64), nullable=True)
    estimated_cost = Column(Numeric(10, 4), nullable=False)
    actual_cost = Column(Numeric(10, 4), nullable=True)
    status = Column(String(20), nullable=False, server_default="pending")
    started_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    settled_at = Column(DateTime(timezone=True), nullable=True)
    last_activity_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


# ── LLM 调用埋点 ──────────────────────────────────────────────

class LlmCallLog(Base):
    """LLM 调用埋点（可观测性 & 成本核算）"""
    __tablename__ = "llm_call_logs"
    __table_args__ = (
        Index("idx_llm_call_user_created", "user_id", "created_at"),
        Index("idx_llm_call_model", "model", "created_at"),
        Index("idx_llm_call_task", "task_type", "created_at"),
        Index("idx_llm_billing_session", "billing_session_id"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    article_id = Column(Integer, nullable=True)
    section_id = Column(Integer, nullable=True)
    session_id = Column(String(36), nullable=True)
    billing_session_id = Column(String(36), ForeignKey("billing_sessions.session_id"), nullable=True)
    task_type = Column(String(64), nullable=False)
    model = Column(String(100), nullable=False)
    provider = Column(String(50), nullable=True)
    tokens_in = Column(Integer, default=0)
    tokens_out = Column(Integer, default=0)
    tokens_in_reported = Column(Integer, nullable=True)
    tokens_out_reported = Column(Integer, nullable=True)
    token_source = Column(String(20), server_default="estimated")
    latency_ms = Column(Integer, nullable=True)
    cost_usd = Column(Numeric(10, 6), nullable=True)
    cost_credits = Column(Numeric(10, 4), nullable=True)
    cost_billable = Column(Boolean, nullable=False, server_default="true")
    status = Column(String(20), nullable=False, server_default="success")
    error_message = Column(Text, nullable=True)
    meta = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


# ── 内容审核日志 ──────────────────────────────────────────────

class ContentModerationLog(Base):
    """内容审核记录 — 三层审核（入口/生成/导出）"""
    __tablename__ = "content_moderation_logs"
    __table_args__ = (
        Index("idx_moderation_user", "user_id", "created_at"),
        Index("idx_moderation_stage", "stage", "rule_level", "created_at"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    article_id = Column(Integer, nullable=True)
    section_id = Column(Integer, nullable=True)
    stage = Column(String(20), nullable=False)           # input / generation / export
    rule_level = Column(String(20), nullable=False)      # block / warn / info
    matched_rule = Column(String(128), nullable=True)    # 命中的规则名
    snippet = Column(Text, nullable=True)                # 命中片段（脱敏）
    action_taken = Column(String(32), nullable=False, server_default="blocked")  # blocked / passed_with_warning / user_confirmed
    meta = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
