"""
辅助提示词（v2.3）
SCENE_DESC_OPTIMIZE / RAG_FILTER / FEEDBACK_INTEGRATE / COMPRESS / TERM_EXPLAIN
供图像优化、RAG 过滤、反馈整合、平台裁剪、术语解释等场景使用
"""
from app.agents.prompts.loader import load_auxiliary


def get_scene_desc_optimize_prompt(
    raw_desc: str,
    image_type: str,
    style: str,
    target_audience: str,
    medical_topic: str,
) -> str:
    """图像提示词反向优化"""
    tpl = load_auxiliary("scene_desc_optimize")
    if tpl:
        return tpl.format(
            raw_desc=raw_desc,
            image_type=image_type,
            style=style,
            target_audience=target_audience,
            medical_topic=medical_topic,
        )
    return _DEFAULT_SCENE_DESC_OPTIMIZE.format(
        raw_desc=raw_desc,
        image_type=image_type,
        style=style,
        target_audience=target_audience,
        medical_topic=medical_topic,
    )


def get_rag_filter_prompt(
    content_format: str,
    section_type: str,
    topic: str,
    target_audience: str,
    raw_chunks: str,
    chunk_count: int,
) -> str:
    """RAG 检索结果摘要过滤"""
    tpl = load_auxiliary("rag_filter")
    if tpl:
        return tpl.format(
            content_format=content_format,
            section_type=section_type,
            topic=topic,
            target_audience=target_audience,
            raw_chunks=raw_chunks,
            chunk_count=chunk_count,
        )
    return _DEFAULT_RAG_FILTER.format(
        content_format=content_format,
        section_type=section_type,
        topic=topic,
        target_audience=target_audience,
        raw_chunks=raw_chunks,
        chunk_count=chunk_count,
    )


def get_feedback_integrate_prompt(
    original_content: str,
    user_feedback: str,
    content_format: str,
    section_type: str,
    target_audience: str,
    platform: str,
) -> str:
    """多轮写作反馈整合"""
    tpl = load_auxiliary("feedback_integrate")
    if tpl:
        return tpl.format(
            original_content=original_content,
            user_feedback=user_feedback,
            content_format=content_format,
            section_type=section_type,
            target_audience=target_audience,
            platform=platform,
        )
    return _DEFAULT_FEEDBACK_INTEGRATE.format(
        original_content=original_content,
        user_feedback=user_feedback,
        content_format=content_format,
        section_type=section_type,
        target_audience=target_audience,
        platform=platform,
    )


def get_compress_prompt(
    original_content: str,
    platform: str,
    target_max_words: int,
    current_words: int,
    target_audience: str,
) -> str:
    """平台字数智能裁剪"""
    compress_ratio = 1 - (target_max_words / current_words) if current_words > 0 else 0
    tpl = load_auxiliary("compress")
    if tpl:
        return tpl.format(
            original_content=original_content,
            platform=platform,
            target_max_words=target_max_words,
            current_words=current_words,
            compress_ratio=compress_ratio,
            target_audience=target_audience,
        )
    return _DEFAULT_COMPRESS.format(
        original_content=original_content,
        platform=platform,
        target_max_words=target_max_words,
        current_words=current_words,
        compress_ratio=compress_ratio,
        target_audience=target_audience,
    )


def get_term_explain_prompt(
    term_zh: str,
    term_en: str,
    term_abbr: str,
    article_topic: str,
    target_audience: str,
    section_type: str,
) -> str:
    """术语解释卡片生成"""
    tpl = load_auxiliary("term_explain")
    if tpl:
        return tpl.format(
            term_zh=term_zh,
            term_en=term_en,
            term_abbr=term_abbr,
            article_topic=article_topic,
            target_audience=target_audience,
            section_type=section_type,
        )
    return _DEFAULT_TERM_EXPLAIN.format(
        term_zh=term_zh,
        term_en=term_en,
        term_abbr=term_abbr,
        article_topic=article_topic,
        target_audience=target_audience,
        section_type=section_type,
    )


# 默认模板（当 prompt-example 无对应文件时使用）
_DEFAULT_SCENE_DESC_OPTIMIZE = """请将以下图像需求描述优化为高质量的 AI 图像生成提示词（英文）。

【原始描述】
{raw_desc}

【图像上下文】
图像类型：{image_type}
图像风格：{style}
目标受众：{target_audience}
医学主题：{medical_topic}

【优化目标】
将原始描述转化为结构清晰、细节丰富、DALL·E 3 可高质量生成的英文提示词。

【必须包含的五要素】
主体（Subject）、动作/状态（Action）、背景（Background）、风格（Style）、氛围（Mood）

【输出格式（合法JSON）】
{{"optimized_prompt": "...", "negative_prompt": "...", "quality_score": 0.0, "improvement_notes": "...", "missing_elements": []}}

请直接输出JSON。
"""

_DEFAULT_RAG_FILTER = """请对以下检索到的医学文献内容进行相关性过滤和摘要整理。

【当前写作任务】
科普形式：{content_format}
章节类型：{section_type}
主题：{topic}
目标受众：{target_audience}

【检索到的原始内容（共 {chunk_count} 段）】
{raw_chunks}

【过滤任务】
相关性≥0.7：提取可用信息，整理为≤60字摘要，usable=true
相关性0.4-0.7：记录在 low_relevance_note，不纳入 top_insights
相关性<0.4：忽略

【输出格式（合法JSON）】
{{"filtered_chunks": [...], "top_insights": [...], "data_points": [...], "low_relevance_note": "", "overall_quality": "rich|adequate|sparse", "fallback_needed": false, "fallback_reason": ""}}

请直接输出JSON。
"""

_DEFAULT_FEEDBACK_INTEGRATE = """请根据用户的修改反馈，对以下内容进行定向改写。

【原始生成内容】
{original_content}

【用户修改反馈】
{user_feedback}

【写作上下文】
科普形式：{content_format}
章节类型：{section_type}
目标受众：{target_audience}
目标平台：{platform}

【医学安全不降级原则（最高优先级）】
就医提示、不确定性说明、安全警示不能因用户要求而删除。

【输出格式（合法JSON）】
{{"rewritten_content": "...", "change_summary": "...", "feedback_type": "...", "medical_safety_preserved": true, "safety_notes": "", "word_count_before": 0, "word_count_after": 0}}

请直接输出JSON。
"""

_DEFAULT_COMPRESS = """请将以下医学科普内容压缩到目标字数范围内。

【原始内容】
{original_content}

【压缩目标】
目标平台：{platform}
字数上限：{target_max_words}字
当前字数：{current_words}字
需要压缩比例：{compress_ratio:.0%}
目标受众：{target_audience}

【内容保留优先级】
第一优先：就医提示、核心行动建议、纠正危险误区
第二优先：核心知识点、关键类比
可压缩：重复说明、过渡语句、次要例子

【输出格式（合法JSON）】
{{"compress_executed": true, "compressed_content": "...", "word_count_before": {current_words}, "word_count_after": 0, "compress_ratio_actual": 0.0, "deleted_types": [], "safety_check": "是/否", "skip_reason": ""}}

请直接输出JSON。
"""

_DEFAULT_TERM_EXPLAIN = """请为以下医学术语生成一个解释卡片。

【术语信息】
术语：{term_zh}
英文：{term_en}
缩写：{term_abbr}

【读者上下文】
当前文章主题：{article_topic}
目标受众：{target_audience}
当前章节：{section_type}

【related_tip 规则】
若术语名称出现在 article_topic 中，生成1条≤30字关联提示；否则为空字符串。

【输出格式（合法JSON）】
{{"term_zh": "{term_zh}", "term_en": "{term_en}", "abbreviation": "{term_abbr}", "explanation": "...", "related_tip": ""}}

请直接输出JSON。
"""
