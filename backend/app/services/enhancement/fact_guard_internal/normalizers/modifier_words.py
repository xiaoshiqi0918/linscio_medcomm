"""
数值修饰词等价类（P0-1 / 决策 N1）

合并模糊估算类：'约 / 大约 / 大致 / 差不多 / 近 / 接近 / 约莫 / 左右 / 上下 / 前后'
都视为同一等价类。前置（约 15%）和后置（15% 左右）统一处理。

其余类别保持独立：超过 / 不到 / 至少 / 至多 等。
"""
from __future__ import annotations

# ────────────────────────────────────────────
# 等价类（同集合内任意两个修饰词视为等价）
# ────────────────────────────────────────────

MODIFIER_EQUIVALENCE_CLASSES: list[set[str]] = [
    # 模糊估算（决策 N1：前置 + 后置统一）
    {
        "约", "大约", "大致", "差不多", "近", "接近", "约莫",
        "左右", "上下", "前后",
    },
    # 超过类
    {"超过", "大于", "多于", "高于", "超", "以上", ">"},
    # 不到类
    {"不到", "小于", "少于", "低于", "不足", "以下", "<"},
    # 至少
    {"至少", "起码", "不少于", "≥", ">="},
    # 至多
    {"至多", "最多", "不超过", "不多于", "≤", "<="},
    # 大致区间
    {"大概", "估计", "可能"},
]

# 前置修饰词（出现在数字前）
PREFIX_MODIFIERS: list[str] = [
    "约莫", "大约", "大致", "差不多", "接近", "约", "近",
    "超过", "大于", "多于", "高于", "超", "至少", "起码", "不少于",
    "不到", "小于", "少于", "低于", "不足", "至多", "最多", "不超过", "不多于",
    "大概", "估计", "可能",
    "≥", ">=", "≤", "<=", ">", "<",
]

# 后置修饰词（出现在数字后）
SUFFIX_MODIFIERS: list[str] = [
    "左右", "上下", "前后", "以上", "以下", "之多", "余",
]


# 反查表：词 → 等价类的代表词（用集合中字典序最小的作为代表）
def _build_canonical_map() -> dict[str, str]:
    mapping: dict[str, str] = {}
    for cls in MODIFIER_EQUIVALENCE_CLASSES:
        canonical = min(cls)  # 用字典序最小作为代表
        for word in cls:
            mapping[word] = canonical
    return mapping


_CANONICAL = _build_canonical_map()


def canonicalize_modifier(word: str) -> str:
    """把修饰词归一化为其等价类的代表词；未识别返回原词。"""
    if not word:
        return ""
    return _CANONICAL.get(word.strip(), word.strip())


def modifiers_equivalent(a: str, b: str) -> bool:
    """两个修饰词是否等价（同等价类，或都为空）。"""
    a_norm = canonicalize_modifier(a) if a else ""
    b_norm = canonicalize_modifier(b) if b else ""
    return a_norm == b_norm


__all__ = [
    "MODIFIER_EQUIVALENCE_CLASSES",
    "PREFIX_MODIFIERS",
    "SUFFIX_MODIFIERS",
    "canonicalize_modifier",
    "modifiers_equivalent",
]
