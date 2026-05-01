"""
P0-3 风险词扫描单元测试

覆盖决策附录 A.9 / A.10 的全部行为：

K1：
  - 全 CONFIRM（无 BLOCK 实际触发）
  - CONFIRM_HARD / CONFIRM_SOFT 视觉分级
  - 自行注射放 CONFIRM_HARD

K2：
  - 否定环视（避免 / 不要 等前缀过滤）
  - 警示语境二次过滤（"会带来风险" 等）
  - 处方药模糊规则放 LOG_ONLY，不展示给用户
  - 复合单位 mg/kg 不被 specific_dosage 误命中

K3：
  - WARN 在 ALL_RULES 中默认全开（前端折叠 / 持久化属于 UI 关注点）

运行：
  pytest backend/tests/test_risk_scanner.py -v
"""
from __future__ import annotations

import pytest


# ────────────────────────────────────────────
# K1: ActionLevel 完整枚举与 CONFIRM 分级
# ────────────────────────────────────────────


class TestActionLevel:
    def test_all_levels_present(self) -> None:
        from app.services.safety.risk_words_dict import ActionLevel
        for name in ("BLOCK", "CONFIRM_HARD", "CONFIRM_SOFT", "WARN", "LOG_ONLY"):
            assert hasattr(ActionLevel, name)

    def test_no_p0_rule_uses_block(self) -> None:
        """决策 K1：P0 阶段不应有任何规则使用 BLOCK"""
        from app.services.safety.risk_words_dict import ALL_RULES, ActionLevel
        for rule in ALL_RULES:
            assert rule.action != ActionLevel.BLOCK, (
                f"P0 阶段不允许 BLOCK，但 {rule.name} 用了 BLOCK"
            )

    def test_self_administration_is_confirm_hard(self) -> None:
        """决策 K1：自行注射放 CONFIRM_HARD"""
        from app.services.safety.risk_words_dict import ALL_RULES, ActionLevel
        rule = next(r for r in ALL_RULES if r.name == "self_administration")
        assert rule.action == ActionLevel.CONFIRM_HARD


# ────────────────────────────────────────────
# K1 + K2 综合：CONFIRM 命中、否定环视、警示语境
# ────────────────────────────────────────────


class TestSelfAdministration:
    def test_positive_match(self) -> None:
        from app.services.safety import scan_risk_words
        r = scan_risk_words("糖尿病患者可以自行注射胰岛素以控制血糖。")
        assert r.matches_by_action.get("confirm_hard")
        assert r.confirm_required

    def test_negation_avoid_K2(self) -> None:
        """K2 否定环视：'避免自行注射' 不命中"""
        from app.services.safety import scan_risk_words
        r = scan_risk_words("避免自行注射胰岛素，应在医生指导下进行。")
        assert not r.matches_by_action.get("confirm_hard")

    def test_negation_dont(self) -> None:
        from app.services.safety import scan_risk_words
        r = scan_risk_words("切勿自行注射，必须由医务人员操作。")
        assert not r.matches_by_action.get("confirm_hard")

    def test_warning_context_filtered_K2(self) -> None:
        """K2 警示语境过滤：'会带来严重风险' 视为合规警示"""
        from app.services.safety import scan_risk_words
        r = scan_risk_words("自行注射会带来严重的健康风险，必须避免。")
        assert not r.matches_by_action.get("confirm_hard")


class TestAbsoluteClaims:
    def test_cure_rate_100(self) -> None:
        from app.services.safety import scan_risk_words
        r = scan_risk_words("该疗法治愈率 100%，临床效果突出。")
        assert any(
            m.rule_name == "absolute_cure_rate"
            for m in r.matches_by_action["confirm_soft"]
        )

    def test_radical_cure_words(self) -> None:
        from app.services.safety import scan_risk_words
        r = scan_risk_words("该药能彻底治愈痤疮，永不复发。")
        assert r.matches_by_action.get("confirm_soft")

    def test_best_first_only(self) -> None:
        from app.services.safety import scan_risk_words
        r = scan_risk_words("这是治疗 X 的最佳方案，也是首选治疗。")
        assert r.matches_by_action.get("confirm_soft")

    def test_legitimate_recommend_not_caught(self) -> None:
        """合法的'建议多饮水'不应该命中任何规则"""
        from app.services.safety import scan_risk_words
        r = scan_risk_words("建议患者多饮水，保持充足睡眠。")
        assert r.total_visible == 0
        assert len(r.matches_log_only) == 0


# ────────────────────────────────────────────
# WARN 默认开启（K3）
# ────────────────────────────────────────────


class TestWarnRules:
    def test_warn_rules_present_K3(self) -> None:
        """决策 K3：WARN 默认全开"""
        from app.services.safety.risk_words_dict import RULES_WARN
        assert len(RULES_WARN) >= 3, "至少包含 罕见病 / 精神类 / 新药 三条"
        rule_names = {r.name for r in RULES_WARN}
        assert "rare_disease_mention" in rule_names
        assert "psychiatric_topic" in rule_names

    def test_rare_disease(self) -> None:
        from app.services.safety import scan_risk_words
        r = scan_risk_words("这是一种罕见病，需要长期管理。")
        assert r.matches_by_action.get("warn")

    def test_warn_does_not_require_confirm(self) -> None:
        """WARN 不应触发 confirm_required"""
        from app.services.safety import scan_risk_words
        r = scan_risk_words("这是一种罕见病，需要长期管理。")
        assert not r.confirm_required


# ────────────────────────────────────────────
# LOG_ONLY（处方药 / specific_dosage）
# ────────────────────────────────────────────


class TestLogOnlyRules:
    def test_prescription_drug_log_only_K2(self) -> None:
        """决策 K2：处方药模糊规则只记日志，不展示给用户"""
        from app.services.safety import scan_risk_words
        r = scan_risk_words("建议服用阿莫西林治疗。")
        assert any(
            m.rule_name == "prescription_drug_recommendation_hint"
            for m in r.matches_log_only
        )
        # 关键：用户可见报告里不应出现
        assert "log_only" not in r.matches_by_action
        assert r.total_visible == 0

    def test_prescription_drug_negation(self) -> None:
        """K2: '不要建议服用' 否定环视生效"""
        from app.services.safety import scan_risk_words
        r = scan_risk_words("不要建议服用阿莫西林。")
        assert not any(
            m.rule_name == "prescription_drug_recommendation_hint"
            for m in r.matches_log_only
        )

    def test_specific_dosage_positive(self) -> None:
        from app.services.safety import scan_risk_words
        r = scan_risk_words("剂量为 50 mg。")
        assert any(
            m.rule_name == "specific_dosage_recommendation_hint"
            for m in r.matches_log_only
        )

    def test_specific_dosage_excludes_compound_unit_K2(self) -> None:
        """K2: 复合单位 mg/kg / mg/d 不被 specific_dosage 命中"""
        from app.services.safety import scan_risk_words
        r = scan_risk_words("小鼠剂量 5 mg/kg/d 是安全的。")
        assert not any(
            m.rule_name == "specific_dosage_recommendation_hint"
            for m in r.matches_log_only
        )


# ────────────────────────────────────────────
# Report 序列化
# ────────────────────────────────────────────


class TestReportSerialization:
    def test_to_dict_structure(self) -> None:
        from app.services.safety import scan_risk_words
        r = scan_risk_words("治愈率 100%。")
        d = r.to_dict()
        assert "matches_by_action" in d
        assert "confirm_required" in d
        assert "block_required" in d
        assert d["block_required"] is False, "P0 不应触发 block_required"
        assert d["confirm_required"] is True

    def test_empty_text_returns_empty_report(self) -> None:
        from app.services.safety import scan_risk_words
        r = scan_risk_words("")
        assert r.total_visible == 0
        assert not r.confirm_required
        assert not r.block_required


# ────────────────────────────────────────────
# 否定环视健壮性
# ────────────────────────────────────────────


class TestNegationLookback:
    def test_lookback_within_30_chars(self) -> None:
        """30 字内的否定词都能阻止命中"""
        from app.services.safety import scan_risk_words
        # 否定词与目标距离 < 30
        r = scan_risk_words("严禁孕妇自行注射任何药物。")
        assert not r.matches_by_action.get("confirm_hard")

    def test_lookback_beyond_distance_still_match(self) -> None:
        """超过 negation_lookback 范围的否定词不再过滤"""
        from app.services.safety import scan_risk_words
        # 否定词在 50+ 字之前，前面是无关内容
        long_prefix = "请勿吸烟。" + "X" * 60 + "糖尿病患者可以自行注射胰岛素。"
        r = scan_risk_words(long_prefix)
        assert r.matches_by_action.get("confirm_hard")
