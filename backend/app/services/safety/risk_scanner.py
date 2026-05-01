"""
合规风险扫描入口（P0-3 / 决策附录 A.9 / A.10）

设计要点：
  1. 否定环视由 risk_words_dict 中各 RiskRule.pattern 自带（K2）
  2. 二次过滤"警示语境"——命中所在句若包含"风险 / 危险 / 副作用"等词，
     将匹配过滤掉，避免"自行注射会带来严重风险"被误判（K2）
  3. ActionLevel.LOG_ONLY 仅写日志，不出现在用户可见的 RiskScanReport
  4. UI 折叠 / 持久化由前端处理，本模块只负责生成结构化报告
"""
from __future__ import annotations

import logging
import re
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Iterable, Optional

from .risk_words_dict import (
    ALL_RULES,
    NEGATION_PREFIXES,
    WARNING_CONTEXTS,
    ActionLevel,
    RiskRule,
)

logger = logging.getLogger(__name__)


# ────────────────────────────────────────────
# 数据结构
# ────────────────────────────────────────────


@dataclass(frozen=True)
class RiskMatch:
    rule_name: str
    category: str
    action: str            # ActionLevel.value
    matched_text: str
    span: tuple[int, int]
    legal_ref: str
    user_message: str
    suggestion: str = ""


@dataclass
class RiskScanReport:
    """风险扫描完整报告。

    matches_visible：用户可见匹配（按 action 分组）
    matches_log_only：仅日志的匹配（不返回给前端展示，但保留供后端审计）
    """
    matches_by_action: dict[str, list[RiskMatch]] = field(
        default_factory=lambda: defaultdict(list)
    )
    matches_log_only: list[RiskMatch] = field(default_factory=list)

    @property
    def confirm_required(self) -> bool:
        """前端是否必须显示勾选框（CONFIRM_HARD 或 CONFIRM_SOFT 命中）"""
        return bool(
            self.matches_by_action.get(ActionLevel.CONFIRM_HARD.value)
            or self.matches_by_action.get(ActionLevel.CONFIRM_SOFT.value)
        )

    @property
    def block_required(self) -> bool:
        """是否触发硬阻断（P0 不会出现，P1 数据驱动启用）"""
        return bool(self.matches_by_action.get(ActionLevel.BLOCK.value))

    @property
    def total_visible(self) -> int:
        return sum(len(v) for v in self.matches_by_action.values())

    def to_dict(self) -> dict:
        return {
            "matches_by_action": {
                k: [_match_to_dict(m) for m in v]
                for k, v in self.matches_by_action.items()
            },
            "matches_log_only_count": len(self.matches_log_only),
            "confirm_required": self.confirm_required,
            "block_required": self.block_required,
            "total_visible": self.total_visible,
        }


def _match_to_dict(m: RiskMatch) -> dict:
    return {
        "rule_name": m.rule_name,
        "category": m.category,
        "action": m.action,
        "matched_text": m.matched_text,
        "span": list(m.span),
        "legal_ref": m.legal_ref,
        "user_message": m.user_message,
        "suggestion": m.suggestion,
    }


# ────────────────────────────────────────────
# 警示语境过滤
# ────────────────────────────────────────────


_SENTENCE_BOUNDARY = re.compile(r"[。！？；\n]")


def _local_context(text: str, span: tuple[int, int], radius: int = 50) -> str:
    """取命中位置前后 radius 字内容作为局部语境。"""
    s = max(0, span[0] - radius)
    e = min(len(text), span[1] + radius)
    return text[s:e]


def _is_in_warning_context(text: str, span: tuple[int, int]) -> bool:
    """K2 决策：命中点周边出现警示词时视为合规警示语境。"""
    ctx = _local_context(text, span, radius=50)
    return any(w in ctx for w in WARNING_CONTEXTS)


def _has_preceding_negation(text: str, span: tuple[int, int], lookback: int) -> bool:
    """K2 决策：命中位置前 ``lookback`` 字内是否包含 NEGATION_PREFIXES 任一前缀。

    Python re 模块只支持定长 lookbehind，不能用变长正则；改为命中后手动检查。
    """
    if lookback <= 0:
        return False
    s = max(0, span[0] - lookback)
    chunk = text[s:span[0]]
    return any(neg in chunk for neg in NEGATION_PREFIXES)


# ────────────────────────────────────────────
# 主入口
# ────────────────────────────────────────────


def scan_risk_words(
    text: str,
    rules: Optional[Iterable[RiskRule]] = None,
) -> RiskScanReport:
    """对文本运行所有合规风险规则。

    rules: 可指定规则子集；None 表示走 ALL_RULES。
    """
    report = RiskScanReport()
    if not text or not text.strip():
        return report

    target_rules = list(rules) if rules is not None else list(ALL_RULES)
    seen_spans: set[tuple[int, int, str]] = set()  # 同 (span, rule) 去重

    for rule in target_rules:
        for m in rule.pattern.finditer(text):
            span = m.span()
            key = (span[0], span[1], rule.name)
            if key in seen_spans:
                continue
            seen_spans.add(key)

            # K2 决策第一层：紧邻前缀否定环视
            if rule.negation_lookback and _has_preceding_negation(
                text, span, rule.negation_lookback,
            ):
                logger.info(
                    "[RiskScanner] '%s' 命中但前 %d 字含否定词，过滤：%s",
                    rule.name, rule.negation_lookback, m.group(0)[:40],
                )
                continue

            # K2 决策第二层：警示语境过滤；只对"行动建议"类规则生效，
            # 绝对化用语（治愈率 100%）即便处于"风险"段也是违规
            if rule.category in {"self_administration", "prescription_drug", "specific_dosage"}:
                if _is_in_warning_context(text, span):
                    logger.info(
                        "[RiskScanner] '%s' 命中但处于警示语境，过滤：%s",
                        rule.name, m.group(0)[:40],
                    )
                    continue

            match = RiskMatch(
                rule_name=rule.name,
                category=rule.category,
                action=rule.action.value,
                matched_text=m.group(0),
                span=span,
                legal_ref=rule.legal_ref,
                user_message=rule.user_message,
                suggestion=rule.suggestion,
            )

            if rule.action == ActionLevel.LOG_ONLY:
                report.matches_log_only.append(match)
                logger.info(
                    "[RiskScanner LOG_ONLY] rule=%s text=%s",
                    rule.name, match.matched_text,
                )
            else:
                report.matches_by_action[rule.action.value].append(match)

    return report


__all__ = [
    "RiskMatch",
    "RiskScanReport",
    "scan_risk_words",
]
