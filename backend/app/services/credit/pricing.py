"""
积分定价计算
"""
from decimal import Decimal, ROUND_UP
from enum import Enum


class LiteratureAnalysisMode(str, Enum):
    ABSTRACT = "abstract"
    FULLTEXT = "fulltext"


_LITERATURE_PRICING = {
    "abstract": [
        (3000, Decimal("0.5")),
        (8000, Decimal("0.5")),
        (15000, Decimal("1")),
        (30000, Decimal("1")),
        (float("inf"), Decimal("1.5")),
    ],
    "fulltext": [
        (3000, Decimal("1")),
        (8000, Decimal("2")),
        (15000, Decimal("4")),
        (30000, Decimal("6")),
        (float("inf"), Decimal("8")),
    ],
}


def calc_literature_cost(char_count: int, mode: LiteratureAnalysisMode) -> Decimal:
    tiers = _LITERATURE_PRICING[mode.value]
    for threshold, price in tiers:
        if char_count <= threshold:
            return price
    return tiers[-1][1]


_GENERATION_TIERS = [
    (1000, Decimal("3")),
    (2000, Decimal("5")),
    (3000, Decimal("8")),
    (5000, Decimal("12")),
]
_GENERATION_EXTRA_PER_1K = Decimal("2")


def calc_generation_cost(target_word_count: int) -> Decimal:
    for threshold, price in _GENERATION_TIERS:
        if target_word_count <= threshold:
            return price
    base = _GENERATION_TIERS[-1][1]
    extra_words = target_word_count - _GENERATION_TIERS[-1][0]
    extra_cost = (Decimal(extra_words) / Decimal("1000")).quantize(Decimal("1"), rounding=ROUND_UP) * _GENERATION_EXTRA_PER_1K
    return base + extra_cost


def calc_optimization_cost(char_count: int) -> Decimal:
    if char_count <= 500:
        return Decimal("1")
    elif char_count <= 1000:
        return Decimal("2")
    else:
        return (Decimal(char_count) / Decimal("1000") * Decimal("2")).quantize(Decimal("0.0001"))


EXPORT_COST_WATERMARK = Decimal("0")
EXPORT_COST_CLEAN = Decimal("3")


def calc_export_cost(with_watermark: bool) -> Decimal:
    return EXPORT_COST_WATERMARK if with_watermark else EXPORT_COST_CLEAN


def calc_cost_from_token_ratio(
    estimated_cost: Decimal,
    actual_tokens: int,
    estimated_tokens: int,
) -> Decimal:
    if estimated_tokens <= 0 or actual_tokens <= 0:
        return Decimal("0")
    ratio = Decimal(actual_tokens) / Decimal(estimated_tokens)
    ratio = min(ratio, Decimal("1"))
    return (estimated_cost * ratio).quantize(Decimal("0.0001"))
