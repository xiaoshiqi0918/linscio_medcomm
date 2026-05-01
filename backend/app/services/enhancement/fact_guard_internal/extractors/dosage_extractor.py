"""
给药方案 / 剂量数值（P0-1 / 决策 D1）

D1 拆分：
  dosage_amounts (弱 gate):
    - "50mg" / "约 50mg" / "5-10 mg/kg"
    - 用 NumberPhrase 接口比对，与 numbers gate 共用归一化能力

  dosage_schedules (强 gate):
    - "每天 3 次"、"每周 2 次"（频率）
    - "疗程 7 天"、"连服 14 天"（时长）
    - "睡前 / 餐前 / 餐后 / 空腹"（时机）
    - 整体匹配作为不可拆分签名；任一改变（频率 / 时长 / 时机）都视为强 gate 失败

dosage_amounts 的改变交由 numbers gate 报告（弱 gate，仅记录日志），不在
本模块再做一次 diff，避免重复。
"""
from __future__ import annotations

import re
from dataclasses import dataclass


# ────────────────────────────────────────────
# 数据结构
# ────────────────────────────────────────────


@dataclass(frozen=True)
class DosageSchedule:
    """给药方案不可拆分签名。

    任一字段改变都视为强 gate 失败：
      frequency: "每天3次" / "每周2次" / "3次/天"
      duration:  "疗程7天" / "连服14天"
      timing:    "睡前" / "餐前" / "餐后" / "空腹" / "晨起"
    """
    frequency: str = ""
    duration: str = ""
    timing: str = ""
    span: tuple[int, int] = (0, 0)

    def signature(self) -> tuple[str, str, str]:
        """用于集合比较的签名（忽略 span）。"""
        return (
            _normalize_frequency(self.frequency),
            _normalize_duration(self.duration),
            self.timing.strip(),
        )


@dataclass
class DosageScheduleInconsistency:
    orig_signatures: list[tuple[str, str, str]]
    rewritten_signatures: list[tuple[str, str, str]]
    only_in_orig: list[tuple[str, str, str]]
    only_in_rewritten: list[tuple[str, str, str]]


# ────────────────────────────────────────────
# 正则
# ────────────────────────────────────────────

_FREQ_PATTERN = re.compile(
    r"(?:"
    r"每\s*[天日周月]\s*\d+\s*次|"
    r"每\s*\d+\s*[天日周月]\s*\d+\s*次|"
    r"\d+\s*次\s*/\s*[天日周月]|"
    r"一\s*天\s*\d+\s*次|"
    r"每\s*[天日周月]"  # 兜底"每天"等
    r")"
)

_DURATION_PATTERN = re.compile(
    r"(?:"
    r"疗程\s*\d+\s*[天日周月年]|"
    r"连服\s*\d+\s*[天日周月]|"
    r"持续\s*\d+\s*[天日周月]|"
    r"服用\s*\d+\s*[天日周月]"
    r")"
)

_TIMING_PATTERN = re.compile(
    r"(?:睡前|餐前|餐后|空腹|饭前|饭后|晨起|临睡前|晨服|晚服|午饭后|早餐前|早餐后)"
)


# ────────────────────────────────────────────
# 归一化
# ────────────────────────────────────────────


def _normalize_frequency(s: str) -> str:
    """把"3次/天"和"每天3次"归一成同一签名。"""
    if not s:
        return ""
    s = s.strip().replace(" ", "")
    # "3次/天" → "每天3次"
    m = re.match(r"(\d+)次/([天日周月])", s)
    if m:
        return f"每{m.group(2)}{m.group(1)}次"
    # "一天3次" → "每天3次"
    m = re.match(r"一天(\d+)次", s)
    if m:
        return f"每天{m.group(1)}次"
    # 把"日"统一成"天"，方便比较
    s = s.replace("日", "天")
    return s


def _normalize_duration(s: str) -> str:
    if not s:
        return ""
    return s.strip().replace(" ", "").replace("日", "天")


# ────────────────────────────────────────────
# 抽取
# ────────────────────────────────────────────


def extract_dosage_schedules(text: str) -> list[DosageSchedule]:
    """从文本提取所有 DosageSchedule（频率 / 时长 / 时机）。

    每个匹配点产出独立的 DosageSchedule。如果同一句中三种都出现，会拆成
    三个 schedule，比较时按集合而非顺序——这是合理的，因为"睡前每天 3 次
    疗程 7 天"调换"睡前 / 每天 3 次 / 疗程 7 天"次序不影响事实。
    """
    if not text:
        return []
    schedules: list[DosageSchedule] = []

    for m in _FREQ_PATTERN.finditer(text):
        schedules.append(DosageSchedule(frequency=m.group(0), span=m.span()))
    for m in _DURATION_PATTERN.finditer(text):
        schedules.append(DosageSchedule(duration=m.group(0), span=m.span()))
    for m in _TIMING_PATTERN.finditer(text):
        schedules.append(DosageSchedule(timing=m.group(0), span=m.span()))

    schedules.sort(key=lambda s: s.span[0])
    return schedules


# ────────────────────────────────────────────
# 一致性检查
# ────────────────────────────────────────────


def check_dosage_schedule_consistency(
    orig: str,
    rewritten: str,
) -> tuple[bool, DosageScheduleInconsistency]:
    """强 gate：给药方案集合不变。"""
    o = [s.signature() for s in extract_dosage_schedules(orig)]
    r = [s.signature() for s in extract_dosage_schedules(rewritten)]

    o_sorted = sorted(o)
    r_sorted = sorted(r)

    o_multiset = list(o_sorted)
    only_in_orig: list[tuple[str, str, str]] = []
    for sig in o_sorted:
        if sig in r_sorted:
            r_sorted.remove(sig)
        else:
            only_in_orig.append(sig)

    r_remaining = sorted(r)
    o_match = list(o_multiset)
    only_in_rewritten: list[tuple[str, str, str]] = []
    for sig in r_remaining:
        if sig in o_match:
            o_match.remove(sig)
        else:
            only_in_rewritten.append(sig)

    detail = DosageScheduleInconsistency(
        orig_signatures=o_multiset,
        rewritten_signatures=sorted(r),
        only_in_orig=only_in_orig,
        only_in_rewritten=only_in_rewritten,
    )
    passed = not only_in_orig and not only_in_rewritten
    return passed, detail


__all__ = [
    "DosageSchedule",
    "DosageScheduleInconsistency",
    "extract_dosage_schedules",
    "check_dosage_schedule_consistency",
]
