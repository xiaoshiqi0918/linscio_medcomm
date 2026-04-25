"""
订单状态机
定义合法状态转换白名单，非法转换直接抛异常。
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from enum import Enum

logger = logging.getLogger(__name__)


class OrderStatus(str, Enum):
    CREATED = "created"
    PAYING = "paying"
    PAID = "paid"
    EXPIRED = "expired"
    CLOSED = "closed"
    PARTIAL_REFUND = "partial_refund"
    FULL_REFUND = "full_refund"


VALID_TRANSITIONS: dict[OrderStatus, set[OrderStatus]] = {
    OrderStatus.CREATED: {OrderStatus.PAYING, OrderStatus.EXPIRED, OrderStatus.CLOSED},
    OrderStatus.PAYING: {OrderStatus.PAID, OrderStatus.EXPIRED, OrderStatus.CLOSED},
    OrderStatus.PAID: {OrderStatus.PARTIAL_REFUND, OrderStatus.FULL_REFUND},
    OrderStatus.PARTIAL_REFUND: {OrderStatus.FULL_REFUND},
    OrderStatus.EXPIRED: set(),
    OrderStatus.CLOSED: set(),
    OrderStatus.FULL_REFUND: set(),
}

TERMINAL_STATES = {OrderStatus.EXPIRED, OrderStatus.CLOSED, OrderStatus.FULL_REFUND}


class InvalidTransitionError(Exception):
    def __init__(self, current: str, target: str):
        self.current = current
        self.target = target
        super().__init__(f"非法状态转换: {current} -> {target}")


def validate_transition(current: str, target: str) -> None:
    try:
        current_status = OrderStatus(current)
        target_status = OrderStatus(target)
    except ValueError as e:
        raise InvalidTransitionError(current, target) from e

    if target_status not in VALID_TRANSITIONS.get(current_status, set()):
        raise InvalidTransitionError(current, target)


def transition_order(order, target: str) -> None:
    """
    安全地转换订单状态，同时设置对应的时间戳。
    order: PaymentOrder ORM 实例
    """
    validate_transition(order.status, target)
    old = order.status
    order.status = target
    now = datetime.now(timezone.utc)

    if target == OrderStatus.PAID:
        order.paid_at = now
    elif target == OrderStatus.EXPIRED:
        order.expired_at = now
    elif target == OrderStatus.CLOSED:
        order.closed_at = now

    logger.info("订单 %s 状态转换: %s -> %s", order.order_no, old, target)


def is_terminal(status: str) -> bool:
    try:
        return OrderStatus(status) in TERMINAL_STATES
    except ValueError:
        return False
