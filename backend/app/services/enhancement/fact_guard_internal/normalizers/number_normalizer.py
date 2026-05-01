"""
数值短语提取与等价判断（P0-1 弱 gate 主入口）

NumberPhrase = 数值 + 单位 + 修饰词 + 是否区间。两个 NumberPhrase 等价当且仅当：
  1. 单位归一化后相同
  2. 数值相等（区间需端点都相等）
  3. 修饰词等价类相同（决策 N1）

特别地（决策 N2）：
  - 默认严格不互换分数与百分比（"三分之一" ≠ "33%"）
  - 但接口预留 fraction_tolerance 参数供 P1 升级到分级处理
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional, Union

from .chinese_number import (
    _CN_FRACTION_PATTERN,
    is_chinese_number_char,
    parse_chinese_decimal,
    parse_chinese_integer,
)
from .modifier_words import (
    PREFIX_MODIFIERS,
    SUFFIX_MODIFIERS,
    canonicalize_modifier,
    modifiers_equivalent,
)
from .unit_normalizer import UNIT_REGEX_FRAGMENT, normalize_unit


# ────────────────────────────────────────────
# 数据结构
# ────────────────────────────────────────────


@dataclass(frozen=True)
class NumberPhrase:
    """单个数值短语。

    value:
      - float：单点数值（"15.0%"）
      - tuple[float, float]：区间端点（"15-20%" → (15.0, 20.0)）
      - tuple[int, int]：分数（"三分之一" → (1, 3)，按精确分数保留）
    unit:    归一化后的单位字符串（"%" / "mg" / "year" / ""）
    modifier: 等价类代表词（"约" / "超过" / ""），由 canonicalize_modifier 处理
    is_range: 是否为数值区间
    is_fraction: 是否为精确分数（与 unit="ratio" 配套）
    original: 原始匹配文本
    span: 在原文中的字符范围 (start, end)
    """
    value: Union[float, tuple]
    unit: str = ""
    modifier: str = ""
    is_range: bool = False
    is_fraction: bool = False
    original: str = ""
    span: tuple[int, int] = (0, 0)

    def equivalent_to(
        self,
        other: "NumberPhrase",
        *,
        rel_tolerance: float = 0.0,
        fraction_tolerance: float = 0.0,
    ) -> bool:
        """两个 NumberPhrase 是否等价。

        rel_tolerance: 单点数值的相对容差（弱 gate 默认 0，可调到 0.05 = ±5%）
        fraction_tolerance: 分数 ↔ 百分比互转容差（决策 N2，默认 0 严格不换）
        """
        # 修饰词等价
        if not modifiers_equivalent(self.modifier, other.modifier):
            return False

        # 同类型同单位的快速路径
        if self.unit == other.unit:
            if self.is_range and other.is_range:
                a0, a1 = self.value  # type: ignore[misc]
                b0, b1 = other.value  # type: ignore[misc]
                return _close(a0, b0, rel_tolerance) and _close(a1, b1, rel_tolerance)
            if self.is_fraction and other.is_fraction:
                an, ad = self.value  # type: ignore[misc]
                bn, bd = other.value  # type: ignore[misc]
                return an * bd == bn * ad
            if not self.is_range and not other.is_range and not self.is_fraction and not other.is_fraction:
                return _close(float(self.value), float(other.value), rel_tolerance)
            return False

        # 跨类型：分数 ↔ 百分比（决策 N2）
        if fraction_tolerance > 0 and not self.is_range and not other.is_range:
            a_norm01 = self._to_unit_interval()
            b_norm01 = other._to_unit_interval()
            if a_norm01 is not None and b_norm01 is not None:
                # 同精度等价转换才允许：必须有一方是分数或带模糊修饰
                if (self.is_fraction or other.is_fraction) or (self.modifier or other.modifier):
                    return abs(a_norm01 - b_norm01) <= fraction_tolerance

        return False

    def _to_unit_interval(self) -> Optional[float]:
        """把分数 / 百分比统一转换到 [0,1] 区间；其他单位返回 None。"""
        if self.is_fraction:
            n, d = self.value  # type: ignore[misc]
            return float(n) / float(d) if d else None
        if self.unit == "%":
            return float(self.value) / 100.0  # type: ignore[arg-type]
        if self.unit == "ratio":
            return float(self.value)  # type: ignore[arg-type]
        return None


def _close(a: float, b: float, rel: float) -> bool:
    if rel <= 0:
        return a == b
    if a == 0 and b == 0:
        return True
    base = max(abs(a), abs(b), 1e-12)
    return abs(a - b) / base <= rel


# ────────────────────────────────────────────
# 正则
# ────────────────────────────────────────────

_PREFIX_RE = "|".join(re.escape(m) for m in sorted(PREFIX_MODIFIERS, key=lambda x: -len(x)))
_SUFFIX_RE = "|".join(re.escape(m) for m in sorted(SUFFIX_MODIFIERS, key=lambda x: -len(x)))


# 阿拉伯分数 1/3、3/4：必须早于普通数字，且保证不被误解为日期
_ARABIC_FRACTION_PATTERN = re.compile(
    r"(?P<prefix>" + _PREFIX_RE + r")?\s*"
    r"(?P<num>\d{1,3})\s*/\s*(?P<den>\d{1,4})"
    r"(?!\s*\d)"
)

# 阿拉伯数字 + 单位（含区间）
# 注意单位匹配片段已按长度倒序，复合单位优先
_ARABIC_NUMBER_PATTERN = re.compile(
    r"(?P<prefix>" + _PREFIX_RE + r")?\s*"
    r"(?P<num1>\d+(?:\.\d+)?)"
    r"(?:\s*[-~–—]\s*(?P<num2>\d+(?:\.\d+)?))?"
    r"\s*"
    r"(?P<unit>" + UNIT_REGEX_FRAGMENT + r")?"
    r"\s*(?P<suffix>" + _SUFFIX_RE + r")?"
)

# 中文整数 / 小数 + 单位
_CN_NUM_RUN = r"[零〇一二三四五六七八九十百千万壹贰叁肆伍陆柒捌玖拾佰仟萬亿両两俩点點]+"
_CHINESE_NUMBER_PATTERN = re.compile(
    r"(?P<prefix>" + _PREFIX_RE + r")?\s*"
    r"(?P<num>" + _CN_NUM_RUN + r")"
    r"\s*"
    r"(?P<unit>" + UNIT_REGEX_FRAGMENT + r")?"
    r"\s*(?P<suffix>" + _SUFFIX_RE + r")?"
)


# ────────────────────────────────────────────
# 提取
# ────────────────────────────────────────────


def extract_all_number_phrases(text: str) -> list[NumberPhrase]:
    """从文本中提取所有 NumberPhrase。

    优先级：
      1. 中文分数（'三分之一'）
      2. 阿拉伯分数（'1/3'）
      3. 阿拉伯数字（含区间、单位、修饰词）
      4. 中文数字（含单位、修饰词）

    被前序优先级覆盖的位置不会再次匹配，避免重复。
    """
    if not text:
        return []
    phrases: list[NumberPhrase] = []
    consumed = bytearray(len(text))  # 字节为单位标记已消费

    def _claim(span: tuple[int, int]) -> bool:
        s, e = span
        if any(consumed[i] for i in range(s, e)):
            return False
        for i in range(s, e):
            consumed[i] = 1
        return True

    # 1. 中文分数：'X分之Y' → (Y, X)（注意：中文是分母在前，分子在后）
    #    "三分之一" → 分母=3, 分子=1 → 1/3
    for m in _CN_FRACTION_PATTERN.finditer(text):
        denom_str, num_str = m.group(1), m.group(2)
        denom = parse_chinese_integer(denom_str)
        numer = parse_chinese_integer(num_str)
        if not denom or numer is None:
            continue
        # 修饰词：中文分数前后扫描
        prefix = _scan_prefix_modifier(text, m.start())
        suffix = _scan_suffix_modifier(text, m.end())
        s = m.start() - len(prefix) if prefix else m.start()
        e = m.end() + len(suffix) if suffix else m.end()
        if not _claim((s, e)):
            continue
        phrases.append(NumberPhrase(
            value=(numer, denom),
            unit="ratio",
            modifier=canonicalize_modifier(prefix or suffix),
            is_fraction=True,
            original=text[s:e],
            span=(s, e),
        ))

    # 2. 阿拉伯分数
    for m in _ARABIC_FRACTION_PATTERN.finditer(text):
        if not _claim(m.span()):
            continue
        prefix = (m.group("prefix") or "").strip()
        suffix = _scan_suffix_modifier(text, m.end())
        if suffix and not _claim((m.end(), m.end() + len(suffix))):
            suffix = ""
        try:
            n = int(m.group("num"))
            d = int(m.group("den"))
        except ValueError:
            continue
        if d == 0:
            continue
        phrases.append(NumberPhrase(
            value=(n, d),
            unit="ratio",
            modifier=canonicalize_modifier(prefix or suffix),
            is_fraction=True,
            original=m.group(0),
            span=m.span(),
        ))

    # 3. 阿拉伯数字
    for m in _ARABIC_NUMBER_PATTERN.finditer(text):
        if not _claim(m.span()):
            continue
        prefix = (m.group("prefix") or "").strip()
        suffix = (m.group("suffix") or "").strip()
        unit_raw = (m.group("unit") or "").strip()
        try:
            n1 = float(m.group("num1"))
        except ValueError:
            continue
        n2_str = m.group("num2")
        if n2_str is not None:
            try:
                n2 = float(n2_str)
            except ValueError:
                continue
            phrases.append(NumberPhrase(
                value=(n1, n2),
                unit=normalize_unit(unit_raw),
                modifier=canonicalize_modifier(prefix or suffix),
                is_range=True,
                original=m.group(0),
                span=m.span(),
            ))
        else:
            phrases.append(NumberPhrase(
                value=n1,
                unit=normalize_unit(unit_raw),
                modifier=canonicalize_modifier(prefix or suffix),
                original=m.group(0),
                span=m.span(),
            ))

    # 4. 中文数字
    for m in _CHINESE_NUMBER_PATTERN.finditer(text):
        if not _claim(m.span()):
            continue
        prefix = (m.group("prefix") or "").strip()
        suffix = (m.group("suffix") or "").strip()
        unit_raw = (m.group("unit") or "").strip()
        cn_num = m.group("num")
        if not cn_num:
            continue
        # 必须包含至少一个真正的中文数字字符（避免误匹配如纯单位）
        if not any(is_chinese_number_char(c) for c in cn_num):
            continue
        v = parse_chinese_decimal(cn_num)
        if v is None:
            continue
        phrases.append(NumberPhrase(
            value=v,
            unit=normalize_unit(unit_raw),
            modifier=canonicalize_modifier(prefix or suffix),
            original=m.group(0),
            span=m.span(),
        ))

    phrases.sort(key=lambda p: p.span[0])
    return phrases


def _scan_prefix_modifier(text: str, end_pos: int) -> str:
    """从 end_pos 向前扫描 PREFIX 修饰词（中文分数等手动场景用）。"""
    for w in sorted(PREFIX_MODIFIERS, key=lambda x: -len(x)):
        s = end_pos - len(w)
        if s < 0:
            continue
        if text[s:end_pos] == w:
            # 排除前一个字符是字母 / 数字（如"big >="）
            return w
    return ""


def _scan_suffix_modifier(text: str, start_pos: int) -> str:
    for w in sorted(SUFFIX_MODIFIERS, key=lambda x: -len(x)):
        if text[start_pos:start_pos + len(w)] == w:
            return w
    return ""


# ────────────────────────────────────────────
# 集合差异判定
# ────────────────────────────────────────────


@dataclass
class NumberDiff:
    """两段文本的数值集合差异。"""
    only_in_orig: list[NumberPhrase] = field(default_factory=list)
    only_in_rewritten: list[NumberPhrase] = field(default_factory=list)

    @property
    def has_diff(self) -> bool:
        return bool(self.only_in_orig or self.only_in_rewritten)


def diff_number_phrases(
    orig: list[NumberPhrase],
    rewritten: list[NumberPhrase],
    *,
    rel_tolerance: float = 0.0,
    fraction_tolerance: float = 0.0,
) -> NumberDiff:
    """对两组 NumberPhrase 做集合 diff（双向匹配，使用 equivalent_to）。"""
    orig_used = [False] * len(orig)
    rew_used = [False] * len(rewritten)

    for i, a in enumerate(orig):
        for j, b in enumerate(rewritten):
            if rew_used[j]:
                continue
            if a.equivalent_to(b, rel_tolerance=rel_tolerance, fraction_tolerance=fraction_tolerance):
                orig_used[i] = True
                rew_used[j] = True
                break

    return NumberDiff(
        only_in_orig=[a for i, a in enumerate(orig) if not orig_used[i]],
        only_in_rewritten=[b for j, b in enumerate(rewritten) if not rew_used[j]],
    )


__all__ = [
    "NumberPhrase",
    "NumberDiff",
    "extract_all_number_phrases",
    "diff_number_phrases",
]
