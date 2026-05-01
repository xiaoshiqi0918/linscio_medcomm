"""
医学事实一致性 gate（P0-1 主入口）

用途：在改写器将段落改写后，对照原文比对医学事实是否被动；如有强 gate 失败，
回退到原文（不重试），保证医学准确性零妥协。

设计要点（决策附录 A.1-A.7）：

- 强 gate（任一失败即 REJECT_STRONG）：
    study_subjects     - S1-S6 研究对象层级
    citations          - C1 双语法引用一致性
    dosage_schedules   - D1 给药频率/时长/时机

- 弱 gate（仅记录，不阻断）：
    numbers            - N1/N2 数值与修饰等价
    dosage_amounts     - D1 复用 numbers 通道
    drugs              - G1/G2，P0 不启用

- 集成模式（I1）：
    full_scan=False    - 短路：第一个强 gate 失败立即返回（生产默认）
    full_scan=True     - 全量：跑完所有 gate（灰度期 + 离线分析）

- 故障语义（I2）：
    GateResult.PASS                - 真通过
    GateResult.PASS_BY_FAIL_OPEN   - 内部异常但放行（fail_open=True 时）
    GateResult.REJECT_STRONG       - 强 gate 失败
    GateResult.REJECT_WEAK         - 仅弱 gate 失败（hard_block=True 时也回退）
    GateResult.ERROR               - 内部异常且 fail_open=False

- 上线节奏（P1）：
    Week 1-2: hard_block=False + full_scan=True   (dry_run + 全量)
    Week 3:   hard_block=True  + full_scan=False  (生产模式)
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from .fact_guard_internal.extractors.citation_extractor import (
    check_citation_consistency,
)
from .fact_guard_internal.extractors.dosage_extractor import (
    check_dosage_schedule_consistency,
)
from .fact_guard_internal.extractors.subject_extractor import (
    check_subject_consistency,
)
from .fact_guard_internal.normalizers.number_normalizer import (
    diff_number_phrases,
    extract_all_number_phrases,
)

logger = logging.getLogger(__name__)


# ────────────────────────────────────────────
# 公共枚举与数据结构
# ────────────────────────────────────────────


class GateResult(Enum):
    PASS = "pass"
    PASS_BY_FAIL_OPEN = "pass_fail_open"
    REJECT_STRONG = "reject_strong"
    REJECT_WEAK = "reject_weak"
    ERROR = "error"


@dataclass
class FactCheckResult:
    """单次 fact_guard 检查的完整结果。"""
    result: GateResult
    failed_dimensions: list[str] = field(default_factory=list)
    details: dict[str, Any] = field(default_factory=dict)
    error_msg: Optional[str] = None

    @property
    def passed(self) -> bool:
        """对调用方：是否放行（含 fail-open）。"""
        return self.result in (GateResult.PASS, GateResult.PASS_BY_FAIL_OPEN)

    @property
    def is_normal_pass(self) -> bool:
        """是否真通过（用于监控区分 fail-open）。"""
        return self.result == GateResult.PASS

    @property
    def is_strong_reject(self) -> bool:
        return self.result == GateResult.REJECT_STRONG

    def to_log_dict(self) -> dict[str, Any]:
        """用于结构化日志输出。"""
        return {
            "result": self.result.value,
            "failed_dimensions": list(self.failed_dimensions),
            "error_msg": self.error_msg,
        }


@dataclass
class FactGuardConfig:
    """单次调用的 feature flag 配置。"""
    enable_master: bool = True
    enable_subjects: bool = True            # 强 gate
    enable_citations: bool = True           # 强 gate
    enable_dosage_schedules: bool = True    # 强 gate
    enable_numbers: bool = True             # 弱 gate
    enable_dosage_amounts: bool = True      # 弱 gate（复用 numbers 通道）
    enable_drugs: bool = False              # G2: P0 不启用

    fail_open_on_error: bool = True
    hard_block: bool = True                 # P1 决策：False=dry_run，True=真阻断
    full_scan: bool = False                 # I1：True=跑全维度（灰度/离线）

    # 弱 gate 容差
    number_rel_tolerance: float = 0.0       # 单点数值相对容差，P0 严格
    fraction_tolerance: float = 0.0         # N2：分数 ↔ 百分比容差，P0 严格


@dataclass
class FactGuardSummary:
    """生成器/改写器侧的累计统计（用于 report["fact_guard"]）。"""
    rewrites_passed: int = 0
    rewrites_pass_fail_open: int = 0
    rewrites_rejected_strong: int = 0
    rewrites_rejected_weak: int = 0
    rewrites_total: int = 0
    failed_dimensions_count: dict[str, int] = field(default_factory=dict)

    def record(self, result: FactCheckResult) -> None:
        self.rewrites_total += 1
        if result.result == GateResult.PASS:
            self.rewrites_passed += 1
        elif result.result == GateResult.PASS_BY_FAIL_OPEN:
            self.rewrites_pass_fail_open += 1
        elif result.result == GateResult.REJECT_STRONG:
            self.rewrites_rejected_strong += 1
        elif result.result == GateResult.REJECT_WEAK:
            self.rewrites_rejected_weak += 1
        for dim in result.failed_dimensions:
            self.failed_dimensions_count[dim] = (
                self.failed_dimensions_count.get(dim, 0) + 1
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "total": self.rewrites_total,
            "passed": self.rewrites_passed,
            "pass_fail_open": self.rewrites_pass_fail_open,
            "rejected_strong": self.rewrites_rejected_strong,
            "rejected_weak": self.rewrites_rejected_weak,
            "failed_dimensions_count": dict(self.failed_dimensions_count),
        }


# ────────────────────────────────────────────
# 主入口
# ────────────────────────────────────────────


# 强 gate 维度清单（顺序即短路顺序）
_STRONG_GATES = ("study_subjects", "citations", "dosage_schedules")
# 弱 gate 维度清单
_WEAK_GATES = ("numbers", "drugs")


def validate_facts_consistency(
    orig: str,
    rewritten: str,
    config: Optional[FactGuardConfig] = None,
) -> FactCheckResult:
    """主入口：对照原文检查改写文本的医学事实一致性。

    short-circuit 与 full_scan 的区别：
      - full_scan=False：第一个强 gate 失败立即返回 REJECT_STRONG，弱 gate
        不再扫描；性能模式
      - full_scan=True：跑完所有强 gate + 弱 gate，details 含完整数据；
        灰度期 / 离线分析用

    hard_block：
      - False：所有 REJECT_* 都映射成 PASS（但保留 details 用于离线分析）
        等价于 dry_run，不阻断改写器调用方
      - True：返回真实 result，调用方据此回退
    """
    cfg = config or FactGuardConfig()
    if not cfg.enable_master:
        return FactCheckResult(result=GateResult.PASS)

    if not orig or not rewritten:
        return FactCheckResult(result=GateResult.PASS)

    failed: list[str] = []
    details: dict[str, Any] = {}

    try:
        # ── 强 gate ──
        if cfg.enable_subjects:
            ok, info = check_subject_consistency(orig, rewritten)
            if not ok:
                failed.append("study_subjects")
                details["study_subjects"] = _subject_detail_to_dict(info)
                if not cfg.full_scan:
                    return _emit_strong_reject(cfg, failed, details)

        if cfg.enable_citations:
            ok, info = check_citation_consistency(orig, rewritten)
            if not ok:
                failed.append("citations")
                details["citations"] = _citation_detail_to_dict(info)
                if not cfg.full_scan:
                    return _emit_strong_reject(cfg, failed, details)

        if cfg.enable_dosage_schedules:
            ok, info = check_dosage_schedule_consistency(orig, rewritten)
            if not ok:
                failed.append("dosage_schedules")
                details["dosage_schedules"] = _dosage_detail_to_dict(info)
                if not cfg.full_scan:
                    return _emit_strong_reject(cfg, failed, details)

        # 任一强 gate 失败时（full_scan 模式才会到这里）
        strong_failed = [d for d in failed if d in _STRONG_GATES]

        # ── 弱 gate ──
        if cfg.enable_numbers:
            o_phrases = extract_all_number_phrases(orig)
            r_phrases = extract_all_number_phrases(rewritten)
            ndiff = diff_number_phrases(
                o_phrases, r_phrases,
                rel_tolerance=cfg.number_rel_tolerance,
                fraction_tolerance=cfg.fraction_tolerance,
            )
            if ndiff.has_diff:
                failed.append("numbers")
                details["numbers"] = {
                    "only_in_orig": [_np_to_dict(p) for p in ndiff.only_in_orig],
                    "only_in_rewritten": [_np_to_dict(p) for p in ndiff.only_in_rewritten],
                }

        # G1/G2：drugs P0 不启用，保留接口
        if cfg.enable_drugs:
            details["drugs"] = {"status": "module_not_implemented_in_p0"}

        # ── 汇总 ──
        weak_failed = [d for d in failed if d in _WEAK_GATES]
        if strong_failed:
            return _emit_strong_reject(cfg, failed, details)
        if weak_failed:
            return _emit_weak_reject(cfg, failed, details)
        return FactCheckResult(result=GateResult.PASS)

    except Exception as exc:  # noqa: BLE001
        logger.warning("[FactGuard] 内部异常 fail_open=%s: %s", cfg.fail_open_on_error, exc)
        if cfg.fail_open_on_error:
            return FactCheckResult(
                result=GateResult.PASS_BY_FAIL_OPEN,
                error_msg=str(exc),
                details={"partial": details, "partial_failed": list(failed)},
            )
        return FactCheckResult(
            result=GateResult.ERROR,
            error_msg=str(exc),
            failed_dimensions=list(failed),
            details=details,
        )


# ────────────────────────────────────────────
# 内部 helper
# ────────────────────────────────────────────


def _emit_strong_reject(
    cfg: FactGuardConfig,
    failed: list[str],
    details: dict[str, Any],
) -> FactCheckResult:
    if not cfg.hard_block:
        # dry_run：失败信息保留用于离线分析，但放行
        logger.warning(
            "[FactGuard DRY-RUN] would REJECT_STRONG: failed=%s",
            failed,
        )
        return FactCheckResult(
            result=GateResult.PASS,
            failed_dimensions=list(failed),
            details=details,
            error_msg=f"DRY_RUN: would_reject=reject_strong",
        )
    return FactCheckResult(
        result=GateResult.REJECT_STRONG,
        failed_dimensions=list(failed),
        details=details,
    )


def _emit_weak_reject(
    cfg: FactGuardConfig,
    failed: list[str],
    details: dict[str, Any],
) -> FactCheckResult:
    if not cfg.hard_block:
        logger.warning(
            "[FactGuard DRY-RUN] would REJECT_WEAK: failed=%s",
            failed,
        )
        return FactCheckResult(
            result=GateResult.PASS,
            failed_dimensions=list(failed),
            details=details,
            error_msg=f"DRY_RUN: would_reject=reject_weak",
        )
    return FactCheckResult(
        result=GateResult.REJECT_WEAK,
        failed_dimensions=list(failed),
        details=details,
    )


def _subject_detail_to_dict(info) -> dict[str, Any]:  # type: ignore[no-untyped-def]
    return {
        "added_layer1": sorted(info.added_layer1),
        "removed_layer1": sorted(info.removed_layer1),
        "added_layer2": sorted(info.added_layer2),
        "removed_layer2": sorted(info.removed_layer2),
    }


def _citation_detail_to_dict(info) -> dict[str, Any]:  # type: ignore[no-untyped-def]
    return {
        "orig_literature_ids": list(info.orig_literature_ids),
        "rewritten_literature_ids": list(info.rewritten_literature_ids),
        "consensus": (info.orig_consensus_count, info.rewritten_consensus_count),
        "inferences_added": sorted(set(info.rewritten_inferences) - set(info.orig_inferences)),
        "inferences_removed": sorted(set(info.orig_inferences) - set(info.rewritten_inferences)),
        "todos_added": sorted(set(info.rewritten_todos) - set(info.orig_todos)),
        "todos_removed": sorted(set(info.orig_todos) - set(info.rewritten_todos)),
    }


def _dosage_detail_to_dict(info) -> dict[str, Any]:  # type: ignore[no-untyped-def]
    return {
        "only_in_orig": [list(s) for s in info.only_in_orig],
        "only_in_rewritten": [list(s) for s in info.only_in_rewritten],
    }


def _np_to_dict(p) -> dict[str, Any]:  # type: ignore[no-untyped-def]
    return {
        "value": list(p.value) if isinstance(p.value, tuple) else p.value,
        "unit": p.unit,
        "modifier": p.modifier,
        "is_range": p.is_range,
        "is_fraction": p.is_fraction,
        "original": p.original,
    }


__all__ = [
    "GateResult",
    "FactCheckResult",
    "FactGuardConfig",
    "FactGuardSummary",
    "validate_facts_consistency",
]
