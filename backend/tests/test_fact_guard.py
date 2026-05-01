"""
P0-1 fact_guard 单元测试集

覆盖决策附录 A.1-A.7 全部 16 项设计点 + I1/I2 集成行为：

normalizers (N1, N2, S1)
  - 模糊估算修饰等价类合并
  - 分数与百分比 P0 严格不互换
  - "年" / "岁" 拆分

study_subjects (S2, S3, S4, S5, S6)
  - IN_VIVO_AMBIGUOUS 同段消解
  - 不收录 "subject"
  - HUMAN_PATIENTS 仅泛指
  - 受试者 / 志愿者 不拆分
  - 词典冲突报错

citations (C1)
  - [文献N] 与 [N] 双语法
  - 化学式 [H+] 不被误识别

dosage (D1)
  - dosage_schedules 强 gate

集成 (I1, I2, P1)
  - short-circuit / full_scan
  - PASS_BY_FAIL_OPEN
  - hard_block dry_run 模式

运行：
  pytest backend/tests/test_fact_guard.py -v
"""
from __future__ import annotations

import pytest


# ────────────────────────────────────────────
# normalizers
# ────────────────────────────────────────────


class TestChineseNumber:
    def test_integer(self) -> None:
        from app.services.enhancement.fact_guard_internal.normalizers.chinese_number import (
            parse_chinese_integer,
        )
        assert parse_chinese_integer("十五") == 15
        assert parse_chinese_integer("三百二十一") == 321
        assert parse_chinese_integer("两万三千") == 23000
        assert parse_chinese_integer("二零二三") == 2023

    def test_decimal(self) -> None:
        from app.services.enhancement.fact_guard_internal.normalizers.chinese_number import (
            parse_chinese_decimal,
        )
        assert parse_chinese_decimal("三点五") == 3.5
        assert parse_chinese_decimal("十点二") == 10.2


class TestUnitNormalizer:
    def test_year_age_split_S1(self) -> None:
        """决策 S1：年(time) ≠ 岁(age)"""
        from app.services.enhancement.fact_guard_internal.normalizers.unit_normalizer import (
            normalize_unit,
        )
        assert normalize_unit("年") == "year"
        assert normalize_unit("岁") == "age"
        assert normalize_unit("周岁") == "age"
        assert normalize_unit("年") != normalize_unit("岁"), "年和岁必须独立"

    def test_compound_unit(self) -> None:
        """复合单位整体匹配，不拆斜杠"""
        from app.services.enhancement.fact_guard_internal.normalizers.unit_normalizer import (
            normalize_unit,
        )
        assert normalize_unit("mg/kg") == "mg/kg"
        assert normalize_unit("mg/d") == "mg/day"


class TestModifierEquivalence:
    def test_fuzzy_estimate_class_merged_N1(self) -> None:
        """决策 N1：'约' / '左右' / '大约' 等都属于同一等价类"""
        from app.services.enhancement.fact_guard_internal.normalizers.modifier_words import (
            modifiers_equivalent,
        )
        assert modifiers_equivalent("约", "左右")
        assert modifiers_equivalent("大约", "前后")
        assert modifiers_equivalent("接近", "约莫")

    def test_distinct_classes(self) -> None:
        """超过类、不到类、估算类互不等价"""
        from app.services.enhancement.fact_guard_internal.normalizers.modifier_words import (
            modifiers_equivalent,
        )
        assert not modifiers_equivalent("约", "超过")
        assert not modifiers_equivalent("超过", "不到")


class TestNumberPhraseExtraction:
    def test_arabic_with_modifier(self) -> None:
        from app.services.enhancement.fact_guard_internal.normalizers.number_normalizer import (
            extract_all_number_phrases,
        )
        ps = extract_all_number_phrases("约 15% 的患者出现不良反应")
        assert len(ps) == 1
        assert ps[0].value == 15.0
        assert ps[0].unit == "%"
        assert ps[0].modifier  # 不空

    def test_about_15_equiv_15_around_N1(self) -> None:
        """N1: 约 15% ≡ 15% 左右"""
        from app.services.enhancement.fact_guard_internal.normalizers.number_normalizer import (
            extract_all_number_phrases,
        )
        a = extract_all_number_phrases("约 15% 患者")[0]
        b = extract_all_number_phrases("15% 左右患者")[0]
        assert a.equivalent_to(b)

    def test_fraction_not_equivalent_to_percent_N2(self) -> None:
        """决策 N2：P0 严格不互换"""
        from app.services.enhancement.fact_guard_internal.normalizers.number_normalizer import (
            NumberPhrase,
            extract_all_number_phrases,
        )
        cn_third = extract_all_number_phrases("三分之一的人")[0]
        percent33 = NumberPhrase(value=33.0, unit="%")
        assert not cn_third.equivalent_to(percent33)
        assert not cn_third.equivalent_to(percent33, fraction_tolerance=0.0)

    def test_fraction_tolerance_hook_for_p1(self) -> None:
        """N2 P1 hook：当 fraction_tolerance > 0 时允许同精度等价转换"""
        from app.services.enhancement.fact_guard_internal.normalizers.number_normalizer import (
            NumberPhrase,
            extract_all_number_phrases,
        )
        cn_third = extract_all_number_phrases("约三分之一的人")[0]
        percent33 = NumberPhrase(value=33.0, unit="%", modifier="约")
        assert cn_third.equivalent_to(percent33, fraction_tolerance=0.01)

    def test_arabic_fraction(self) -> None:
        from app.services.enhancement.fact_guard_internal.normalizers.number_normalizer import (
            extract_all_number_phrases,
        )
        ps = extract_all_number_phrases("约 1/3 的人群")
        assert len(ps) >= 1
        assert ps[0].is_fraction
        assert ps[0].value == (1, 3)

    def test_compound_unit_priority(self) -> None:
        """5 mg/kg 整体匹配，不被拆成 5 mg + 杂项"""
        from app.services.enhancement.fact_guard_internal.normalizers.number_normalizer import (
            extract_all_number_phrases,
        )
        ps = extract_all_number_phrases("小鼠 5 mg/kg 安全。")
        assert any(p.unit == "mg/kg" for p in ps)


# ────────────────────────────────────────────
# study_subjects
# ────────────────────────────────────────────


class TestSubjectDictionary:
    def test_no_conflict_S6(self) -> None:
        """决策 S6：词典冲突在 import 时即报错（启动 fail-fast）"""
        # 重新 import 即可触发 _build_term_to_layer2，无冲突时不会报错
        from app.services.enhancement.fact_guard_internal.dictionaries import (
            study_subjects,
        )
        assert study_subjects.TERM_TO_LAYER2

    def test_subject_word_excluded_S3(self) -> None:
        """决策 S3：英文 'subject' 不收录"""
        from app.services.enhancement.fact_guard_internal.dictionaries.study_subjects import (
            TERM_TO_LAYER2,
        )
        assert "subject" not in TERM_TO_LAYER2
        assert "subjects" not in TERM_TO_LAYER2

    def test_volunteer_subject_in_general_S5(self) -> None:
        """决策 S5：志愿者 / 受试者 不拆分，都归 HUMAN_GENERAL"""
        from app.services.enhancement.fact_guard_internal.dictionaries.study_subjects import (
            TERM_TO_LAYER2,
        )
        assert TERM_TO_LAYER2["志愿者"] == "HUMAN_GENERAL"
        assert TERM_TO_LAYER2["受试者"] == "HUMAN_GENERAL"


class TestSubjectExtractor:
    def test_basic_animal_human(self) -> None:
        from app.services.enhancement.fact_guard_internal.extractors.subject_extractor import (
            extract_subjects,
        )
        ms = extract_subjects("小鼠和大鼠模型上观察到的现象")
        assert {m.layer1 for m in ms} == {"ANIMAL"}
        ms2 = extract_subjects("成年患者的反应")
        assert "HUMAN" in {m.layer1 for m in ms2}

    def test_in_vivo_consolidation_S2(self) -> None:
        """决策 S2：同段已有明确 ANIMAL 时，IN_VIVO_AMBIGUOUS 被消解"""
        from app.services.enhancement.fact_guard_internal.extractors.subject_extractor import (
            check_subject_consistency,
        )
        ok, _ = check_subject_consistency(
            "小鼠 in vivo 实验显示效果",
            "在小鼠的体内实验中可看到效果",
        )
        assert ok, "同段已有 ANIMAL，IN_VIVO_AMBIGUOUS 应被消解"

    def test_subject_change_detected(self) -> None:
        """小鼠 → 患者：必然失败（强 gate 关键场景）"""
        from app.services.enhancement.fact_guard_internal.extractors.subject_extractor import (
            check_subject_consistency,
        )
        ok, info = check_subject_consistency(
            "小鼠实验显示该药物降低肿瘤体积 40%。",
            "临床患者中观察到肿瘤体积降低 40%。",
        )
        assert not ok
        assert "ANIMAL" in info.removed_layer1 or "HUMAN" in info.added_layer1


# ────────────────────────────────────────────
# citations
# ────────────────────────────────────────────


class TestCitationExtractor:
    def test_dual_syntax_C1(self) -> None:
        """决策 C1：[文献N] 和 [N] 都能识别"""
        from app.services.enhancement.fact_guard_internal.extractors.citation_extractor import (
            extract_citation_signature,
        )
        sig = extract_citation_signature("研究 [文献1] 和综述 [2] 都说明了这一点。")
        assert 1 in sig.literature_ids
        assert 2 in sig.literature_ids

    def test_chemistry_not_misextracted_C1(self) -> None:
        """[H+] / [Cl-] 等化学式不应被识别为引用"""
        from app.services.enhancement.fact_guard_internal.extractors.citation_extractor import (
            extract_citation_signature,
        )
        sig = extract_citation_signature("血液中 [H+] 浓度变化和 [Cl-] 离子。")
        assert sig.literature_ids == ()

    def test_inference_and_todo(self) -> None:
        from app.services.enhancement.fact_guard_internal.extractors.citation_extractor import (
            extract_citation_signature,
        )
        sig = extract_citation_signature(
            "结论可能与 X 相关[推断: 基于代谢机制]。[[待补充: 需要长期随访数据]]"
        )
        assert sig.inference_contents == ("基于代谢机制",)
        assert sig.todo_contents == ("需要长期随访数据",)

    def test_citation_loss(self) -> None:
        from app.services.enhancement.fact_guard_internal.extractors.citation_extractor import (
            check_citation_consistency,
        )
        ok, _ = check_citation_consistency(
            "研究 [1] 显示有效率 75%。",
            "研究显示有效率 75%。",
        )
        assert not ok


# ────────────────────────────────────────────
# dosage_schedules
# ────────────────────────────────────────────


class TestDosageSchedule:
    def test_frequency_change_D1(self) -> None:
        from app.services.enhancement.fact_guard_internal.extractors.dosage_extractor import (
            check_dosage_schedule_consistency,
        )
        ok, _ = check_dosage_schedule_consistency(
            "建议每天 3 次。",
            "建议每天 2 次。",
        )
        assert not ok

    def test_duration_change(self) -> None:
        from app.services.enhancement.fact_guard_internal.extractors.dosage_extractor import (
            check_dosage_schedule_consistency,
        )
        ok, _ = check_dosage_schedule_consistency(
            "疗程 7 天即可。",
            "疗程 14 天为宜。",
        )
        assert not ok

    def test_timing_change(self) -> None:
        from app.services.enhancement.fact_guard_internal.extractors.dosage_extractor import (
            check_dosage_schedule_consistency,
        )
        ok, _ = check_dosage_schedule_consistency(
            "睡前服用最佳。",
            "餐后服用最佳。",
        )
        assert not ok

    def test_normalize_3_times_per_day(self) -> None:
        """'3次/天' 应该归一化到与 '每天3次' 等价"""
        from app.services.enhancement.fact_guard_internal.extractors.dosage_extractor import (
            check_dosage_schedule_consistency,
        )
        ok, _ = check_dosage_schedule_consistency(
            "每天 3 次。",
            "3 次/天。",
        )
        assert ok


# ────────────────────────────────────────────
# fact_guard 主入口（I1, I2, P1）
# ────────────────────────────────────────────


class TestFactGuardIntegration:
    def test_pass_case(self) -> None:
        """合法改写：句式重组，事实保留"""
        from app.services.enhancement.fact_guard import (
            GateResult,
            validate_facts_consistency,
        )
        r = validate_facts_consistency(
            "约 15% 的患者出现不良反应 [1]。",
            "15% 左右的患者会有不良反应 [1]。",
        )
        assert r.result == GateResult.PASS
        assert r.is_normal_pass

    def test_strong_reject_subjects(self) -> None:
        from app.services.enhancement.fact_guard import (
            GateResult,
            validate_facts_consistency,
        )
        r = validate_facts_consistency(
            "小鼠实验显示该药物降低肿瘤 40% [1]。",
            "临床患者肿瘤减少 40% [1]。",
        )
        assert r.result == GateResult.REJECT_STRONG
        assert "study_subjects" in r.failed_dimensions

    def test_strong_reject_citation_loss(self) -> None:
        from app.services.enhancement.fact_guard import (
            GateResult,
            validate_facts_consistency,
        )
        r = validate_facts_consistency(
            "研究 [1] 显示有效率 75%。",
            "研究显示有效率 75%。",
        )
        assert r.result == GateResult.REJECT_STRONG
        assert "citations" in r.failed_dimensions

    def test_weak_reject_numbers(self) -> None:
        from app.services.enhancement.fact_guard import (
            GateResult,
            validate_facts_consistency,
        )
        r = validate_facts_consistency(
            "约 15% 的患者出现不良反应。",
            "15.3% 的患者出现不良反应。",
        )
        assert r.result == GateResult.REJECT_WEAK

    def test_short_circuit_I1_default(self) -> None:
        """I1 默认 short-circuit：subjects 失败时 numbers 不再扫描"""
        from app.services.enhancement.fact_guard import (
            FactGuardConfig,
            validate_facts_consistency,
        )
        cfg = FactGuardConfig(full_scan=False)
        r = validate_facts_consistency(
            "小鼠实验显示效果 80% [1]。",
            "临床患者疗效 90% [1]。",  # 同时改了 subject 和 number
            cfg,
        )
        # short-circuit：只报告 study_subjects，不会再到 numbers
        assert r.failed_dimensions == ["study_subjects"]

    def test_full_scan_I1(self) -> None:
        """I1 full_scan=True：跑全维度，details 包含所有失败项"""
        from app.services.enhancement.fact_guard import (
            FactGuardConfig,
            validate_facts_consistency,
        )
        cfg = FactGuardConfig(full_scan=True)
        r = validate_facts_consistency(
            "小鼠实验显示效果 80% [1]。",
            "临床患者疗效 90% [1]。",
            cfg,
        )
        assert "study_subjects" in r.failed_dimensions
        assert "numbers" in r.failed_dimensions

    def test_dry_run_P1_hard_block_false(self) -> None:
        """P1 决策：hard_block=False 时所有 REJECT 映射成 PASS（保留 details）"""
        from app.services.enhancement.fact_guard import (
            FactGuardConfig,
            GateResult,
            validate_facts_consistency,
        )
        cfg = FactGuardConfig(hard_block=False, full_scan=True)
        r = validate_facts_consistency(
            "小鼠实验。",
            "临床患者。",
            cfg,
        )
        assert r.result == GateResult.PASS
        assert r.passed
        assert r.failed_dimensions == ["study_subjects"]
        assert r.error_msg and "DRY_RUN" in r.error_msg

    def test_fail_open_I2(self) -> None:
        """I2：内部异常时 fail_open=True 返回 PASS_BY_FAIL_OPEN"""
        from app.services.enhancement import fact_guard
        from app.services.enhancement.fact_guard import (
            FactGuardConfig,
            GateResult,
        )

        # 通过 monkey-patch 强制 check_subject_consistency 抛异常
        def _boom(*args, **kwargs):
            raise RuntimeError("simulated failure")

        original = fact_guard.check_subject_consistency
        try:
            fact_guard.check_subject_consistency = _boom
            r = fact_guard.validate_facts_consistency(
                "原文",
                "改写",
                FactGuardConfig(fail_open_on_error=True),
            )
            assert r.result == GateResult.PASS_BY_FAIL_OPEN
            assert r.passed
            assert not r.is_normal_pass, "fail-open 不应算作 normal_pass"
        finally:
            fact_guard.check_subject_consistency = original


class TestFactGuardSummary:
    def test_record_each_result(self) -> None:
        from app.services.enhancement.fact_guard import (
            FactCheckResult,
            FactGuardSummary,
            GateResult,
        )
        s = FactGuardSummary()
        s.record(FactCheckResult(result=GateResult.PASS))
        s.record(FactCheckResult(
            result=GateResult.REJECT_STRONG,
            failed_dimensions=["study_subjects"],
        ))
        s.record(FactCheckResult(
            result=GateResult.PASS_BY_FAIL_OPEN,
            error_msg="boom",
        ))
        d = s.to_dict()
        assert d["total"] == 3
        assert d["passed"] == 1
        assert d["pass_fail_open"] == 1
        assert d["rejected_strong"] == 1
        assert d["failed_dimensions_count"]["study_subjects"] == 1


class TestRewriterIntegration:
    """deai_rewriter._validate_rewrite 接入 fact_guard 的核心路径。"""

    def test_validate_rewrite_blocks_subject_change(self) -> None:
        """改写后研究对象改变 → _validate_rewrite 必须返回 None（回退）"""
        import os

        # 强制 fact_guard 启用且 hard_block=True
        os.environ["ENABLE_FACT_GUARD"] = "1"
        os.environ["FACT_GUARD_HARD_BLOCK"] = "1"

        # 重载 settings 与 deai_rewriter 以应用新环境变量
        from app.core import config as cfg_mod
        from importlib import reload
        reload(cfg_mod)
        from app.services.enhancement import deai_rewriter
        reload(deai_rewriter)

        orig = "小鼠实验显示该药物降低肿瘤 40% [1]。" * 6  # 拉长以越过 50 字阈值
        bad_rewrite = "临床患者肿瘤减少 40% [1]。" * 6

        result = deai_rewriter._validate_rewrite(
            orig, bad_rewrite, label="test",
        )
        assert result is None, "改写动了研究对象，必须回退"

    def test_validate_rewrite_passes_legal_change(self) -> None:
        """合法的句式重组 → _validate_rewrite 应该通过"""
        import os
        os.environ["ENABLE_FACT_GUARD"] = "1"
        os.environ["FACT_GUARD_HARD_BLOCK"] = "1"

        from app.core import config as cfg_mod
        from importlib import reload
        reload(cfg_mod)
        from app.services.enhancement import deai_rewriter
        reload(deai_rewriter)

        orig = "约 15% 的患者出现不良反应 [1]。" * 6
        good_rewrite = "15% 左右的患者会有不良反应 [1]。" * 6

        result = deai_rewriter._validate_rewrite(
            orig, good_rewrite, label="test",
        )
        assert result is not None, "合法改写不应被回退"
