"""
支付 API（SaaS 模式独有）— 薄路由层
所有业务逻辑委托给 PaymentService，此处仅做参数解析与权限校验。
"""
import logging
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.services.payment.service import payment_service
from app.services.payment.registry import list_channels

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/payment", tags=["支付"])


# ── 请求/响应模型 ─────────────────────────────────────────

class CreateOrderRequest(BaseModel):
    amount_yuan: int = Field(..., description="充值金额（元）")
    pay_type: str = Field("alipay", description="支付方式: alipay / wxpay")
    channel_code: str = Field("yipay", description="支付渠道: yipay / alipay / wechatpay")


class CreateOrderResponse(BaseModel):
    order_no: str
    qrcode: str
    pay_url: str
    amount_yuan: int
    credits: int
    bonus: int


class OrderStatusResponse(BaseModel):
    order_no: str
    status: str
    amount_yuan: str
    credits_to_add: float
    bonus_credits: float
    paid_at: str | None = None
    created_at: str | None = None


class CloseOrderRequest(BaseModel):
    order_no: str


class RefundRequest(BaseModel):
    order_no: str
    refund_amount_yuan: float | None = None
    reason: str = ""


class OrderListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[dict]


# ── API 端点 ──────────────────────────────────────────────

@router.get("/channels")
async def get_available_channels():
    """获取当前可用的支付渠道列表"""
    return {"channels": list_channels()}


@router.post("/create-order", response_model=CreateOrderResponse)
async def create_order(
    req: CreateOrderRequest,
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from app.core.rate_limit import check_recharge_rate
    await check_recharge_rate(user.id)

    client_ip = request.client.host if request.client else "127.0.0.1"
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        client_ip = forwarded.split(",")[0].strip()

    user_agent = request.headers.get("user-agent", "")

    try:
        result = await payment_service.create_order(
            user_id=user.id,
            amount_yuan=req.amount_yuan,
            channel_code=req.channel_code,
            pay_method=req.pay_type,
            client_ip=client_ip,
            db=db,
            user_agent=user_agent,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if not result["success"]:
        raise HTTPException(status_code=502, detail=result.get("error", "支付下单失败"))

    return CreateOrderResponse(
        order_no=result["order_no"],
        qrcode=result.get("qrcode", ""),
        pay_url=result.get("pay_page_url", ""),
        amount_yuan=req.amount_yuan,
        credits=result["credits"],
        bonus=result["bonus"],
    )


@router.get("/notify/{channel_code}", response_class=PlainTextResponse)
async def payment_notify(
    channel_code: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """渠道异步回调（按渠道区分 URL）"""
    params = dict(request.query_params)
    logger.info("收到支付回调: channel=%s params=%s", channel_code, params)
    return await payment_service.handle_callback(channel_code, params, db)


@router.get("/notify", response_class=PlainTextResponse)
async def payment_notify_default(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """兼容旧的不带渠道的回调 URL"""
    params = dict(request.query_params)
    logger.info("收到支付回调(默认): params=%s", params)
    return await payment_service.handle_callback("yipay", params, db)


@router.get("/order-status", response_model=OrderStatusResponse)
async def get_order_status(
    order_no: str = Query(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """前端轮询订单状态（自动同步渠道侧状态）"""
    result = await payment_service.query_and_sync(order_no, user.id, db)
    if not result.get("found"):
        raise HTTPException(status_code=404, detail="订单不存在")

    return OrderStatusResponse(
        order_no=result["order_no"],
        status=result["status"],
        amount_yuan=result["amount_yuan"],
        credits_to_add=result["credits_to_add"],
        bonus_credits=result["bonus_credits"],
        paid_at=result.get("paid_at"),
        created_at=result.get("created_at"),
    )


@router.post("/close")
async def close_order(
    req: CloseOrderRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """用户取消未支付订单"""
    result = await payment_service.close_order(req.order_no, user.id, db)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.post("/refund")
async def refund_order(
    req: RefundRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """退款（需管理员权限，暂用用户身份标识操作人）"""
    result = await payment_service.refund(
        order_no=req.order_no,
        refund_amount_yuan=Decimal(str(req.refund_amount_yuan)) if req.refund_amount_yuan is not None else None,
        reason=req.reason,
        operator=f"user:{user.id}",
        db=db,
    )
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.get("/orders", response_model=OrderListResponse)
async def list_orders(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: str | None = Query(None),
):
    """用户充值订单列表"""
    result = await payment_service.list_orders(
        user_id=user.id,
        db=db,
        page=page,
        page_size=page_size,
        status_filter=status,
    )
    return OrderListResponse(**result)
