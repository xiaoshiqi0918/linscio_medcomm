"""
支付宝官方直连适配器（预留）
接入前需安装 alipay-sdk-python 并配置应用私钥/支付宝公钥。
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


class AlipayAdapter(PaymentChannelAdapter):
    channel_code = "alipay"

    def __init__(self):
        # 启用时从 settings 加载:
        # self.app_id = settings.alipay_app_id
        # self.private_key = settings.alipay_private_key
        # self.alipay_public_key = settings.alipay_public_key
        # self.notify_url = settings.alipay_notify_url
        # self.return_url = settings.alipay_return_url
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
        # 使用 alipay SDK:
        # from alipay import AliPay
        # alipay_client = AliPay(...)
        # result = alipay_client.api_alipay_trade_precreate(
        #     subject=subject,
        #     out_trade_no=order_no,
        #     total_amount=amount_yuan,
        # )
        raise NotImplementedError("支付宝直连尚未配置")

    async def query_order(self, order_no: str) -> QueryResult:
        # alipay_client.api_alipay_trade_query(out_trade_no=order_no)
        raise NotImplementedError("支付宝直连尚未配置")

    def verify_callback(self, params: dict) -> bool:
        # from alipay import verify_with_rsa
        # return verify_with_rsa(params, self.alipay_public_key)
        raise NotImplementedError("支付宝直连尚未配置")

    async def refund(
        self,
        order_no: str,
        refund_amount: str,
        reason: str,
    ) -> RefundResult:
        # alipay_client.api_alipay_trade_refund(
        #     out_trade_no=order_no,
        #     refund_amount=refund_amount,
        #     refund_reason=reason,
        # )
        raise NotImplementedError("支付宝直连尚未配置")

    async def download_bill(self, bill_date: str) -> list[dict]:
        # alipay_client.api_alipay_data_dataservice_bill_downloadurl_query(
        #     bill_type='trade',
        #     bill_date=bill_date,
        # )
        raise NotImplementedError("支付宝直连尚未配置")
