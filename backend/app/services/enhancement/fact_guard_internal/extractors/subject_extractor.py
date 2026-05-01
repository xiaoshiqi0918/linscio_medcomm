"""
研究对象一致性强 gate（P0-1 / 决策 S1-S6）

职责：
  1. 抽取文本中所有 SubjectMatch
  2. 同段消解 IN_VIVO_AMBIGUOUS（决策 S2）
  3. 比较原文与改写后的 layer1 / layer2 集合，集合不等即视为强 gate 失败
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from ..dictionaries.study_subjects import (
    ALL_SUBJECT_TERMS,
    TERM_TO_LAYER1,
    TERM_TO_LAYER2,
)


# ────────────────────────────────────────────
# 数据结构
# ────────────────────────────────────────────


@dataclass(frozen=True)
class SubjectMatch:
    term: str          # 原始匹配文本（保留大小写）
    layer1: str        # HUMAN / ANIMAL / IN_VITRO / IN_VIVO_AMBIGUOUS
    layer2: str        # HUMAN_GENERAL / ANIMAL_RODENT 等
    span: tuple[int, int]


@dataclass
class SubjectInconsistency:
    """研究对象一致性失败的详情。"""
    orig_layer1_set: set[str]
    rewritten_layer1_set: set[str]
    orig_layer2_set: set[str]
    rewritten_layer2_set: set[str]
    added_layer1: set[str]
    removed_layer1: set[str]
    added_layer2: set[str]
    removed_layer2: set[str]

    @property
    def has_layer1_diff(self) -> bool:
        return bool(self.added_layer1 or self.removed_layer1)

    @property
    def has_layer2_diff(self) -> bool:
        return bool(self.added_layer2 or self.removed_layer2)


# ────────────────────────────────────────────
# 提取
# ────────────────────────────────────────────


# 按长度倒序构建词典正则（最长匹配优先）
_TERM_PATTERN = re.compile(
    "|".join(re.escape(t) for t in ALL_SUBJECT_TERMS),
    flags=re.IGNORECASE,
)


def extract_subjects(text: str) -> list[SubjectMatch]:
    """从文本提取所有研究对象匹配（保留 span 用于段落定位与同段消解）。"""
    if not text:
        return []
    matches: list[SubjectMatch] = []
    for m in _TERM_PATTERN.finditer(text):
        token = m.group(0)
        key = token.lower() if token.isascii() else token
        layer2 = TERM_TO_LAYER2.get(key)
        layer1 = TERM_TO_LAYER1.get(key)
        if not layer1 or not layer2:
            continue
        matches.append(SubjectMatch(
            term=token,
            layer1=layer1,
            layer2=layer2,
            span=m.span(),
        ))
    return matches


# ────────────────────────────────────────────
# IN_VIVO_AMBIGUOUS 同段消解（决策 S2）
# ────────────────────────────────────────────


_PARAGRAPH_SPLIT = re.compile(r"\n\s*\n+|\r\n\s*\r\n+")


def _paragraph_spans(text: str) -> list[tuple[int, int]]:
    """返回每个段落的 (start, end) 字符范围。空段落跳过。"""
    if not text:
        return []
    spans: list[tuple[int, int]] = []
    pos = 0
    for m in _PARAGRAPH_SPLIT.finditer(text):
        if m.start() > pos:
            spans.append((pos, m.start()))
        pos = m.end()
    if pos < len(text):
        spans.append((pos, len(text)))
    return spans


def consolidate_ambiguous_subjects(
    matches: list[SubjectMatch],
    text: str,
) -> list[SubjectMatch]:
    """同段消解：如果某段内已有明确 HUMAN 或 ANIMAL 类，过滤掉该段所有
    IN_VIVO_AMBIGUOUS 项（它们被解释为该明确类的辅助说明）。
    """
    if not matches or not text:
        return matches

    paragraphs = _paragraph_spans(text)
    if not paragraphs:
        return matches

    # 把 match 按段落归类
    para_matches: dict[int, list[SubjectMatch]] = {}
    for m in matches:
        for idx, (s, e) in enumerate(paragraphs):
            if s <= m.span[0] < e:
                para_matches.setdefault(idx, []).append(m)
                break

    kept: list[SubjectMatch] = []
    for idx, group in para_matches.items():
        layers = {g.layer1 for g in group}
        if "HUMAN" in layers or "ANIMAL" in layers:
            kept.extend(g for g in group if g.layer1 != "IN_VIVO_AMBIGUOUS")
        else:
            kept.extend(group)

    kept.sort(key=lambda m: m.span[0])
    return kept


# ────────────────────────────────────────────
# 一致性检查（强 gate）
# ────────────────────────────────────────────


def check_subject_consistency(orig: str, rewritten: str) -> tuple[bool, SubjectInconsistency]:
    """检查研究对象在改写前后是否保持一致。

    返回 (passed, detail)：
      passed = True  → layer1 + layer2 集合都相等
      passed = False → 任一层级差异即失败（强 gate）
    """
    orig_matches = consolidate_ambiguous_subjects(extract_subjects(orig), orig)
    rew_matches = consolidate_ambiguous_subjects(extract_subjects(rewritten), rewritten)

    orig_l1 = {m.layer1 for m in orig_matches}
    rew_l1 = {m.layer1 for m in rew_matches}
    orig_l2 = {m.layer2 for m in orig_matches}
    rew_l2 = {m.layer2 for m in rew_matches}

    detail = SubjectInconsistency(
        orig_layer1_set=orig_l1,
        rewritten_layer1_set=rew_l1,
        orig_layer2_set=orig_l2,
        rewritten_layer2_set=rew_l2,
        added_layer1=rew_l1 - orig_l1,
        removed_layer1=orig_l1 - rew_l1,
        added_layer2=rew_l2 - orig_l2,
        removed_layer2=orig_l2 - rew_l2,
    )
    passed = not (detail.has_layer1_diff or detail.has_layer2_diff)
    return passed, detail


__all__ = [
    "SubjectMatch",
    "SubjectInconsistency",
    "extract_subjects",
    "consolidate_ambiguous_subjects",
    "check_subject_consistency",
]
