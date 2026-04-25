"""
用户模型 — 双模式
桌面端只使用 id/display_name/email/created_at/updated_at，其余字段 SaaS 使用。
"""
import secrets
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Column, Integer, String, Boolean, DateTime, Numeric, ForeignKey, func
from app.models import Base
from app.core.config import settings


def _generate_referral_code() -> str:
    return secrets.token_urlsafe(6)[:8]


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # ── 原有字段（桌面端核心）──────────────────────────────
    display_name = Column(String(100), nullable=True)
    email = Column(String(255), nullable=True)

    # ── SaaS 账号体系 ────────────────────────────────────
    phone = Column(String(20), unique=True, nullable=True, index=True)
    password_hash = Column(String(255), nullable=True)
    is_banned = Column(Boolean, default=False, server_default="false")
    is_admin = Column(Boolean, default=False, server_default="false")
    last_login_at = Column(DateTime(timezone=True), nullable=True)

    # ── 积分体系 ──────────────────────────────────────────
    credits = Column(Numeric(10, 4), default=0, server_default="0")
    gift_credits = Column(
        Numeric(10, 4), default=settings.new_user_gift_credits,
        server_default=str(settings.new_user_gift_credits),
    )
    gift_credits_expire_at = Column(DateTime(timezone=True), nullable=True)
    promo_credits = Column(Numeric(10, 4), default=0, server_default="0")
    promo_credits_expire_at = Column(DateTime(timezone=True), nullable=True)
    frozen_credits = Column(Numeric(10, 4), default=0, server_default="0")
    free_generation_used = Column(Boolean, default=False, server_default="false")

    # ── 推广体系 ──────────────────────────────────────────
    referral_code = Column(String(8), unique=True, default=_generate_referral_code)
    referred_by = Column(Integer, ForeignKey("users.id"), nullable=True)

    # ── 统计 ──────────────────────────────────────────────
    total_recharged = Column(Numeric(10, 4), default=0, server_default="0")
    total_consumed = Column(Numeric(10, 4), default=0, server_default="0")

    # ── 管理 ──────────────────────────────────────────────
    admin_note = Column(Text, nullable=True)
    last_login_at = Column(DateTime(timezone=True), nullable=True)

    # ── 时间戳 ────────────────────────────────────────────
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())

    @property
    def total_available_credits(self) -> Decimal:
        """可用积分总额（含赠送和推广，排除冻结）"""
        from datetime import timezone
        now = datetime.now(timezone.utc)
        total = Decimal(str(self.credits or 0))
        gc = Decimal(str(self.gift_credits or 0))
        if gc > 0 and (not self.gift_credits_expire_at or self.gift_credits_expire_at > now):
            total += gc
        pc = Decimal(str(self.promo_credits or 0))
        if pc > 0 and (not self.promo_credits_expire_at or self.promo_credits_expire_at > now):
            total += pc
        return total - Decimal(str(self.frozen_credits or 0))
