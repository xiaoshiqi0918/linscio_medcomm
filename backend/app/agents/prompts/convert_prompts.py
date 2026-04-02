"""
多形式内容转换提示词（v2.2）
ContentFormatConvertor 任务提示词 + CONVERSION_QA_PROMPT 转换质量检查
"""
from app.agents.prompts.audiences import AUDIENCE_PROFILES

# 转换策略矩阵（v2.2 扩展）
CONVERSION_STRATEGY = {
    ("article", "oral_script"): "direct",
    ("article", "comic_strip"): "direct",
    ("article", "card_series"): "extract",
    ("article", "patient_handbook"): "adapt",
    ("article", "debunk"): "extract",
    ("article", "poster"): "extract",
    ("article", "long_image"): "adapt",
    ("article", "quiz_article"): "extract",
    ("article", "picture_book"): "direct",
    ("oral_script", "article"): "expand",
    ("oral_script", "audio_script"): "adapt",
    ("comic_strip", "article"): "expand",
    ("debunk", "comic_strip"): "direct",
    ("debunk", "quiz_article"): "adapt",
    ("patient_handbook", "card_series"): "extract",
    ("qa_article", "oral_script"): "adapt",
    ("qa_article", "quiz_article"): "adapt",
}

# children 受众不允许转换的目标形式
CHILDREN_BLOCKED_TARGETS = (
    "oral_script",
    "audio_script",
    "debunk",
    "quiz_article",
    "patient_handbook",
)

FORMAT_NAMES = {
    "article": "图文文章",
    "oral_script": "口播脚本",
    "comic_strip": "条漫脚本",
    "card_series": "知识卡片系列",
    "patient_handbook": "患者教育手册",
    "debunk": "辟谣文",
    "poster": "科普海报",
    "long_image": "竖版长图",
    "audio_script": "播客脚本",
    "qa_article": "问答科普",
    "quiz_article": "自测科普",
    "picture_book": "科普绘本",
}

STRATEGY_GUIDE = {
    "direct": "直接将原文核心信息转换为新形式，不需要保留原文结构",
    "adapt": "保留原文的主要结构和观点，调整语言风格和格式适配新形式",
    "extract": "从原文中提取最重要的信息点，重新精炼组织为新形式",
    "expand": "以原文为基础，补充细节和背景，扩展为更完整的新形式",
}

TARGET_FORMAT_REQUIREMENTS = {
    "oral_script": (
        "· 每句≤15字，完全口语化，无书面连接词\n"
        "· 每段标注时间戳 [MM:SS-MM:SS]\n"
        "· 关键信息重复一遍，每隔几句加停顿标记(/)"
    ),
    "comic_strip": (
        "· 输出合法JSON数组，每格含：scene_desc（英文30-50词）/ dialogue（≤30字）/ narration（≤20字）\n"
        "· scene_desc 必须是英文\n"
        "· 每格聚焦一个情节点，对白极度精炼"
    ),
    "card_series": (
        "· 输出合法JSON数组，每张卡含：card_title / headline（≤15字）/ body_text（80-120字）/ key_takeaway（≤20字）\n"
        "· 每张卡只讲一件事，headline 独立成立"
    ),
    "patient_handbook": (
        "· 结构化段落，面向患者和家属\n"
        "· 重要提示用【注意】，医嘱用【医嘱】，紧急情况用【警告】\n"
        "· 不给出具体剂量"
    ),
    "quiz_article": (
        "· 输出合法JSON数组，每题含：question_text / options / correct_answer / explanation / key_learning\n"
        "· 问题用读者自然口吻，explanation 温和不批评"
    ),
    "picture_book": (
        "· 输出合法JSON数组，每页含：page_text（≤20字，一句话）/ illustration_desc（英文30-50词）\n"
        "· 绝对无恐惧元素，用儿童熟悉的比喻"
    ),
    "poster": (
        "· 输出JSON：main_title（≤10字）/ sub_title（≤20字）/ key_points（3条，每条≤15字动词开头）\n"
        "· 文字极度精炼，路人3秒内理解"
    ),
    "long_image": (
        "· 按区块输出，每区块含：section_title / section_body（≤100字）/ image_prompt（英文）\n"
        "· 覆盖封面区、知识区、行动区、结尾区"
    ),
    "debunk": (
        "· 固定三段式：❌ 误区 → ✅ 真相 → 📖 解释\n"
        "· 误区用普通人真实口吻，真相直接有力"
    ),
}


def get_conversion_prompt(
    source_format: str,
    target_format: str,
    source_content: str,
    target_audience: str = "public",
    platform: str = "universal",
) -> str:
    """生成内容转换任务提示词"""
    audience = AUDIENCE_PROFILES.get(target_audience, AUDIENCE_PROFILES["public"])
    strategy = CONVERSION_STRATEGY.get((source_format, target_format), "direct")
    strategy_guide = STRATEGY_GUIDE.get(strategy, STRATEGY_GUIDE["direct"])
    target_reqs = TARGET_FORMAT_REQUIREMENTS.get(
        target_format, "按照目标形式的标准格式输出。"
    )

    children_block_msg = ""
    if target_audience == "children" and target_format in CHILDREN_BLOCKED_TARGETS:
        children_block_msg = (
            f"【特别注意：儿童受众转换限制】\n"
            f"目标受众为儿童（3-12岁），{target_format} 形式不适合儿童。\n"
            f"请自动调整策略：\n"
            f"· 若目标是脚本类：改为生成 picture_book 或 comic_strip 形式\n"
            f"· 若无法转换：在内容开头说明限制，并提供替代建议\n\n"
        )

    truncated = len(source_content) > 3000
    content_preview = source_content[:3000] + ("...(已截取前3000字)" if truncated else "")

    return f"""{children_block_msg}请将以下医学科普内容从【{FORMAT_NAMES.get(source_format, source_format)}】
转换为【{FORMAT_NAMES.get(target_format, target_format)}】形式。

【原始内容】
{content_preview}

【转换信息】
目标受众：{audience['desc']}
目标平台：{platform}
转换策略：{strategy_guide}

【转换核心原则】
① 内容准确性优先：医学信息不能在转换中失真或遗漏安全提示
② 形式适配：输出必须完全符合目标形式的格式要求和语言风格
③ 受众适配：根据目标受众调整语言，不照搬原文措辞
④ 医学安全不降级：不能删除就医提示，不能把"可能"转换成"一定"，不能改成具体剂量

↓ 正确转换示范（article→oral_script）：
原文："胰岛素就像一把钥匙，帮助葡萄糖进入细胞。当细胞对胰岛素不敏感时，血糖就会升高。"
转换："你的身体里有一把钥匙，叫胰岛素。它的工作，是帮血糖进入细胞变成能量。但如果细胞开始不认这把钥匙了——血糖就会越来越高。/"

↓ 错误转换（遗漏安全提示）：
原文结尾："如出现视力模糊或严重头晕，请立即就医。"
错误转换后：[直接省略了就医提示]

【目标形式的格式要求】
{target_reqs}

请直接输出转换后内容，格式完全符合{FORMAT_NAMES.get(target_format, target_format)}的规范。
"""


_DEFAULT_CONVERSION_QA = """请检查以下内容转换是否满足质量要求。

【原始内容摘要】
{source_summary}

【转换后内容】
{converted_content}

【转换方向】
{source_format} → {target_format}
目标受众：{target_audience}

【检查维度】
1. 医学准确性（最高优先级）：核心医学信息是否失真？安全提示是否保留？是否引入原文没有的声明？
2. 形式合规性：输出格式是否完全符合目标形式规范？
3. 信息完整性：关键知识点是否都包含？
4. children 受众特殊检查（仅当 target_audience='children'）：是否有恐惧内容？每句是否≤15字？

【overall_quality 判断标准】
excellent：0 个问题
good：仅有 1-2 个 warning，无 error
needs_revision：有 3+ 个 warning，或 1 个 error（非医学准确性）
failed：医学准确性维度有任何 error

【输出格式（合法JSON）】
{{
  "passed": true,
  "issues": [{{"dimension": "...", "severity": "error|warning", "description": "...", "suggestion": "..."}}],
  "overall_quality": "excellent|good|needs_revision|failed",
  "children_check_executed": false,
  "critical_medical_issues": []
}}

请直接输出JSON。
"""


def get_conversion_qa_prompt(
    source_summary: str,
    converted_content: str,
    source_format: str,
    target_format: str,
    target_audience: str,
) -> str:
    """获取转换质量检查提示词"""
    from app.agents.prompts.loader import load_convert_prompt
    tpl = load_convert_prompt("conversion_qa")
    if tpl:
        return tpl.format(
            source_summary=source_summary,
            converted_content=converted_content,
            source_format=source_format,
            target_format=target_format,
            target_audience=target_audience,
        )
    return _DEFAULT_CONVERSION_QA.format(
        source_summary=source_summary,
        converted_content=converted_content,
        source_format=source_format,
        target_format=target_format,
        target_audience=target_audience,
    )
