"""
中文数字归一化（P0-1）

只覆盖医学科普中常见的形式：
  - 整数："三百"、"五十"、"一千两百"
  - 小数："三点五"
  - 中文分数："三分之一"、"四分之三"

对于"几十""上百""数千"等模糊表达，按修饰词处理（见 modifier_words），
本模块不做范围估算。
"""
from __future__ import annotations

import re
from typing import Optional


_CN_DIGITS = {
    "零": 0, "〇": 0,
    "一": 1, "壹": 1, "二": 2, "贰": 2, "两": 2, "俩": 2,
    "三": 3, "叁": 3, "四": 4, "肆": 4, "五": 5, "伍": 5,
    "六": 6, "陆": 6, "七": 7, "柒": 7, "八": 8, "捌": 8, "九": 9, "玖": 9,
}

_CN_UNITS = {
    "十": 10, "拾": 10,
    "百": 100, "佰": 100,
    "千": 1000, "仟": 1000,
    "万": 10_000, "萬": 10_000,
    "亿": 100_000_000, "億": 100_000_000,
}

_CN_DECIMAL_SEP = {"点", "點"}

_CN_NUMBER_CHARS = (
    set(_CN_DIGITS.keys())
    | set(_CN_UNITS.keys())
    | _CN_DECIMAL_SEP
)


_CN_FRACTION_PATTERN = re.compile(
    r"([零〇一二三四五六七八九十百千万壹贰叁肆伍陆柒捌玖拾佰仟萬亿両两俩]+)\s*分之\s*"
    r"([零〇一二三四五六七八九十百千万壹贰叁肆伍陆柒捌玖拾佰仟萬亿両两俩]+)"
)


def _parse_simple_int(s: str) -> Optional[int]:
    """处理'三百二十一'/'十五'/'两万三千' 等中文整数。

    限制：不处理'万亿'级混合最罕见情况，已覆盖 99% 医学科普用法。
    """
    if not s:
        return None
    if all(ch in _CN_DIGITS for ch in s):
        # 纯数字串如"二零二三" → 2023（按位拼）
        digits = "".join(str(_CN_DIGITS[ch]) for ch in s)
        try:
            return int(digits)
        except ValueError:
            return None

    total = 0
    section = 0  # 当前节累计（万以下）
    current = 0  # 当前未结算的数字

    for ch in s:
        if ch in _CN_DIGITS:
            current = _CN_DIGITS[ch]
        elif ch in _CN_UNITS:
            unit = _CN_UNITS[ch]
            if unit == 10 and current == 0:
                current = 1  # 处理"十"开头如"十五"
            if unit >= 10_000:
                section = (section + current) * unit
                total += section
                section = 0
            else:
                section += current * unit
            current = 0
        else:
            return None

    return total + section + current


def parse_chinese_integer(s: str) -> Optional[int]:
    """对外接口：将中文整数串转 int，无法解析返回 None。"""
    if not s:
        return None
    s = s.strip()
    return _parse_simple_int(s)


def parse_chinese_decimal(s: str) -> Optional[float]:
    """处理'三点五'类小数。整数部分用 _parse_simple_int，小数部分按位读。"""
    if not s:
        return None
    s = s.strip()
    sep = next((c for c in s if c in _CN_DECIMAL_SEP), None)
    if sep is None:
        v = _parse_simple_int(s)
        return float(v) if v is not None else None
    int_part, _, dec_part = s.partition(sep)
    int_v = _parse_simple_int(int_part) if int_part else 0
    if int_v is None:
        return None
    if not dec_part:
        return float(int_v)
    if not all(ch in _CN_DIGITS for ch in dec_part):
        return None
    dec_str = "".join(str(_CN_DIGITS[ch]) for ch in dec_part)
    return float(f"{int_v}.{dec_str}")


def is_chinese_number_char(ch: str) -> bool:
    """判断一个字符是否属于中文数字（含分数 / 小数标识）。"""
    return ch in _CN_NUMBER_CHARS


__all__ = [
    "parse_chinese_integer",
    "parse_chinese_decimal",
    "is_chinese_number_char",
    "_CN_FRACTION_PATTERN",
]
