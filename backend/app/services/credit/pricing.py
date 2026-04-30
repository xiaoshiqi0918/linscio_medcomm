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

# ── 输入 prompt 成本估算 ──────────────────────────────────────

_SYSTEM_PROMPT_TOKENS = 2500

_PART1_TOKENS: dict[str, int] = {
    "contest_article": 700,
    "comic_strip": 800,
    "storyboard": 800,
    "card_series": 800,
    "picture_book": 800,
    "poster": 600,
    "long_image": 600,
    "oral_script": 1200,
    "drama_script": 1200,
    "patient_handbook": 1500,
}
_PART1_TOKENS_FULL = 3500

_PART2_TOKENS_WITH_LIT = 2000
_PART2_TOKENS_NO_LIT = 200
_PART3_BASE_TOKENS = 500
_PART3_PRIOR_TOKENS_PER_SECTION = 300

_INPUT_COST_PER_1K_TOKENS: dict[str, Decimal] = {
    "basic": Decimal("0.03"),
    "standard": Decimal("0.06"),
    "pro": Decimal("0.12"),
}


def estimate_prompt_overhead(
    content_format: str = "article",
    section_count: int = 1,
    has_literature: bool = False,
) -> int:
    """估算全文所有章节的累计输入 token 总量（不含输出）。

    Returns: 全部章节求和的总 input token 数。
    """
    if content_format in _PART1_TOKENS:
        part1 = _PART1_TOKENS[content_format]
    else:
        part1 = _PART1_TOKENS_FULL

    part2 = _PART2_TOKENS_WITH_LIT if has_literature else _PART2_TOKENS_NO_LIT

    total = 0
    for i in range(section_count):
        per_section = _SYSTEM_PROMPT_TOKENS + part1 + part2 + _PART3_BASE_TOKENS
        per_section += i * _PART3_PRIOR_TOKENS_PER_SECTION
        total += per_section
    return total


def _generation_output_cost(target_word_count: int, model_tier: str) -> Decimal:
    """按输出字数阶梯查价（原 calc_generation_cost 核心逻辑）"""
    tier_key = model_tier if model_tier in _GENERATION_TIERS_BY_MODEL else "standard"
    tiers = _GENERATION_TIERS_BY_MODEL[tier_key]
    for threshold, price in tiers:
        if target_word_count <= threshold:
            return price
    base = tiers[-1][1]
    extra_words = target_word_count - tiers[-1][0]
    extra_per_1k = _GENERATION_EXTRA_PER_1K_BY_MODEL.get(tier_key, Decimal("2"))
    extra_cost = (Decimal(extra_words) / Decimal("1000")).quantize(Decimal("1"), rounding=ROUND_UP) * extra_per_1k
    return base + extra_cost


def calc_generation_cost(
    target_word_count: int,
    model_tier: str = "standard",
    include_embedding: bool = False,
    content_format: str = "article",
    section_count: int = 1,
) -> Decimal:
    output_cost = _generation_output_cost(target_word_count, model_tier)
    surcharge = SAAS_EMBEDDING_SURCHARGE if include_embedding else Decimal("0")

    input_tokens = estimate_prompt_overhead(
        content_format=content_format,
        section_count=section_count,
        has_literature=include_embedding,
    )
    input_rate = _INPUT_COST_PER_1K_TOKENS.get(model_tier, Decimal("0.06"))
    input_cost = (Decimal(input_tokens) / Decimal("1000") * input_rate).quantize(
        Decimal("0.01"), rounding=ROUND_UP,
    )

    return output_cost + input_cost + surcharge


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


_POLISH_PROMPT_OVERHEAD_CHARS = 2000


def calc_optimization_cost(char_count: int) -> Decimal:
    """润色预估费用（输入+预估输出），用于余额预检。
    char_count 额外计入系统 prompt 及格式指令开销。
    """
    effective_chars = char_count + _POLISH_PROMPT_OVERHEAD_CHARS
    input_cost = _optimization_input_cost(effective_chars)
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


_AI_ASSIST_CONTEXT_OVERHEAD_CHARS = 8000

_AI_ASSIST_INPUT_TIERS: list[tuple[int, Decimal]] = [
    (500, Decimal("0.1")),
    (1500, Decimal("0.2")),
    (3000, Decimal("0.3")),
    (8000, Decimal("0.5")),
    (15000, Decimal("0.8")),
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
    """AI 辅助写作预估费用（输入+预估输出），用于余额预检。
    input_chars 计入文章上下文开销（系统 prompt + 周边章节内容）。
    """
    effective_input = input_chars + _AI_ASSIST_CONTEXT_OVERHEAD_CHARS
    input_cost = _ai_assist_input_cost(effective_input)
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


# ── 图像生成（外部 API） ──────────────────────────────────────
IMAGE_GEN_COST_PER_IMAGE = Decimal("1.5")


def calc_image_gen_cost(batch_count: int = 1) -> Decimal:
    """图像生成固定费用，按张数计"""
    return IMAGE_GEN_COST_PER_IMAGE * max(batch_count, 1)


# ── 参赛 LLM 辅助 ─────────────────────────────────────────────
CONTEST_SUGGEST_INTENT_COST = Decimal("0.15")
CONTEST_GENERATE_PROMPT_COST = Decimal("0.2")
CONTEST_PARSE_ANNOUNCEMENT_COST = Decimal("0.15")


def calc_contest_llm_cost(action: str) -> Decimal:
    """参赛相关 LLM 调用固定费用"""
    costs = {
        "suggest_intent": CONTEST_SUGGEST_INTENT_COST,
        "generate_prompt": CONTEST_GENERATE_PROMPT_COST,
        "parse_announcement": CONTEST_PARSE_ANNOUNCEMENT_COST,
    }
    return costs.get(action, Decimal("0.15"))


# ── 标题生成 ───────────────────────────────────────────────────
TITLE_GENERATION_COST = Decimal("0.1")


def calc_title_generation_cost() -> Decimal:
    """独立标题生成，固定费用（FAST 模型，小输入量）"""
    return TITLE_GENERATION_COST


# ── 图片 AI 提示词（imagegen 场景） ─────────────────────────────
IMAGEGEN_AI_PROMPT_COST = Decimal("0.2")


def calc_imagegen_prompt_cost() -> Decimal:
    """imagegen AI 提示词生成，固定费用"""
    return IMAGEGEN_AI_PROMPT_COST


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
