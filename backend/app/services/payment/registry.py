"""
支付渠道注册表
根据 channel_code 获取对应的适配器实例，支持运行时动态注册。
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.services.payment.base import PaymentChannelAdapter

logger = logging.getLogger(__name__)

_registry: dict[str, PaymentChannelAdapter] = {}


def register_channel(adapter: PaymentChannelAdapter) -> None:
    code = adapter.channel_code
    _registry[code] = adapter
    logger.info("支付渠道已注册: %s", code)


def get_channel(channel_code: str) -> PaymentChannelAdapter:
    adapter = _registry.get(channel_code)
    if adapter is None:
        raise ValueError(f"未注册的支付渠道: {channel_code}，可用渠道: {list(_registry.keys())}")
    return adapter


def list_channels() -> list[str]:
    return list(_registry.keys())


def _init_default_channels() -> None:
    """启动时自动注册已配置的渠道"""
    from app.core.config import settings

    if settings.yipay_pid and settings.yipay_key:
        from app.services.payment.yipay import YiPayAdapter
        register_channel(YiPayAdapter())

    if settings.alipay_app_id and settings.alipay_private_key:
        from app.services.payment.alipay import AlipayAdapter
        register_channel(AlipayAdapter())

    if settings.wechat_mch_id and settings.wechat_api_key:
        from app.services.payment.wechatpay import WeChatPayAdapter
        register_channel(WeChatPayAdapter())


_init_default_channels()
