"""
AUTO_QUALITY_RULES 完整版
在原有 10 条规则基础上补全三条缺失规则：
  #11 开场套话
  #12 感谢阅读
  #13 illustration_desc/scene_desc 中文检测

v1.0 原有 10 条 + v2.0 新增 3 条 = 共 13 条
"""

import json
import re

# 图示类形式（需 JSON / 图像描述字段检测）
VISUAL_FORMATS = {
    "comic_strip",
    "storyboard",
    "card_series",
    "picture_book",
    "poster",
    "long_image",
    "h5_outline",
}

AUTO_QUALITY_RULES = [
    # ── 原有 10 条（v1.0）──────────────────────────────────
    (
        "剂量表述",
        re.compile(
            r"\d+\s*(mg|ml|毫克|毫升|片|粒|滴|μg|mcg|IU|单位)(?:/(?:次|天|日|kg))?",
            re.IGNORECASE,
        ),
        "error",
        "移除具体剂量，改为'遵医嘱'或'在医生指导下使用'",
    ),
    (
        "绝对化表述",
        re.compile(r"一定会|必然导致|百分之百|完全治愈|永久有效|从不发生|只要.{0,20}就能治愈"),
        "error",
        "替换为概率性表述：可能/有助于/研究显示/在多数情况下",
    ),
    (
        "编造来源",
        re.compile(r"据.*?研究[，,。]|根据.*?指南[，,。]|.*?统计(?:数据)?(?:显示|表明)[，,。]"),
        "warning",
        "确认是否有 RAG 来源支撑；无来源时使用 [DATA:] 占位",
    ),
    (
        "超长句子-大众",
        re.compile(r"[\u4e00-\u9fff]{26,}(?=[，。！？\n])"),
        "warning",
        "目标受众为大众时，句子超25字需拆分（其他受众根据 AUDIENCE_PROFILES 调整）",
    ),
    (
        "英文缩写未解释",
        re.compile(r"(?<![（(【])\b[A-Z]{2,6}\b(?![）)】：])"),
        "warning",
        "英文缩写首次出现时在括号内附中文解释，如 HbA1c（糖化血红蛋白）",
    ),
    (
        "感叹号密集",
        re.compile(r"！.{0,25}！.{0,25}！"),
        "warning",
        "减少感叹号密集使用，避免标题党风格",
    ),
    (
        "JSON格式检查",
        re.compile(r"^\s*[\[{]"),
        "check",
        "验证是否为合法 JSON（仅在输出类型为 JSON 时执行）",
    ),
    (
        "scene_desc中文",
        re.compile(r'"scene_desc"\s*:\s*"[^"]*[\u4e00-\u9fff][^"]*"'),
        "error",
        "scene_desc 字段必须是英文，请翻译为英文后重新生成",
    ),
    (
        "画面描述太短",
        re.compile(r'"scene_desc"\s*:\s*"[^"]{1,30}"'),
        "warning",
        "scene_desc 建议30-50英文词，当前过短，建议补充主体+动作+背景+风格信息",
    ),
    (
        "illustration_desc中文",
        re.compile(r'"illustration_desc"\s*:\s*"[^"]*[\u4e00-\u9fff][^"]*"'),
        "error",
        "illustration_desc 字段必须是英文",
    ),
    # ── 新增 3 条（v2.0 补全）────────────────────────────────
    (
        "开场套话",
        re.compile(
            r"^.{0,50}(随着医学的发展|在当今社会|众所周知|大家都知道"
            r"|随着科技的进步|在现代医学|随着人们生活水平|随着时代的发展)",
            re.MULTILINE,
        ),
        "warning",
        "开场使用了套话，建议换为有信息量的开场（数字、反问、场景、价值承诺）",
    ),
    (
        "感谢阅读",
        re.compile(
            r"(感谢阅读|谢谢观看|感谢您的关注|感谢您的耐心阅读"
            r"|感谢大家的观看|欢迎关注我们的公众号|感谢收看)"
        ),
        "warning",
        "删除无意义的结尾套语，这类表达不增加内容价值",
    ),
    (
        "图像描述字段中文",
        re.compile(
            r'"(?:illustration_desc|scene_desc|image_prompt|main_visual_desc'
            r'|footer_image_prompt|visual_mood|background_desc)"\s*:\s*"[^"]*[\u4e00-\u9fff][^"]*"'
        ),
        "error",
        "图像描述字段（illustration_desc/scene_desc/image_prompt等）必须使用英文，"
        "含中文时图像生成将失败或质量极差",
    ),
]


def run_auto_quality_check(
    content: str,
    content_format: str = "article",
    check_json_fields: bool = False,
    scope_article: tuple[str, ...] | None = None,
    scope_visual: tuple[str, ...] | None = None,
) -> list[dict]:
    """
    对内容执行全部自动质量规则检查
    返回触发的规则列表（未触发的规则不返回）

    Args:
        content:          待检查内容（纯文本或 JSON 字符串）
        content_format:   科普形式（用于决定是否执行某些规则）
        check_json_fields:是否需要解析 JSON 后检查字段（图示类输出时设为 True）
        scope_article:    视为文章类的形式集合（默认包含 article, story, debunk 等）
        scope_visual:     视为图示类的形式集合（默认包含 comic_strip, card_series 等）

    Returns:
        [{"rule": str, "severity": str, "suggestion": str, "match_preview": str?}, ...]
    """
    triggered = []
    if scope_article is None:
        scope_article = (
            "article",
            "story",
            "debunk",
            "qa_article",
            "research_read",
            "poster",
            "long_image",
            "quiz_article",
            "h5_outline",
        )
    if scope_visual is None:
        scope_visual = tuple(VISUAL_FORMATS)

    is_visual = content_format in scope_visual
    is_article = content_format in scope_article

    flat_content = content
    if is_visual and check_json_fields:
        try:
            parsed = json.loads(content)
            flat_content = json.dumps(parsed, ensure_ascii=False)
        except (json.JSONDecodeError, ValueError, TypeError):
            pass

    for rule_name, pattern, severity, suggestion in AUTO_QUALITY_RULES:
        # JSON格式检查 只在视觉类形式执行
        if rule_name == "JSON格式检查":
            if is_visual:
                try:
                    json.loads(content)
                except (json.JSONDecodeError, ValueError, TypeError):
                    triggered.append({
                        "rule": rule_name,
                        "severity": severity,
                        "suggestion": suggestion,
                    })
            continue

        # 编造来源、超长句子、英文缩写、感叹号 仅文章类
        if rule_name in ("编造来源", "超长句子-大众", "英文缩写未解释", "感叹号密集"):
            if not is_article:
                continue

        # scene_desc/画面描述/illustration_desc/图像描述字段中文 仅图示类
        if rule_name in (
            "scene_desc中文",
            "画面描述太短",
            "illustration_desc中文",
            "图像描述字段中文",
        ):
            if not is_visual:
                continue

        m = pattern.search(flat_content)
        if m:
            preview = flat_content[max(0, m.start() - 5) : m.end() + 15][:60]
            triggered.append({
                "rule": rule_name,
                "severity": severity,
                "suggestion": suggestion,
                "match_preview": preview,
            })

    return triggered


def check_opening_cliche(content: str) -> dict | None:
    """
    单独检查开场套话（适合在 IntroAgent 生成后立即调用）
    仅检查前 100 字，比全文扫描更精准
    """
    opening = content[:100]
    cliches = [
        "随着医学的发展",
        "在当今社会",
        "众所周知",
        "大家都知道",
        "随着科技的进步",
        "在现代医学",
        "随着人们生活水平",
        "随着时代的发展",
        "随着医疗水平的提高",
    ]
    for c in cliches:
        if c in opening:
            return {
                "rule": "开场套话",
                "severity": "warning",
                "found": c,
                "suggestion": f"'{c}' 是常见的无信息量开场，建议换为数字/反问/场景/价值承诺",
            }
    return None


def check_closing_cliche(content: str) -> dict | None:
    """
    单独检查感谢阅读等结尾套语（适合在 SummaryAgent 生成后立即调用）
    仅检查后 100 字
    """
    closing = content[-100:] if len(content) >= 100 else content
    cliches = [
        "感谢阅读",
        "谢谢观看",
        "感谢您的关注",
        "感谢您的耐心阅读",
        "感谢大家的观看",
        "欢迎关注我们的公众号",
        "感谢收看",
    ]
    for c in cliches:
        if c in closing:
            return {
                "rule": "感谢阅读",
                "severity": "warning",
                "found": c,
                "suggestion": "结尾套语无内容价值，直接删除即可",
            }
    return None


def check_image_desc_language(json_content: str) -> list[dict]:
    """
    专项检查 JSON 输出中所有图像描述字段是否为中文
    比正则全文扫描更精准，可定位到具体字段路径

    适合在 ComicPanelWriterAgent / PictureBookPageAgent 等图示类 Agent
    生成内容后立即调用
    """
    IMAGE_DESC_FIELDS = {
        "illustration_desc",
        "scene_desc",
        "image_prompt",
        "main_visual_desc",
        "footer_image_prompt",
        "visual_mood",
        "background_desc",
    }

    issues = []

    def scan(obj, path=""):
        if isinstance(obj, dict):
            for k, v in obj.items():
                current_path = f"{path}.{k}" if path else k
                if k in IMAGE_DESC_FIELDS and isinstance(v, str):
                    has_chinese = bool(re.search(r"[\u4e00-\u9fff]", v))
                    is_too_short = len(v.split()) < 8
                    if has_chinese:
                        issues.append({
                            "field": current_path,
                            "rule": "图像描述字段中文",
                            "severity": "error",
                            "value": v[:50] + ("..." if len(v) > 50 else ""),
                            "suggestion": "必须改为英文，含中文时图像生成将失败",
                        })
                    elif is_too_short:
                        issues.append({
                            "field": current_path,
                            "rule": "图像描述太短",
                            "severity": "warning",
                            "value": v,
                            "suggestion": f"仅 {len(v.split())} 词，建议20词以上，补充主体+动作+背景+风格",
                        })
                else:
                    scan(v, current_path)
        elif isinstance(obj, list):
            for i, item in enumerate(obj):
                scan(item, f"{path}[{i}]")

    try:
        parsed = json.loads(json_content)
        scan(parsed)
    except (json.JSONDecodeError, ValueError, TypeError):
        issues.append({
            "field": "root",
            "rule": "JSON格式",
            "severity": "error",
            "value": "",
            "suggestion": "输出不是合法 JSON，无法执行图像描述检查",
        })

    return issues
