"""
推广与兑现模型 — referral_logs / withdrawal_logs
仅 SaaS 模式使用。
"""
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Column, String, Text, DateTime, Integer, Numeric, ForeignKey, func
from app.models import Base


class ReferralLog(Base):
    """推广记录"""
    __tablename__ = "referral_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    referrer_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    referred_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    trigger_type = Column(String(20), nullable=False)
    related_recharge_id = Column(Integer, nullable=True)
    reward_credits = Column(Numeric(10, 4), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class WithdrawalLog(Base):
    """兑现记录"""
    __tablename__ = "withdrawal_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    credits_used = Column(Numeric(10, 4), nullable=False)
    amount_yuan = Column(Numeric(10, 2), nullable=False)
    real_name = Column(String(64), nullable=True)
    id_card = Column(String(32), nullable=True)
    bank_account = Column(String(64), nullable=True)
    status = Column(String(20), nullable=False, server_default="pending")
    reviewed_by = Column(Integer, nullable=True)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    paid_at = Column(DateTime(timezone=True), nullable=True)
    note = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
