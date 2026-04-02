"""
输出质量评估
QUALITY_CHECKLIST：按形式族的质量关卡矩阵
AUTO_QUALITY_RULES：正则检测规则，用于自动化质量检查
v2.3：接入 FORMAT_SPECIFIC_CHECKS 供质量自评/人工评审使用
v2.0：接入 auto_quality_rules（含开场套话/感谢阅读/图像描述中文）、acceptance_checker
"""
import json
import re
from typing import Any

# 形式族映射：content_format -> 适用的 checklist 键
FORMAT_TO_CHECKLIST_KEY = {
    "article": "article_agents",
    "story": "article_agents",
    "debunk": "article_agents",
    "qa_article": "article_agents",
    "research_read": "article_agents",
    "oral_script": "script_agents",
    "drama_script": "script_agents",
    "audio_script": "script_agents",
    "comic_strip": "comic_agents",
    "storyboard": "comic_agents",
    "card_series": "comic_agents",
    "picture_book": "comic_agents",
    "patient_handbook": "handbook_agents",
    "poster": "article_agents",
    "long_image": "article_agents",
    "quiz_article": "article_agents",
    "h5_outline": "article_agents",
}

# 图示/脚本类形式（需 JSON / scene_desc 检测）
VISUAL_FORMATS = {"comic_strip", "storyboard", "card_series", "picture_book"}
SCRIPT_FORMATS = {"oral_script", "drama_script", "audio_script"}

QUALITY_CHECKLIST = {
    "article_agents": {
        "医学准确性": "无错误医学事实 / 无具体剂量 / 无编造数据",
        "受众适配性": "词汇复杂度 / 句长 / 类比选择符合受众标准",
        "格式完整性": "章节结构完整 / 字数在范围内",
        "防编造合规": "通过 VerificationPipeline 检查",
        "可读性": "jieba 术语密度 ≤ 受众上限 / 句长达标",
    },
    "script_agents": {
        "口语化程度": "无书面连接词 / 句子≤15字（口播）",
        "格式合规": "时间戳存在 / 角色标注正确",
        "节奏合理": "内容量与时长匹配（按字数/分钟换算）",
        "医学准确性": "同叙事类要求",
    },
    "comic_agents": {
        "JSON 合规": "输出为合法 JSON / 字段完整",
        "画面可生成性": "scene_desc 为英文 / 描述具体 / 30-50词",
        "对白精炼度": "每格对白≤30字",
        "格间连贯性": "相邻格有逻辑衔接（由 planner 保证）",
    },
    "handbook_agents": {
        "医嘱合规性": "无具体剂量 / 遵医嘱提示存在",
        "警示框准确": "紧急症状描述准确 / 就医建议明确",
        "可操作性": "日常建议具体可执行",
        "PDF 格式兼容": "格式标注（【注意】等）一致",
    },
}

# 保留兼容：AUTO_QUALITY_RULES 已迁移至 prompts/auto_quality_rules.py（含开场套话/感谢阅读/图像描述字段中文）
# 此处保留引用供外部导入，实际执行使用 run_auto_quality_checks
AUTO_QUALITY_RULES = [
    ("剂量表述", r"\d+\s*(mg|ml|毫克|毫升|片|粒|滴|g|克)/?", "error", "移除具体剂量，改为「遵医嘱」", None),
    ("绝对化表述", r"一定会|必然|绝对|百分之百|完全治愈|永久有效|肯定能|绝对不会", "error", "替换为概率性表述", None),
    ("编造来源", r"据[^，。]{2,10}研究|根据[^，。]{2,10}指南|统计数据表明", "warning", "检查是否有 RAG 来源支撑", "article"),
    ("超长句子", r"[\u4e00-\u9fff]{40,}[，,]", "warning", "考虑拆分为短句", "article"),
    ("英文缩写未解释", r"(?<![（(\[【])\b[A-Z]{2,5}\b(?![）)\]】])", "warning", "添加中文解释", "article"),
    ("感叹号密集", r"！.{0,20}！.{0,20}！", "warning", "减少感叹号，避免标题党风格", "article"),
    ("scene_desc 中文", r'"scene_desc"\s*:\s*"[^"]*[\u4e00-\u9fff]', "error", "scene_desc 必须为英文", "visual"),
    ("画面描述太短", r'"scene_desc"\s*:\s*"[^"]{1,25}"', "warning", "scene_desc 建议 30-50 英文词", "visual"),
    ("开场套话", r"^(随着医学的发展|在当今社会|众所周知|大家都知道)", "warning", "更换开场，不用套话", "article"),
    ("感谢阅读", r"感谢阅读|谢谢观看|感谢您的关注", "warning", "删除，无信息量", "article"),
    ("illustration_desc中文", r'"illustration_desc"\s*:\s*"[^\x00-\x7F]', "error", "illustration_desc必须为英文", "visual"),
]

# JSON 格式检测（图示类）：尝试解析
JSON_FORMATS = {"comic_strip", "storyboard", "card_series", "picture_book"}


def _run_regex_rules(content: str, content_format: str) -> list[dict]:
    """执行正则规则，返回 issues"""
    issues = []
    is_article = content_format in ("article", "story", "debunk", "qa_article", "research_read", "poster", "long_image", "quiz_article", "h5_outline")
    is_visual = content_format in VISUAL_FORMATS

    for rule_name, pattern, severity, suggestion, scope in AUTO_QUALITY_RULES:
        if scope == "article" and not is_article:
            continue
        if scope == "visual" and not is_visual:
            continue
        try:
            for m in re.finditer(pattern, content):
                issues.append({
                    "rule": rule_name,
                    "severity": severity,
                    "suggestion": suggestion,
                    "match_preview": content[max(0, m.start() - 5) : m.end() + 15][:60],
                })
                if len(issues) >= 20:  # 限制单规则命中数
                    break
        except re.error:
            pass
        if len(issues) >= 30:
            break
    return issues


def _check_json_compliance(content: str, content_format: str) -> list[dict]:
    """图示类：检查是否为合法 JSON"""
    if content_format not in JSON_FORMATS:
        return []
    issues = []
    # 尝试提取 JSON 块
    stripped = content.strip()
    if stripped.startswith("{") or stripped.startswith("["):
        try:
            json.loads(stripped)
        except json.JSONDecodeError as e:
            issues.append({
                "rule": "JSON 格式",
                "severity": "error",
                "suggestion": "输出必须为合法 JSON",
                "match_preview": str(e)[:80],
            })
    return issues


def run_auto_quality_checks(
    content: str,
    content_format: str = "article",
    section_type: str = "",
) -> dict[str, Any]:
    """
    执行自动化质量检查（v2.0 整合 auto_quality_rules + 开场/结尾套话 + 图像描述专项）
    返回 {
        "errors": [...],      # severity=error
        "warnings": [...],    # severity=warning
        "has_errors": bool,
        "checklist_key": str,
        "format_specific_checks": str,
    }
    """
    from app.agents.prompts.quality_check import get_format_specific_checks, get_sop_quality_checks
    from app.agents.prompts.auto_quality_rules import (
        run_auto_quality_check,
        check_opening_cliche,
        check_closing_cliche,
        check_image_desc_language,
        VISUAL_FORMATS,
    )

    checklist_key = FORMAT_TO_CHECKLIST_KEY.get(content_format, "article_agents")
    format_checks = get_format_specific_checks(content_format)

    if not content:
        return {
            "errors": [],
            "warnings": [],
            "has_errors": False,
            "checklist_key": checklist_key,
            "format_specific_checks": format_checks,
        }

    is_visual = content_format in VISUAL_FORMATS

    # Step 1: 使用 auto_quality_rules（含 13 条规则）
    auto_issues = run_auto_quality_check(
        content, content_format, check_json_fields=is_visual
    )

    # Step 2: 图示类专项图像描述字段检查
    if is_visual:
        img_issues = check_image_desc_language(content)
        for issue in img_issues:
            auto_issues.append({
                "rule": issue["rule"],
                "severity": issue["severity"],
                "suggestion": issue["suggestion"] + f"（位置：{issue.get('field', '')}）",
            })

    # Step 3: 特定章节的开场/结尾套话检查
    if section_type == "intro":
        cliche = check_opening_cliche(content)
        if cliche:
            auto_issues.append({
                "rule": cliche["rule"],
                "severity": cliche["severity"],
                "suggestion": cliche["suggestion"],
            })
    if section_type in ("summary", "lesson", "cta"):
        closing = check_closing_cliche(content)
        if closing:
            auto_issues.append({
                "rule": closing["rule"],
                "severity": closing["severity"],
                "suggestion": closing["suggestion"],
            })

    errors = [i for i in auto_issues if i.get("severity") == "error"]
    warnings = [i for i in auto_issues if i.get("severity") == "warning"]

    sop_checks = get_sop_quality_checks()

    return {
        "errors": errors,
        "warnings": warnings,
        "has_errors": len(errors) > 0,
        "checklist_key": checklist_key,
        "format_specific_checks": format_checks,
        "sop_quality_checks": sop_checks,
    }
