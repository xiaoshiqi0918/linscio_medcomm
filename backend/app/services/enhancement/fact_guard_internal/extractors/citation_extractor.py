"""
引用一致性强 gate（P0-1 / 决策 C1）

支持的引用语法：
  [文献N]            - 项目早期主用
  [N]                - 项目当前主用（C1：双语法都识别）
  [共识]             - 公认医学知识
  [推断: ...]        - 基于文献的推断（语义内容须保持）
  [[待补充: ...]]    - 文献不足占位（语义内容须保持）

不识别（避免误判）：
  化学式 [H+] [Cl-]  - 用否定环视排除
  数学符号 [3][4]    - 边界情况，接受小概率误识
  内部标签如 [图]    - 由项目其它模块处理
"""
from __future__ import annotations

import re
from dataclasses import dataclass


# ────────────────────────────────────────────
# 数据结构
# ────────────────────────────────────────────


@dataclass(frozen=True)
class CitationSignature:
    """文章引用结构指纹。集合相等 == 一致。

    literature_ids: 排序后的文献编号 tuple（multiset 由后续 diff 处理）
    consensus_count: 共识标注数量
    inference_contents: 推断内容元组（语义需保持）
    todo_contents:     待补充占位元组（语义需保持）
    """
    literature_ids: tuple[int, ...]
    consensus_count: int
    inference_contents: tuple[str, ...]
    todo_contents: tuple[str, ...]


@dataclass
class CitationInconsistency:
    """引用一致性失败的详情。"""
    orig_literature_ids: tuple[int, ...]
    rewritten_literature_ids: tuple[int, ...]
    orig_consensus_count: int
    rewritten_consensus_count: int
    orig_inferences: tuple[str, ...]
    rewritten_inferences: tuple[str, ...]
    orig_todos: tuple[str, ...]
    rewritten_todos: tuple[str, ...]


# ────────────────────────────────────────────
# 正则
# ────────────────────────────────────────────

# [文献N] 优先匹配（避免被 [N] 模式提前消费）
_LITERATURE_PATTERN = re.compile(r"\[\s*文献\s*(\d{1,3})\s*\]")

# [N] 简单数字引用：前后否定环视排除化学式 / 化学符号
#   前面不能是字母 / + / -（避免 [H+]、[Cl-]、F[18]）
#   数字后不能是 + / -（避免 [Cl-] 这种已经在前置否定中处理，再加一层稳）
_SIMPLE_NUM_PATTERN = re.compile(
    r"(?<![A-Za-z+\-])"
    r"\[\s*(\d{1,3})\s*\]"
    r"(?![+\-])"
)

_CONSENSUS_PATTERN = re.compile(r"\[\s*共识\s*\]")

# [推断: 内容] / [推断:内容]
_INFERENCE_PATTERN = re.compile(r"\[\s*推断\s*[:：]\s*([^\]]+?)\s*\]")

# [[待补充: 内容]] / [[待补充:内容]]
_TODO_PATTERN = re.compile(r"\[\[\s*待补充\s*[:：]\s*([^\]]+?)\s*\]\]")


# ────────────────────────────────────────────
# 提取
# ────────────────────────────────────────────


def extract_citation_signature(text: str) -> CitationSignature:
    """提取整篇引用指纹（multiset 风格：相同 id 出现多次按多次保留）。"""
    if not text:
        return CitationSignature((), 0, (), ())

    # 先剥离 [[待补充: ...]]，避免内层 ":" 被误解
    todo_matches = _TODO_PATTERN.findall(text)
    text_after_todo = _TODO_PATTERN.sub(" ", text)

    inference_matches = _INFERENCE_PATTERN.findall(text_after_todo)
    text_after_inf = _INFERENCE_PATTERN.sub(" ", text_after_todo)

    # 文献编号：先 [文献N] 后 [N]
    lit_ids: list[int] = []
    for m in _LITERATURE_PATTERN.finditer(text_after_inf):
        try:
            lit_ids.append(int(m.group(1)))
        except ValueError:
            continue
    text_after_lit_named = _LITERATURE_PATTERN.sub(" ", text_after_inf)

    for m in _SIMPLE_NUM_PATTERN.finditer(text_after_lit_named):
        try:
            lit_ids.append(int(m.group(1)))
        except ValueError:
            continue

    consensus_count = len(_CONSENSUS_PATTERN.findall(text))

    return CitationSignature(
        literature_ids=tuple(sorted(lit_ids)),
        consensus_count=consensus_count,
        inference_contents=tuple(s.strip() for s in inference_matches),
        todo_contents=tuple(s.strip() for s in todo_matches),
    )


# ────────────────────────────────────────────
# 一致性检查
# ────────────────────────────────────────────


def check_citation_consistency(orig: str, rewritten: str) -> tuple[bool, CitationInconsistency]:
    """改写前后引用一致性强 gate。

    通过条件（全部满足才视为通过）：
      1. literature_ids multiset 完全相等
      2. consensus_count 完全相等
      3. inference_contents 集合相等（顺序可变）
      4. todo_contents 集合相等
    """
    sig_o = extract_citation_signature(orig)
    sig_r = extract_citation_signature(rewritten)

    detail = CitationInconsistency(
        orig_literature_ids=sig_o.literature_ids,
        rewritten_literature_ids=sig_r.literature_ids,
        orig_consensus_count=sig_o.consensus_count,
        rewritten_consensus_count=sig_r.consensus_count,
        orig_inferences=sig_o.inference_contents,
        rewritten_inferences=sig_r.inference_contents,
        orig_todos=sig_o.todo_contents,
        rewritten_todos=sig_r.todo_contents,
    )

    passed = (
        sig_o.literature_ids == sig_r.literature_ids
        and sig_o.consensus_count == sig_r.consensus_count
        and set(sig_o.inference_contents) == set(sig_r.inference_contents)
        and set(sig_o.todo_contents) == set(sig_r.todo_contents)
    )
    return passed, detail


__all__ = [
    "CitationSignature",
    "CitationInconsistency",
    "extract_citation_signature",
    "check_citation_consistency",
]
