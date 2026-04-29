"""
积分定价计算
"""
from decimal import Decimal, ROUND_UP
from enum import Enum


class ModelTier(str, Enum):
    BASIC = "basic"        # deepseek-chat, qwen-plus, glm-4-flash
    STANDARD = "standard"  # kimi-k2.5
    PRO = "pro"            # gpt-4o, gemini-3.1-pro-preview


class LiteratureAnalysisMode(str, Enum):
    ABSTRACT = "abstract"
    FULLTEXT = "fulltext"


_LITERATURE_INPUT_PRICING = {
    "abstract": [
        (3000, Decimal("0.3")),
        (8000, Decimal("0.3")),
        (15000, Decimal("0.5")),
        (30000, Decimal("0.5")),
        (float("inf"), Decimal("0.8")),
    ],
    "fulltext": [
        (3000, Decimal("0.5")),
        (8000, Decimal("1")),
        (15000, Decimal("2")),
        (30000, Decimal("3")),
        (float("inf"), Decimal("4")),
    ],
}

_LITERATURE_OUTPUT_PER_1K: dict[str, Decimal] = {
    "abstract": Decimal("0.8"),
    "fulltext": Decimal("1.2"),
}

_LITERATURE_OUTPUT_RATIO: dict[str, Decimal] = {
    "abstract": Decimal("1.3"),
    "fulltext": Decimal("0.6"),
}

_LITERATURE_OUTPUT_MIN: dict[str, int] = {
    "abstract": 1500,
    "fulltext": 2000,
}


def _literature_input_cost(char_count: int, mode: LiteratureAnalysisMode) -> Decimal:
    tiers = _LITERATURE_INPUT_PRICING[mode.value]
    for threshold, price in tiers:
        if char_count <= threshold:
            return price
    return tiers[-1][1]


def _literature_output_cost(output_chars: int, mode: LiteratureAnalysisMode) -> Decimal:
    per_1k = _LITERATURE_OUTPUT_PER_1K[mode.value]
    return (Decimal(output_chars) / Decimal("1000") * per_1k).quantize(Decimal("0.01"), rounding=ROUND_UP)


def estimate_literature_output_chars(input_chars: int, mode: LiteratureAnalysisMode) -> int:
    """Pre-estimate output chars based on input volume for credit freezing."""
    ratio = _LITERATURE_OUTPUT_RATIO[mode.value]
    minimum = _LITERATURE_OUTPUT_MIN[mode.value]
    return max(int(Decimal(input_chars) * ratio), minimum)


def calc_literature_cost(char_count: int, mode: LiteratureAnalysisMode) -> Decimal:
    """Backward-compatible: estimate total cost (input + estimated output) for pre-freeze."""
    input_cost = _literature_input_cost(char_count, mode)
    est_output = estimate_literature_output_chars(char_count, mode)
    output_cost = _literature_output_cost(est_output, mode)
    return input_cost + output_cost


def calc_literature_cost_final(
    input_chars: int,
    output_chars: int,
    mode: LiteratureAnalysisMode,
    estimated_cost: Decimal | None = None,
) -> Decimal:
    """Final settlement: input cost + actual output cost, capped at estimated_cost."""
    input_cost = _literature_input_cost(input_chars, mode)
    output_cost = _literature_output_cost(output_chars, mode)
    total = input_cost + output_cost
    if estimated_cost is not None:
        total = min(total, estimated_cost)
    return total


_GENERATION_TIERS_BY_MODEL: dict[str, list[tuple[int, Decimal]]] = {
    "basic": [
        (1000, Decimal("2")),
        (2000, Decimal("3")),
        (3000, Decimal("5")),
        (5000, Decimal("8")),
    ],
    "standard": [
        (1000, Decimal("3")),
        (2000, Decimal("5")),
        (3000, Decimal("8")),
        (5000, Decimal("12")),
    ],
    "pro": [
        (1000, Decimal("5")),
        (2000, Decimal("8")),
        (3000, Decimal("12")),
        (5000, Decimal("18")),
    ],
}

_GENERATION_EXTRA_PER_1K_BY_MODEL: dict[str, Decimal] = {
    "basic": Decimal("1"),
    "standard": Decimal("2"),
    "pro": Decimal("3"),
}

SAAS_EMBEDDING_SURCHARGE = Decimal("0.1")


def calc_generation_cost(
    target_word_count: int,
    model_tier: str = "standard",
    include_embedding: bool = False,
) -> Decimal:
    tier_key = model_tier if model_tier in _GENERATION_TIERS_BY_MODEL else "standard"
    tiers = _GENERATION_TIERS_BY_MODEL[tier_key]
    surcharge = SAAS_EMBEDDING_SURCHARGE if include_embedding else Decimal("0")
    for threshold, price in tiers:
        if target_word_count <= threshold:
            return price + surcharge
    base = tiers[-1][1]
    extra_words = target_word_count - tiers[-1][0]
    extra_per_1k = _GENERATION_EXTRA_PER_1K_BY_MODEL.get(tier_key, Decimal("2"))
    extra_cost = (Decimal(extra_words) / Decimal("1000")).quantize(Decimal("1"), rounding=ROUND_UP) * extra_per_1k
    return base + extra_cost + surcharge


_OPTIMIZATION_INPUT_TIERS: list[tuple[int, Decimal]] = [
    (500, Decimal("0.5")),
    (1000, Decimal("1")),
    (2000, Decimal("1.5")),
]
_OPTIMIZATION_INPUT_EXTRA_PER_1K = Decimal("0.8")

_OPTIMIZATION_OUTPUT_PER_1K = Decimal("0.6")
_OPTIMIZATION_OUTPUT_RATIO = Decimal("0.8")
_OPTIMIZATION_OUTPUT_MIN = 500


def _optimization_input_cost(char_count: int) -> Decimal:
    for threshold, price in _OPTIMIZATION_INPUT_TIERS:
        if char_count <= threshold:
            return price
    base = _OPTIMIZATION_INPUT_TIERS[-1][1]
    extra = char_count - _OPTIMIZATION_INPUT_TIERS[-1][0]
    return base + (Decimal(extra) / Decimal("1000")).quantize(Decimal("1"), rounding=ROUND_UP) * _OPTIMIZATION_INPUT_EXTRA_PER_1K


def _optimization_output_cost(output_chars: int) -> Decimal:
    return (Decimal(output_chars) / Decimal("1000") * _OPTIMIZATION_OUTPUT_PER_1K).quantize(
        Decimal("0.01"), rounding=ROUND_UP
    )


def calc_optimization_cost(char_count: int) -> Decimal:
    """润色预估费用（输入+预估输出），用于余额预检。"""
    input_cost = _optimization_input_cost(char_count)
    est_output = max(int(Decimal(char_count) * _OPTIMIZATION_OUTPUT_RATIO), _OPTIMIZATION_OUTPUT_MIN)
    output_cost = _optimization_output_cost(est_output)
    return input_cost + output_cost


def calc_optimization_cost_final(
    input_chars: int,
    output_chars: int,
    estimated_cost: Decimal | None = None,
) -> Decimal:
    """润色最终结算（输入+实际输出），不超过预估。"""
    input_cost = _optimization_input_cost(input_chars)
    output_cost = _optimization_output_cost(output_chars)
    total = input_cost + output_cost
    if estimated_cost is not None:
        total = min(total, estimated_cost)
    return total


_LITERATURE_FILTER_TIERS: list[tuple[int, Decimal]] = [
    (10, Decimal("0.5")),
    (20, Decimal("1")),
    (30, Decimal("1.5")),
    (50, Decimal("2")),
]
_LITERATURE_FILTER_MAX = Decimal("3")


def calc_literature_filter_cost(paper_count: int) -> Decimal:
    """AI 文献筛选费用，按待筛选文献数量阶梯计价。"""
    if paper_count <= 0:
        return Decimal("0")
    for threshold, price in _LITERATURE_FILTER_TIERS:
        if paper_count <= threshold:
            return price
    return _LITERATURE_FILTER_MAX


_TRANSLATION_INPUT_TIERS: list[tuple[int, Decimal]] = [
    (500, Decimal("0.05")),
    (2000, Decimal("0.1")),
    (5000, Decimal("0.2")),
    (15000, Decimal("0.4")),
]

_TRANSLATION_OUTPUT_PER_1K = Decimal("0.3")

_TRANSLATION_OUTPUT_RATIO = Decimal("1.5")
_TRANSLATION_OUTPUT_MIN = 300


def _translation_input_cost(char_count: int) -> Decimal:
    if char_count <= 0:
        return Decimal("0")
    for threshold, price in _TRANSLATION_INPUT_TIERS:
        if char_count <= threshold:
            return price
    return _TRANSLATION_INPUT_TIERS[-1][1]


def _translation_output_cost(output_chars: int) -> Decimal:
    return (Decimal(output_chars) / Decimal("1000") * _TRANSLATION_OUTPUT_PER_1K).quantize(
        Decimal("0.01"), rounding=ROUND_UP
    )


def calc_translation_cost(char_count: int) -> Decimal:
    """AI 翻译预估费用（输入+预估输出），用于余额预检。"""
    if char_count <= 0:
        return Decimal("0")
    input_cost = _translation_input_cost(char_count)
    est_output = max(int(Decimal(char_count) * _TRANSLATION_OUTPUT_RATIO), _TRANSLATION_OUTPUT_MIN)
    output_cost = _translation_output_cost(est_output)
    return input_cost + output_cost


def calc_translation_cost_final(
    input_chars: int,
    output_chars: int,
    estimated_cost: Decimal | None = None,
) -> Decimal:
    """AI 翻译最终结算（输入+实际输出），不超过预估。"""
    input_cost = _translation_input_cost(input_chars)
    output_cost = _translation_output_cost(output_chars)
    total = input_cost + output_cost
    if estimated_cost is not None:
        total = min(total, estimated_cost)
    return total


_AI_ASSIST_INPUT_TIERS: list[tuple[int, Decimal]] = [
    (500, Decimal("0.1")),
    (1500, Decimal("0.2")),
    (3000, Decimal("0.3")),
]

_AI_ASSIST_OUTPUT_PER_1K = Decimal("0.5")
_AI_ASSIST_OUTPUT_RATIO = Decimal("2.0")
_AI_ASSIST_OUTPUT_MIN = 500


def _ai_assist_input_cost(char_count: int) -> Decimal:
    for threshold, price in _AI_ASSIST_INPUT_TIERS:
        if char_count <= threshold:
            return price
    return _AI_ASSIST_INPUT_TIERS[-1][1]


def _ai_assist_output_cost(output_chars: int) -> Decimal:
    return (Decimal(output_chars) / Decimal("1000") * _AI_ASSIST_OUTPUT_PER_1K).quantize(
        Decimal("0.01"), rounding=ROUND_UP
    )


def calc_ai_assist_cost(input_chars: int) -> Decimal:
    """AI 辅助写作预估费用（输入+预估输出），用于余额预检。"""
    input_cost = _ai_assist_input_cost(input_chars)
    est_output = max(int(Decimal(input_chars) * _AI_ASSIST_OUTPUT_RATIO), _AI_ASSIST_OUTPUT_MIN)
    output_cost = _ai_assist_output_cost(est_output)
    return input_cost + output_cost


def calc_ai_assist_cost_final(
    input_chars: int,
    output_chars: int,
    estimated_cost: Decimal | None = None,
) -> Decimal:
    """AI 辅助写作最终结算（输入+实际输出），不超过预估。"""
    input_cost = _ai_assist_input_cost(input_chars)
    output_cost = _ai_assist_output_cost(output_chars)
    total = input_cost + output_cost
    if estimated_cost is not None:
        total = min(total, estimated_cost)
    return total


EXPORT_COST_WATERMARK = Decimal("0")
EXPORT_COST_CLEAN = Decimal("3")


def calc_export_cost(with_watermark: bool) -> Decimal:
    return EXPORT_COST_WATERMARK if with_watermark else EXPORT_COST_CLEAN


# ── 配图 AI 提示词 ─────────────────────────────────────────
MEDPIC_PROMPT_COST = Decimal("0.2")


def calc_medpic_prompt_cost() -> Decimal:
    """配图 AI 提示词生成/优化，固定费用（单次 FAST 模型调用量小）"""
    return MEDPIC_PROMPT_COST


# ── 检索词智能设计 ─────────────────────────────────────────
KEYWORD_DESIGN_COST = Decimal("0.1")


def calc_keyword_design_cost() -> Decimal:
    """检索词智能设计，固定费用（单次 FAST 模型调用量小）"""
    return KEYWORD_DESIGN_COST


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
