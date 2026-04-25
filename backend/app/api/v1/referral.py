"""
推广系统接口（SaaS 模式独有）
- 获取/重置推广码
- 推广统计 / 奖励明细
- 推广积分兑现申请
"""
import logging
from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.config import settings
from app.core.deps import get_current_user
from app.models.user import User, _generate_referral_code
from app.models.referral import ReferralLog, WithdrawalLog

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/referral", tags=["推广"])


class ReferralInfo(BaseModel):
    referral_code: str
    referral_link: str
    total_referred: int
    total_reward_credits: float


class ReferralDetail(BaseModel):
    id: int
    referred_display_name: str
    trigger_type: str
    reward_credits: float
    created_at: str


@router.get("/info", response_model=ReferralInfo)
async def get_referral_info(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取当前用户的推广码和推广统计"""
    code = user.referral_code
    if not code:
        code = _generate_referral_code()
        user.referral_code = code
        await db.commit()

    total_q = await db.execute(
        select(func.count()).select_from(ReferralLog)
        .where(ReferralLog.referrer_id == user.id)
    )
    total_referred = total_q.scalar() or 0

    reward_q = await db.execute(
        select(func.sum(ReferralLog.reward_credits))
        .where(ReferralLog.referrer_id == user.id)
    )
    total_reward = float(reward_q.scalar() or 0)

    return ReferralInfo(
        referral_code=code,
        referral_link=f"https://www.linscio.com/register?ref={code}",
        total_referred=total_referred,
        total_reward_credits=round(total_reward, 2),
    )


@router.post("/reset-code")
async def reset_referral_code(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """重新生成推广码"""
    new_code = _generate_referral_code()
    user.referral_code = new_code
    await db.commit()
    return {
        "referral_code": new_code,
        "referral_link": f"https://www.linscio.com/register?ref={new_code}",
    }


@router.get("/details", response_model=list[ReferralDetail])
async def get_referral_details(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取推广奖励明细"""
    result = await db.execute(
        select(ReferralLog)
        .where(ReferralLog.referrer_id == user.id)
        .order_by(desc(ReferralLog.created_at))
        .limit(100)
    )
    logs = result.scalars().all()

    details = []
    for log in logs:
        referred = await db.get(User, log.referred_id)
        details.append(ReferralDetail(
            id=log.id,
            referred_display_name=referred.display_name if referred else "未知用户",
            trigger_type=log.trigger_type,
            reward_credits=float(log.reward_credits or 0),
            created_at=log.created_at.isoformat() if log.created_at else "",
        ))

    return details


# ══════════════════════════════════════════════════════════════
#  推广积分兑现
# ══════════════════════════════════════════════════════════════

class WithdrawRequest(BaseModel):
    credits_amount: float = Field(..., gt=0, description="兑现积分数量")
    real_name: str = Field(..., min_length=2, max_length=64)
    id_card: str = Field(..., min_length=15, max_length=32)
    bank_account: str = Field(..., min_length=10, max_length=64, description="收款账号（银行卡/支付宝）")


class WithdrawItem(BaseModel):
    id: int
    credits_used: float
    amount_yuan: float
    status: str
    created_at: str
    reviewed_at: str | None
    paid_at: str | None
    note: str | None


@router.post("/withdraw")
async def apply_withdraw(
    req: WithdrawRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """申请推广积分兑现（≥1000积分，按 1积分=0.08元 折算）"""
    credits = Decimal(str(req.credits_amount))
    min_wd = Decimal(str(settings.promo_min_withdraw))
    if credits < min_wd:
        raise HTTPException(400, f"最低兑现 {min_wd} 推广积分")

    promo = Decimal(str(user.promo_credits or 0))
    if promo < credits:
        raise HTTPException(400, f"推广积分不足，当前 {promo}")

    pending_q = await db.execute(
        select(func.count()).select_from(WithdrawalLog)
        .where(WithdrawalLog.user_id == user.id, WithdrawalLog.status == "pending")
    )
    if (pending_q.scalar() or 0) > 0:
        raise HTTPException(400, "您有一笔待审核的兑现申请，请等待处理完成")

    cash_rate = Decimal(str(settings.promo_cash_rate))
    amount_yuan = (credits * cash_rate).quantize(Decimal("0.01"))

    user.promo_credits = promo - credits

    wl = WithdrawalLog(
        user_id=user.id,
        credits_used=credits,
        amount_yuan=amount_yuan,
        real_name=req.real_name,
        id_card=req.id_card,
        bank_account=req.bank_account,
        status="pending",
    )
    db.add(wl)
    await db.commit()
    await db.refresh(wl)

    logger.info("兑现申请: user=%d credits=%s yuan=%s", user.id, credits, amount_yuan)
    return {
        "id": wl.id,
        "credits_used": float(credits),
        "amount_yuan": float(amount_yuan),
        "status": "pending",
        "message": f"申请已提交，预计到账 ¥{amount_yuan}（1积分={cash_rate}元），请等待人工审核",
    }


@router.get("/withdrawals", response_model=list[WithdrawItem])
async def list_withdrawals(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """查看我的兑现记录"""
    result = await db.execute(
        select(WithdrawalLog)
        .where(WithdrawalLog.user_id == user.id)
        .order_by(desc(WithdrawalLog.created_at))
        .limit(50)
    )
    rows = result.scalars().all()
    return [
        WithdrawItem(
            id=w.id,
            credits_used=float(w.credits_used),
            amount_yuan=float(w.amount_yuan),
            status=w.status,
            created_at=w.created_at.isoformat() if w.created_at else "",
            reviewed_at=w.reviewed_at.isoformat() if w.reviewed_at else None,
            paid_at=w.paid_at.isoformat() if w.paid_at else None,
            note=w.note,
        )
        for w in rows
    ]
