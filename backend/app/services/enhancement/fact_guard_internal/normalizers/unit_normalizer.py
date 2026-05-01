"""
单位归一化（P0-1）

要点（决策附录 A.2 / S1）：
  - "年" → "year"，"岁/周岁" → "age"。两者必须独立，避免 70 岁 ≡ 70 年。
  - 月份 / 月龄 P0 不拆分，仍归 "month"。
  - 复合单位（mg/d、mg/kg、g/L 等）必须按"较长单位优先匹配"，否则正则
    会把 "5 mg/kg" 解析成 "5 mg" 漏掉斜杠后的部分。

UNIT_ALIASES 故意不收录单字"%"等无歧义符号，匹配时由调用方处理。
"""
from __future__ import annotations

import re

UNIT_ALIASES: dict[str, str] = {
    # 百分比 / 比例
    "%": "%", "％": "%", "百分之": "%",
    "‰": "permille", "千分之": "permille",

    # 时间（持续时长）
    "年": "year", "y": "year", "Y": "year", "yr": "year", "yrs": "year",
    "个月": "month", "月": "month", "mo": "month",
    "周": "week", "礼拜": "week", "wk": "week", "wks": "week",
    "天": "day", "日": "day", "d": "day",
    "小时": "hour", "h": "hour", "hr": "hour", "hrs": "hour",
    "分钟": "minute", "min": "minute",
    "秒": "second", "s": "second", "sec": "second",

    # 年龄（与时间独立！S1 决策）
    "岁": "age", "周岁": "age",

    # 质量
    "千克": "kg", "公斤": "kg", "kg": "kg",
    "克": "g", "g": "g",
    "毫克": "mg", "mg": "mg",
    "微克": "ug", "μg": "ug", "ug": "ug",

    # 体积
    "升": "L", "L": "L", "l": "L",
    "毫升": "ml", "ml": "ml", "mL": "ml",
    "微升": "ul", "μl": "ul", "ul": "ul", "uL": "ul",

    # 长度
    "厘米": "cm", "cm": "cm",
    "毫米": "mm", "mm": "mm",
    "米": "m",

    # 计数
    "次": "times", "回": "times",
    "人": "people", "名": "people", "例": "people", "位": "people",
    "片": "tablet", "粒": "tablet", "颗": "tablet",
    "支": "ampoule",
}

# 复合单位别名 — 整体当作单一标识，不拆斜杠
COMPOUND_UNIT_ALIASES: dict[str, str] = {
    "mg/d": "mg/day", "mg/天": "mg/day", "mg/日": "mg/day",
    "mg/kg": "mg/kg", "mg/公斤": "mg/kg",
    "mg/kg/d": "mg/kg/day", "mg/kg/天": "mg/kg/day",
    "g/d": "g/day", "g/天": "g/day", "g/日": "g/day",
    "g/L": "g/L", "g/l": "g/L",
    "mg/L": "mg/L", "mg/l": "mg/L",
    "mg/dL": "mg/dL", "mg/dl": "mg/dL",
    "mmol/L": "mmol/L",
    "次/天": "times/day", "次/日": "times/day", "次/周": "times/week",
    "次/分钟": "times/min", "次/分": "times/min",
}


def normalize_unit(raw: str) -> str:
    """单位字符串归一化。匹配不到时返回原字符串（小写化处理 ASCII）。

    优先级：复合单位 → 单一单位 → 原样小写。
    """
    if not raw:
        return ""
    s = raw.strip()
    if s in COMPOUND_UNIT_ALIASES:
        return COMPOUND_UNIT_ALIASES[s]
    if s in UNIT_ALIASES:
        return UNIT_ALIASES[s]
    return s


# 用于正则匹配的"所有单位别名按长度倒序"列表
# longer-first 保证 "mg/kg" 整体先于 "mg" 被匹配（regex 左替代是 leftmost）
_ALL_ALIASES = sorted(
    set(UNIT_ALIASES.keys()) | set(COMPOUND_UNIT_ALIASES.keys()),
    key=lambda k: -len(k),
)

UNIT_REGEX_FRAGMENT = "(?:" + "|".join(re.escape(k) for k in _ALL_ALIASES) + ")"
"""可嵌入大型正则的单位匹配片段，按长度倒序避免短单位先匹配。"""


__all__ = [
    "UNIT_ALIASES",
    "COMPOUND_UNIT_ALIASES",
    "normalize_unit",
    "UNIT_REGEX_FRAGMENT",
]
