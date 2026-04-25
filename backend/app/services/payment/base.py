"""
支付渠道适配器抽象基类 — Strategy Pattern
每个支付渠道（易支付 / 支付宝 / 微信支付等）实现此接口。
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class CreatePaymentResult:
    success: bool
    channel_order_id: str = ""
    qrcode_url: str = ""
    pay_page_url: str = ""
    raw_response: dict = field(default_factory=dict)
    error: str = ""


@dataclass
class QueryResult:
    success: bool
    paid: bool = False
    channel_order_id: str = ""
    paid_amount: str = ""
    raw_response: dict = field(default_factory=dict)
    error: str = ""


@dataclass
class RefundResult:
    success: bool
    refund_id: str = ""
    raw_response: dict = field(default_factory=dict)
    error: str = ""


class PaymentChannelAdapter(ABC):
    """所有支付渠道适配器的公共接口"""

    channel_code: str  # "yipay" / "alipay" / "wechatpay"

    @abstractmethod
    async def create_payment(
        self,
        order_no: str,
        amount_yuan: str,
        subject: str,
        pay_method: str,
        client_ip: str,
        extra: dict | None = None,
    ) -> CreatePaymentResult:
        """向渠道发起支付请求，返回二维码/跳转链接"""
        ...

    @abstractmethod
    async def query_order(self, order_no: str) -> QueryResult:
        """主动查询渠道侧订单状态"""
        ...

    @abstractmethod
    def verify_callback(self, params: dict) -> bool:
        """校验异步回调签名"""
        ...

    @abstractmethod
    async def refund(
        self,
        order_no: str,
        refund_amount: str,
        reason: str,
    ) -> RefundResult:
        """发起退款（渠道不支持时抛 NotImplementedError）"""
        ...

    async def download_bill(self, bill_date: str) -> list[dict]:
        """下载渠道对账单（可选实现，默认空）"""
        return []
