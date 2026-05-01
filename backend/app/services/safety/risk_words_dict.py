"""
合规风险词典（P0-3 / 决策附录 A.9 / A.10）

ActionLevel 五级（决策 K1）：
  BLOCK         - P1 启用，P0 注册但不实际触发
  CONFIRM_HARD  - 红色 + 必须勾选才能发（自行注射等关键风险）
  CONFIRM_SOFT  - 橙色 + 必须勾选才能发（绝对化用语 / 不当承诺）
  WARN          - 黄色 + UI 默认折叠（信息提醒，可关闭）
  LOG_ONLY      - 仅后端日志，不展示给用户（处方药等高误报规则）

K2 决策：所有"建议/推荐 + 行动"类规则使用否定环视 + 警示语境二次过滤；
处方药模糊匹配规则因误报率高，P0 设为 LOG_ONLY 收数据。
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum


# ────────────────────────────────────────────
# 枚举
# ────────────────────────────────────────────


class ActionLevel(Enum):
    """决策 K1：P0 全 CONFIRM，BLOCK 保留接口待 P1 数据驱动升级。"""
    BLOCK = "block"
    CONFIRM_HARD = "confirm_hard"
    CONFIRM_SOFT = "confirm_soft"
    WARN = "warn"
    LOG_ONLY = "log_only"


# ────────────────────────────────────────────
# 否定环视 / 警示语境（决策 K2）
# ────────────────────────────────────────────

# 紧邻前缀否定词（用于 lookbehind）
NEGATION_PREFIXES: tuple[str, ...] = (
    "不", "不要", "切勿", "禁止", "避免", "杜绝", "严禁",
    "不应", "不得", "不可", "不能", "无需", "不必",
    "切忌", "勿", "禁",
)

# 句中扫描的警示语境词（命中后整段视为合规警示，过滤掉风险匹配）
WARNING_CONTEXTS: tuple[str, ...] = (
    "风险", "危险", "严重后果", "可能导致", "副作用", "并发症",
    "禁忌", "警告", "注意", "切记", "谨慎", "小心", "潜在风险",
)


# ────────────────────────────────────────────
# 数据结构
# ────────────────────────────────────────────


@dataclass(frozen=True)
class RiskRule:
    """单条合规风险规则。

    pattern：核心目标词正则（不要在 pattern 里写 lookbehind，Python 标准
    库的 re 模块只支持定长 lookbehind）。

    negation_lookback：决策 K2 的否定环视——匹配命中后，由 risk_scanner
    检查命中位置前 N 字内是否出现 NEGATION_PREFIXES 任一前缀；如有，匹
    配视为合规警示而过滤。0 表示该规则不做否定环视。
    """
    name: str
    pattern: re.Pattern[str]
    action: ActionLevel
    category: str
    legal_ref: str
    user_message: str
    suggestion: str = ""
    negation_lookback: int = 0


# ────────────────────────────────────────────
# 词典：决策 K1 → 全 CONFIRM；K2 → 否定环视；处方药 → LOG_ONLY
# ────────────────────────────────────────────


# ── CONFIRM_HARD：必须勾选 + 红色 ─────────────────────────────
RULES_CONFIRM_HARD: list[RiskRule] = [
    RiskRule(
        name="self_administration",
        # 决策 K1：自行注射等关键风险用 CONFIRM_HARD（红色），不直接 BLOCK
        # 决策 K2：scanner 检查命中前 30 字内不能出现 NEGATION_PREFIXES，
        # 排除 "避免自行注射" 类警示
        pattern=re.compile(r"自行\s*(?:注射|输液|插管|插胃管|换药|吸氧|配药)"),
        action=ActionLevel.CONFIRM_HARD,
        category="self_administration",
        legal_ref="《互联网诊疗管理办法》第七条",
        user_message="涉及自行实施医疗操作的描述存在风险",
        suggestion="改为'在医生指导下进行'或'由医务人员操作'",
        negation_lookback=30,
    ),
]


# ── CONFIRM_SOFT：必须勾选 + 橙色 ─────────────────────────────
RULES_CONFIRM_SOFT: list[RiskRule] = [
    RiskRule(
        name="absolute_cure_rate",
        pattern=re.compile(r"治愈率\s*[19]?00\s*%"),
        action=ActionLevel.CONFIRM_SOFT,
        category="absolute_claims",
        legal_ref="《广告法》第十六条 / 第九条",
        user_message="使用了'治愈率 100%'类绝对化表述",
        suggestion="改为'治愈率约 X%'或'有效率高达 X%'",
    ),
    RiskRule(
        name="absolute_safety_efficacy",
        pattern=re.compile(r"100%\s*(?:治愈|有效|安全|无副作用)"),
        action=ActionLevel.CONFIRM_SOFT,
        category="absolute_claims",
        legal_ref="《广告法》第九条",
        user_message="使用了 100% 类绝对化表述",
        suggestion="改为'临床证据显示有效率较高'类有依据表达",
    ),
    RiskRule(
        name="cure_promise_words",
        pattern=re.compile(
            r"根治|彻底治愈|永不复发|立竿见影|药到病除|包治百病|包治"
        ),
        action=ActionLevel.CONFIRM_SOFT,
        category="absolute_claims",
        legal_ref="《广告法》第十六条",
        user_message="使用了根治 / 永不复发等绝对化用语",
        suggestion="改为'缓解症状' / '降低复发概率'类有边界表述",
    ),
    RiskRule(
        name="absolute_certainty",
        pattern=re.compile(
            r"绝对\s*(?:安全|有效|无副作用|不会复发|无风险)"
        ),
        action=ActionLevel.CONFIRM_SOFT,
        category="absolute_claims",
        legal_ref="《广告法》第九条",
        user_message="使用了'绝对安全 / 有效'类不当承诺",
        suggestion="改为'临床证据显示安全性良好'类相对表达",
    ),
    RiskRule(
        name="medical_promise_keywords",
        pattern=re.compile(r"祖传秘方|祖传药方|神药|神方|特效药"),
        action=ActionLevel.CONFIRM_SOFT,
        category="medical_promise",
        legal_ref="《广告法》第十六条 / 第十七条",
        user_message="使用了不当医疗承诺类用语",
        suggestion="改用客观循证表述，避免'神效 / 祖传'等夸张词",
    ),
    RiskRule(
        name="best_or_only_choice",
        pattern=re.compile(r"(?:最佳|首选|唯一)\s*(?:治疗|方案|药物|方法)"),
        action=ActionLevel.CONFIRM_SOFT,
        category="absolute_claims",
        legal_ref="《广告法》第十六条",
        user_message="使用了'最佳 / 首选 / 唯一'类绝对化表述",
        suggestion="改为'循证推荐' / '一线方案之一'等相对表达",
    ),
]


# ── WARN：UI 默认折叠 + 黄色 ─────────────────────────────────
RULES_WARN: list[RiskRule] = [
    RiskRule(
        name="rare_disease_mention",
        pattern=re.compile(r"罕见病|罕见疾病"),
        action=ActionLevel.WARN,
        category="rare_disease",
        legal_ref="—",
        user_message="涉及罕见病话题，建议确认信息来源权威",
    ),
    RiskRule(
        name="psychiatric_topic",
        pattern=re.compile(r"精神(?:分裂|障碍|疾病)|抑郁(?:症|障碍)|双相|焦虑症"),
        action=ActionLevel.WARN,
        category="psychiatric",
        legal_ref="—",
        user_message="涉及精神类疾病，建议增加'就医建议'与'危机干预热线'信息",
    ),
    RiskRule(
        name="new_drug_mention",
        pattern=re.compile(r"新药|新型(?:药物|疗法|疫苗)|创新药"),
        action=ActionLevel.WARN,
        category="new_drug",
        legal_ref="—",
        user_message="涉及新药 / 新疗法，建议核对临床批准状态",
    ),
    RiskRule(
        name="pediatric_dosage",
        pattern=re.compile(r"儿童\s*(?:剂量|用量|用法)"),
        action=ActionLevel.WARN,
        category="pediatric",
        legal_ref="《儿童医疗保健法》",
        user_message="涉及儿童用药，建议补充'具体剂量请遵医嘱'",
    ),
    RiskRule(
        name="pregnancy_medication",
        pattern=re.compile(r"孕(?:期|妇).{0,8}(?:用药|服用)"),
        action=ActionLevel.WARN,
        category="pregnancy",
        legal_ref="—",
        user_message="涉及孕期用药，建议提示'妊娠期需医生评估'",
    ),
]


# ── LOG_ONLY：决策 K2，处方药模糊规则误报率高，P0 仅记日志 ────
RULES_LOG_ONLY: list[RiskRule] = [
    RiskRule(
        name="prescription_drug_recommendation_hint",
        # 决策 K2：处方药模糊匹配——"建议/推荐/可以 + 服用/使用/口服/注射"
        # scanner 检查命中前 8 字内不能出现否定词（"不要建议 / 避免推荐"）
        # P0 仅 LOG_ONLY，等数据决定 P1 是否升级 WARN
        pattern=re.compile(
            r"(?:建议|推荐|应该|可以|不妨)\s*(?:服用|使用|口服|注射|肌注|静脉滴注)"
        ),
        action=ActionLevel.LOG_ONLY,
        category="prescription_drug",
        legal_ref="《处方药与非处方药分类管理办法》",
        user_message="可能涉及处方药使用建议（仅日志，不展示）",
        negation_lookback=8,
    ),
    RiskRule(
        name="specific_dosage_recommendation_hint",
        # K2 决策：复合单位 mg/kg 用否定环视排除（不命中 5 mg/kg）
        # 这条只 LOG_ONLY，避免误判 "5 mg/kg/天" 是绝对剂量
        pattern=re.compile(
            r"剂量\s*(?:为|是|应该是|建议是|约为)?\s*"
            r"\d+\s*(?:mg|g|μg|ug|ml|片|粒)"
            r"(?!/)"  # K2: 排除 mg/kg / mg/d 复合单位
        ),
        action=ActionLevel.LOG_ONLY,
        category="specific_dosage",
        legal_ref="—",
        user_message="可能涉及具体剂量建议（仅日志，不展示）",
    ),
]


# 全部启用规则（顺序：高优先级在前）
ALL_RULES: list[RiskRule] = (
    RULES_CONFIRM_HARD
    + RULES_CONFIRM_SOFT
    + RULES_WARN
    + RULES_LOG_ONLY
)


__all__ = [
    "ActionLevel",
    "RiskRule",
    "NEGATION_PREFIXES",
    "WARNING_CONTEXTS",
    "RULES_CONFIRM_HARD",
    "RULES_CONFIRM_SOFT",
    "RULES_WARN",
    "RULES_LOG_ONLY",
    "ALL_RULES",
]
