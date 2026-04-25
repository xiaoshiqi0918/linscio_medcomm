"""
易支付渠道适配器
实现 PaymentChannelAdapter 接口，封装 MD5 签名、API 下单、回调验签、订单查询。
"""
import hashlib
import logging
import uuid
from urllib.parse import urlencode

import httpx

from app.core.config import settings
from app.services.payment.base import (
    PaymentChannelAdapter,
    CreatePaymentResult,
    QueryResult,
    RefundResult,
)

logger = logging.getLogger(__name__)


def _generate_order_no() -> str:
    return uuid.uuid4().hex[:24]


class YiPayAdapter(PaymentChannelAdapter):
    channel_code = "yipay"

    def _make_sign(self, params: dict) -> str:
        filtered = {
            k: v for k, v in params.items()
            if k not in ("sign", "sign_type") and v not in (None, "")
        }
        sorted_keys = sorted(filtered.keys())
        raw = "&".join(f"{k}={filtered[k]}" for k in sorted_keys)
        raw += settings.yipay_key
        return hashlib.md5(raw.encode("utf-8")).hexdigest()

    def verify_callback(self, params: dict) -> bool:
        received_sign = params.get("sign", "")
        expected_sign = self._make_sign(params)
        return received_sign == expected_sign

    async def create_payment(
        self,
        order_no: str,
        amount_yuan: str,
        subject: str,
        pay_method: str,
        client_ip: str,
        extra: dict | None = None,
    ) -> CreatePaymentResult:
        extra = extra or {}
        data = {
            "pid": settings.yipay_pid,
            "type": pay_method,
            "out_trade_no": order_no,
            "notify_url": settings.yipay_notify_url,
            "name": subject,
            "money": amount_yuan,
            "clientip": client_ip,
            "param": extra.get("param", ""),
            "sign_type": "MD5",
        }
        data["sign"] = self._make_sign(data)

        gateway = settings.yipay_gateway.rstrip("/")
        url = f"{gateway}/mapi.php"

        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(url, data=data)
                result = resp.json()
        except Exception as exc:
            logger.error("易支付请求异常: %s", exc)
            return CreatePaymentResult(success=False, error=str(exc))

        if result.get("code") == 1:
            page_url = self._build_page_pay_url(order_no, amount_yuan, subject, pay_method)
            return CreatePaymentResult(
                success=True,
                channel_order_id=result.get("trade_no", ""),
                qrcode_url=result.get("qrcode") or result.get("payurl") or "",
                pay_page_url=page_url,
                raw_response=result,
            )
        else:
            logger.error("易支付下单失败: %s", result)
            return CreatePaymentResult(
                success=False,
                error=result.get("msg", "下单失败"),
                raw_response=result,
            )

    async def query_order(self, order_no: str) -> QueryResult:
        gateway = settings.yipay_gateway.rstrip("/")
        url = f"{gateway}/api.php"
        params = {
            "act": "order",
            "pid": settings.yipay_pid,
            "key": settings.yipay_key,
            "out_trade_no": order_no,
        }
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(url, params=params)
                result = resp.json()
        except Exception as exc:
            logger.error("易支付查询异常: %s", exc)
            return QueryResult(success=False, error=str(exc))

        if result.get("code") == 1:
            return QueryResult(
                success=True,
                paid=result.get("status") == 1,
                channel_order_id=result.get("trade_no", ""),
                paid_amount=result.get("money", ""),
                raw_response=result,
            )
        return QueryResult(success=False, error=result.get("msg", "查询失败"), raw_response=result)

    async def refund(self, order_no: str, refund_amount: str, reason: str) -> RefundResult:
        raise NotImplementedError("易支付不支持 API 退款")

    def _build_page_pay_url(
        self,
        order_no: str,
        amount_yuan: str,
        name: str,
        pay_type: str,
    ) -> str:
        params = {
            "pid": settings.yipay_pid,
            "type": pay_type,
            "out_trade_no": order_no,
            "notify_url": settings.yipay_notify_url,
            "return_url": settings.yipay_return_url,
            "name": name,
            "money": amount_yuan,
            "sign_type": "MD5",
        }
        params["sign"] = self._make_sign(params)
        gateway = settings.yipay_gateway.rstrip("/")
        return f"{gateway}/submit.php?{urlencode(params)}"


# 保留模块级便捷函数以兼容旧代码
_adapter = YiPayAdapter()
generate_order_no = _generate_order_no
verify_sign = _adapter.verify_callback


async def create_payment(order_no, amount_yuan, name, pay_type="alipay", client_ip="127.0.0.1", param=""):
    result = await _adapter.create_payment(
        order_no=order_no,
        amount_yuan=amount_yuan,
        subject=name,
        pay_method=pay_type,
        client_ip=client_ip,
        extra={"param": param},
    )
    if result.success:
        return {
            "success": True,
            "qrcode": result.qrcode_url,
            "img": result.raw_response.get("img", ""),
            "trade_no": result.channel_order_id,
            "order_no": order_no,
        }
    return {"success": False, "error": result.error}


def build_page_pay_url(order_no, amount_yuan, name, pay_type="alipay"):
    return _adapter._build_page_pay_url(order_no, amount_yuan, name, pay_type)


async def query_order(order_no):
    result = await _adapter.query_order(order_no)
    if result.success:
        return {
            "success": True,
            "status": "paid" if result.paid else "unpaid",
            "trade_no": result.channel_order_id,
            "money": result.paid_amount,
        }
    return {"success": False, "error": result.error}
