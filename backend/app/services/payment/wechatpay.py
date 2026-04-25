"""
微信支付官方直连适配器（预留）
接入前需安装 wechatpayv3 并配置商户号/API密钥/证书。
实际启用时在 registry._init_default_channels 中注册即可。
"""
from __future__ import annotations

import logging

from app.services.payment.base import (
    PaymentChannelAdapter,
    CreatePaymentResult,
    QueryResult,
    RefundResult,
)

logger = logging.getLogger(__name__)


class WeChatPayAdapter(PaymentChannelAdapter):
    channel_code = "wechatpay"

    def __init__(self):
        # 启用时从 settings 加载:
        # self.mch_id = settings.wechat_mch_id
        # self.api_key = settings.wechat_api_key
        # self.cert_path = settings.wechat_cert_path
        # self.key_path = settings.wechat_key_path
        pass

    async def create_payment(
        self,
        order_no: str,
        amount_yuan: str,
        subject: str,
        pay_method: str,
        client_ip: str,
        extra: dict | None = None,
    ) -> CreatePaymentResult:
        # 使用 wechatpayv3 SDK:
        # wxpay = WeChatPay(...)
        # result = wxpay.native(description=subject, out_trade_no=order_no,
        #                       amount={'total': int(float(amount_yuan) * 100)})
        raise NotImplementedError("微信支付直连尚未配置")

    async def query_order(self, order_no: str) -> QueryResult:
        # wxpay.query(out_trade_no=order_no)
        raise NotImplementedError("微信支付直连尚未配置")

    def verify_callback(self, params: dict) -> bool:
        # from wechatpayv3 import verify_signature
        raise NotImplementedError("微信支付直连尚未配置")

    async def refund(
        self,
        order_no: str,
        refund_amount: str,
        reason: str,
    ) -> RefundResult:
        # wxpay.refund(out_trade_no=order_no, out_refund_no=...,
        #              amount={'refund': ..., 'total': ..., 'currency': 'CNY'},
        #              reason=reason)
        raise NotImplementedError("微信支付直连尚未配置")

    async def download_bill(self, bill_date: str) -> list[dict]:
        # wxpay.trade_bill(bill_date=bill_date)
        raise NotImplementedError("微信支付直连尚未配置")
