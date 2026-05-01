"""
P0-2 / R3 共享禁令模块单元测试

验证：
1. 共享常量加载与字符串结构
2. 生成层 system prompt 强制注入（含 layer0/system.txt override 路径）
3. 改写层 system prompt 强制注入（含 deai/system_override.txt 路径）
4. 第 2 轮 user prompt 头部提示存在
5. 不重复注入

运行方式：
  pytest backend/tests/test_fact_preservation_rules.py -v
"""
from __future__ import annotations

import pytest


# ────────────────────────────────────────────
# 1. 共享模块本身
# ────────────────────────────────────────────


def test_constants_exported() -> None:
    from app.agents.prompts import fact_preservation_rules as m

    for name in (
        "FACT_PRESERVATION_RULES",
        "REWRITE_FACT_RULES",
        "REWRITE_VIOLATION_EXAMPLES",
        "REWRITE_LEGAL_EXAMPLES",
        "REWRITE_FACT_BLOCK",
    ):
        assert hasattr(m, name), f"缺少导出常量 {name}"
        value = getattr(m, name)
        assert isinstance(value, str)
        assert value.strip(), f"{name} 为空"


def test_generation_rules_have_seven_items() -> None:
    """生成层 7 条规则一一齐全（编号 1-7）"""
    from app.agents.prompts.fact_preservation_rules import FACT_PRESERVATION_RULES

    for i in range(1, 8):
        assert f"\n{i}." in FACT_PRESERVATION_RULES, f"缺少第 {i} 条规则"


def test_rewrite_rules_have_seven_items() -> None:
    """改写层 7 条命令式禁令一一齐全"""
    from app.agents.prompts.fact_preservation_rules import REWRITE_FACT_RULES

    for i in range(1, 8):
        assert f"\n{i}." in REWRITE_FACT_RULES, f"缺少第 {i} 条禁令"


def test_rewrite_block_contains_all_three_sections() -> None:
    """REWRITE_FACT_BLOCK = 禁令 + 合法示例 + 违规示例"""
    from app.agents.prompts.fact_preservation_rules import (
        REWRITE_FACT_BLOCK,
        REWRITE_FACT_RULES,
        REWRITE_LEGAL_EXAMPLES,
        REWRITE_VIOLATION_EXAMPLES,
    )

    assert REWRITE_FACT_RULES in REWRITE_FACT_BLOCK
    assert REWRITE_LEGAL_EXAMPLES in REWRITE_FACT_BLOCK
    assert REWRITE_VIOLATION_EXAMPLES in REWRITE_FACT_BLOCK


def test_rewrite_block_includes_drug_violation_example() -> None:
    """违规示例覆盖"补充药物名"——P0-2 / R3 用户讨论结论"""
    from app.agents.prompts.fact_preservation_rules import REWRITE_VIOLATION_EXAMPLES

    assert "药物名" in REWRITE_VIOLATION_EXAMPLES
    assert "美托洛尔" in REWRITE_VIOLATION_EXAMPLES, (
        "应包含具体药名违规反例（用户决策附录 A.8 / R3）"
    )


# ────────────────────────────────────────────
# 2. 生成层注入
# ────────────────────────────────────────────


def test_generation_default_system_includes_rules() -> None:
    from app.agents.prompts.fact_preservation_rules import FACT_PRESERVATION_RULES
    from app.agents.prompts.system import _DEFAULT_SYSTEM, _DEFAULT_SYSTEM_READER_FACING

    assert FACT_PRESERVATION_RULES in _DEFAULT_SYSTEM
    assert FACT_PRESERVATION_RULES in _DEFAULT_SYSTEM_READER_FACING


def test_get_system_prompt_reader_facing_injects_rules() -> None:
    from app.agents.prompts.fact_preservation_rules import FACT_PRESERVATION_RULES
    from app.agents.prompts.system import get_system_prompt

    prompt = get_system_prompt(
        content_format="contest_article",
        platform="wechat",
        target_audience="public",
    )
    assert FACT_PRESERVATION_RULES in prompt


def test_get_system_prompt_internal_injects_rules() -> None:
    from app.agents.prompts.fact_preservation_rules import FACT_PRESERVATION_RULES
    from app.agents.prompts.system import get_system_prompt

    prompt = get_system_prompt(
        content_format="some_internal_format",
        platform="wechat",
    )
    assert FACT_PRESERVATION_RULES in prompt


def test_layer0_override_cannot_bypass_fact_rules(monkeypatch: pytest.MonkeyPatch) -> None:
    """即便 layer0/system.txt override 文件不含禁令，最终 prompt 也必须包含。

    模拟 _ensure_fact_rules 的健壮性：传入一个无关 override，确认禁令被强制追加。
    """
    from app.agents.prompts.fact_preservation_rules import FACT_PRESERVATION_RULES
    from app.agents.prompts.system import _ensure_fact_rules

    fake_override = "你是 AI 助手。请按用户要求工作。"
    enriched = _ensure_fact_rules(fake_override)
    assert FACT_PRESERVATION_RULES in enriched
    assert fake_override in enriched, "原 override 内容应保留"


def test_ensure_fact_rules_idempotent() -> None:
    """重复调用不应叠加（避免 prompt 膨胀）"""
    from app.agents.prompts.fact_preservation_rules import FACT_PRESERVATION_RULES
    from app.agents.prompts.system import _ensure_fact_rules

    base = "已经注入：" + FACT_PRESERVATION_RULES
    once = _ensure_fact_rules(base)
    twice = _ensure_fact_rules(once)
    assert once == twice
    assert once.count("【信息保真要求】") == 1


# ────────────────────────────────────────────
# 3. 改写层注入
# ────────────────────────────────────────────


def test_rewrite_system_prompt_injects_block() -> None:
    from app.agents.prompts.fact_preservation_rules import REWRITE_FACT_BLOCK
    from app.services.enhancement.deai_rewriter import _resolve_deai_system_prompt

    sp = _resolve_deai_system_prompt("wechat", "public")
    assert REWRITE_FACT_BLOCK in sp


def test_rewrite_override_cannot_bypass_block(monkeypatch: pytest.MonkeyPatch) -> None:
    """即便 prompt-example/prompts/deai/system_override.txt 提供了完整覆盖，
    REWRITE_FACT_BLOCK 仍必须存在（业务规则强制生效）。
    """
    import app.services.enhancement.deai_rewriter as deai

    monkeypatch.setattr(
        "app.agents.prompts.loader.load_deai_system_override",
        lambda: "我是改写器，按要求改写文本即可。",
    )
    sp = deai._resolve_deai_system_prompt("wechat", "public")
    from app.agents.prompts.fact_preservation_rules import REWRITE_FACT_BLOCK

    assert REWRITE_FACT_BLOCK in sp
    assert "我是改写器" in sp, "原 override 内容应保留"


# ────────────────────────────────────────────
# 4. 第 2 轮提示
# ────────────────────────────────────────────


def test_r2_head_hint_present() -> None:
    from app.services.enhancement.deai_rewriter import _R2_HEAD_HINT

    assert "第 2 轮微调" in _R2_HEAD_HINT
    assert "句式微调" in _R2_HEAD_HINT
    assert "不做大幅重写" in _R2_HEAD_HINT
