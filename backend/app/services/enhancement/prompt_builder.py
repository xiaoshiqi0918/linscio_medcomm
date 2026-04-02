"""
四层增强提示词构建（Layer 2）
BaseAgent 调用：RAG 上下文 + Few-shot 示例 + 术语注入 + 写作规范 → 增强 prompt
"""
import json
from app.services.enhancement.rag_retriever import RAGRetriever
from app.services.enhancement.example_retriever import ExampleRetriever
from app.services.enhancement.term_injector import TermInjector
from app.agents.prompts.loader import load_task_guideline, load_comic_guideline, load_handbook_guideline
from app.services.format_router import (
    FORMAT_NAMES,
    SECTION_TITLES,
    PLATFORM_NAMES,
    AUDIENCE_NAMES,
    SPECIALTY_NAMES,
)

rag_retriever = RAGRetriever()
example_retriever = ExampleRetriever()
term_injector = TermInjector()


async def _personal_corpus_section(user_id: int = 1) -> str:
    from app.core.database import AsyncSessionLocal
    from app.services.personal_corpus_prompt import load_corpus_block

    async with AsyncSessionLocal() as db:
        return await load_corpus_block(db, user_id)

_BUILTIN_SPECIALTY_CONFIGS: dict[str, dict] = {
    "endocrine": {
        "specialty_context": "内分泌科专注于糖尿病、甲状腺疾病、代谢综合征、骨质疏松等内分泌和代谢性疾病的诊治。强调终身管理、用药依从性和三级预防（预防发生→早期干预→综合管理防并发症）。",
        "key_diseases": ["2型糖尿病", "甲状腺功能亢进/减退", "代谢综合征", "骨质疏松", "肥胖"],
        "avoid_topics": ["具体胰岛素注射剂量", "个性化降糖方案"],
        "hook_examples": [
            "体检单上的「空腹血糖 6.1」到底要不要紧？",
            "为什么吃得少了体重反而不降？",
            "脖子上的这条黑线，可能是糖尿病的预警信号",
        ],
        "children_analogies": [
            "胰岛素就像一把钥匙，帮助葡萄糖进入细胞的小房间",
            "甲状腺就像身体的小发电站，控制你的精力和体温",
        ],
    },
    "cardiology": {
        "specialty_context": "心内科覆盖冠心病、高血压、心律失常、心力衰竭、心肌病等心血管疾病。强调一级预防（危险因素控制）和二级预防（规范用药防复发），关注急性胸痛的识别和急救。",
        "key_diseases": ["冠心病", "高血压", "心房颤动", "心力衰竭", "高脂血症"],
        "avoid_topics": ["具体抗凝药物剂量", "介入手术具体操作"],
        "hook_examples": [
            "心脏在半夜叫醒你，可能是它在求救",
            "血压 130/85，处于高血压和正常之间的灰色地带",
            "胸口闷了 3 天还没好？别再以为是累的了",
        ],
        "children_analogies": [
            "心脏就像一个不停工作的小水泵，一天要跳 10 万次",
            "血管就像城市的水管，堵了水就送不到了",
        ],
    },
    "respiratory": {
        "specialty_context": "呼吸科涵盖哮喘、慢性阻塞性肺疾病(COPD)、肺炎、肺癌筛查和肺结节管理等呼吸系统疾病。强调吸入装置的正确使用、戒烟和肺功能监测。",
        "key_diseases": ["哮喘", "慢性阻塞性肺疾病(COPD)", "肺炎", "肺结节", "睡眠呼吸暂停"],
        "avoid_topics": ["具体吸入剂剂量方案", "肺癌化疗具体方案"],
        "hook_examples": [
            "咳嗽超过 8 周还没好？可能不只是感冒",
            "打呼噜不是睡得香，可能是呼吸在「罢工」",
            "体检发现肺结节，需要马上做手术吗？",
        ],
        "children_analogies": [
            "肺就像两个大气球，帮你把新鲜空气换进来",
            "哮喘发作时，气管就像被捏紧的吸管，空气很难通过",
        ],
    },
    "neurology": {
        "specialty_context": "神经科涉及脑卒中、帕金森病、阿尔茨海默病、癫痫、头痛和周围神经病变等。强调卒中的「FAST」快速识别和时间窗内急救（黄金 4.5 小时），以及慢性神经退行性疾病的长期管理。",
        "key_diseases": ["脑卒中", "帕金森病", "阿尔茨海默病", "癫痫", "偏头痛"],
        "avoid_topics": ["具体抗癫痫药物剂量", "脑血管手术细节"],
        "hook_examples": [
            "突然说不清话、一侧手脚没力——这不是「中邪」而是脑卒中",
            "记忆力下降就是老年痴呆？其实大多数不是",
            "头痛也分「好头痛」和「坏头痛」，如何区分？",
        ],
        "children_analogies": [
            "大脑就像一台超级计算机，神经就是它的电线",
            "癫痫发作就像大脑里的电路突然短路了",
        ],
    },
    "pediatrics": {
        "specialty_context": "儿科覆盖从新生儿到青少年的全年龄段健康问题，包括生长发育监测、常见传染病、过敏性疾病、儿童哮喘、营养与喂养指导。强调按龄科普、避免恐惧元素、用儿童友好的表达方式。",
        "key_diseases": ["手足口病", "儿童哮喘", "食物过敏", "腺样体肥大", "注意力缺陷多动障碍(ADHD)"],
        "avoid_topics": ["成人用药剂量", "恐惧性描述"],
        "hook_examples": [
            "宝宝反复发烧要不要马上去医院？记住这三个信号",
            "孩子总揉鼻子打喷嚏，可能不是感冒而是过敏",
            "一岁以内不能吃蜂蜜？是真的！",
        ],
        "children_analogies": [
            "白细胞就像身体里的小卫兵，专门打败入侵的坏细菌",
            "疫苗就像给小卫兵们看了一张坏人的照片，下次见到就认识了",
        ],
    },
}


def _resolve_specialty_config(specialty: str | None, specialty_config: dict | None) -> dict | None:
    """解析学科配置：优先使用传入的 specialty_config，否则从内置配置中查找。"""
    if specialty_config:
        return specialty_config
    if specialty and specialty in _BUILTIN_SPECIALTY_CONFIGS:
        return _BUILTIN_SPECIALTY_CONFIGS[specialty]
    return None


# 脚本类/图示类：RAG 用于防编造验证，不直接注入长上下文
SCRIPT_IMAGE_FORMATS = {
    "oral_script",
    "drama_script",
    "storyboard",
    "comic_strip",
    "card_series",
    "poster",
}


def _build_rag_section(rag_chunks: list[dict], content_format: str) -> str:
    """RAG 上下文注入模板"""
    if not rag_chunks:
        return ""
    if content_format in SCRIPT_IMAGE_FORMATS:
        chunks_text = "\n".join(
            f"· {c.get('content', '')[:150]}..." for c in rag_chunks[:3]
        )
        return f"""【参考资料（仅用于事实核查，不必直接引用）】
以下是从医学文献和知识库中检索到的相关内容，可作为内容准确性的参考依据：
{chunks_text}
"""
    chunks_text = "\n\n".join(
        f"[来源 {i+1}] {c.get('content', '')[:300]}"
        for i, c in enumerate(rag_chunks[:5])
    )
    return f"""【权威参考资料】
以下内容来自医学文献和科室知识库，可作为写作的知识背景（不得直接照抄，以自己的语言表达）：

{chunks_text}

注意：参考资料仅供知识背景参考，来源标注将由系统自动处理，请勿在正文中自行标注来源。
"""


def _format_example_type_header(e: dict, content_format: str) -> str:
    """生成示例类型头部：示例类型：图文文章 / 正文章节 / 面向大众 / 微信公众号 / 内分泌科"""
    parts = [
        FORMAT_NAMES.get(content_format, content_format),
        SECTION_TITLES.get(content_format, {}).get(e.get("section_type", ""), e.get("section_type", "")),
        AUDIENCE_NAMES.get(e.get("target_audience", ""), e.get("target_audience", "") or "面向大众"),
        PLATFORM_NAMES.get(e.get("platform", ""), e.get("platform", "") or "通用"),
    ]
    if e.get("specialty"):
        parts.append(SPECIALTY_NAMES.get(e["specialty"], e["specialty"]))
    return "示例类型：" + " / ".join(p for p in parts if p)


def _build_single_example(e: dict, content_format: str) -> str:
    """单条示例渲染，按形式分支"""
    header = _format_example_type_header(e, content_format)
    analysis = (e.get("analysis_text") or "").strip()

    # 条漫：优先用 content_json，按 JSON 结构展示
    if content_format in ("comic_strip", "storyboard", "card_series", "picture_book"):
        cj = e.get("content_json")
        if cj:
            try:
                obj = json.loads(cj) if isinstance(cj, str) else cj
                body = json.dumps(obj, ensure_ascii=False, indent=2)
            except (json.JSONDecodeError, TypeError):
                body = e.get("content", e.get("content_text", ""))
        else:
            body = e.get("content", e.get("content_text", ""))
    else:
        body = e.get("content", e.get("content_text", ""))

    blocks = [f"{header}\n\n---\n\n{body}"]
    if analysis:
        blocks.append(f"【分析】\n{analysis}")
    return "\n\n".join(blocks)


def _build_example_section(examples: list[dict], section_type: str, content_format: str = "article") -> str:
    """Few-shot 示例注入模板，按形式分支 + 示例类型头部 + 分析"""
    if not examples:
        return ""
    examples_text = "\n\n---\n\n".join(
        _build_single_example(e, e.get("content_format", content_format))
        for i, e in enumerate(examples[:2])
    )
    return f"""【优质示例参考】
以下是同类型科普内容的高质量示例，请参考其语言风格、结构方式和表达技巧，但不要模仿具体内容：

{examples_text}

请在保持自己创作独立性的同时，借鉴以上示例的优点。
"""


def _build_term_section(terms: list[dict], target_audience: str) -> str:
    """医学词典注入模板（v2.0：term 即 standard_zh，按受众精确分流）"""
    if not terms:
        return ""
    term_key = "term"  # DB 字段为 term，v2.0 文档称 standard_zh
    if target_audience in ("student", "professional"):
        term_lines = [
            f"· {t.get(term_key, '')}（{t.get('abbreviation', '')}）"
            for t in terms[:12]
        ]
        return f"""【术语规范】
本节涉及以下医学术语，请确保使用方式与规范一致：
{chr(10).join(term_lines)}
"""
    if target_audience == "children":
        term_lines = [
            f"· {t.get(term_key, '')}：小朋友的说法是「{t.get('layman_explain', '')}」。"
            + (f" 可以比喻成：{t.get('analogy', '')}" if t.get("analogy") else "")
            for t in terms[:6]
        ]
        return f"""【儿童友好术语】
以下术语需用儿童理解的方式表达，自然融入内容，不要生硬插入定义：
{chr(10).join(term_lines)}
"""
    term_lines = [
        f"· {t.get(term_key, '')}：通俗说法为「{t.get('layman_explain', '')}」。"
        + (f"推荐类比：{t.get('analogy', '')}" if t.get("analogy") else "")
        for t in terms[:10]
    ]
    return f"""【术语通俗化规则】
以下术语按此方式处理（优先通俗说法，专业名称括号保留）：
{chr(10).join(term_lines)}
"""


def _build_specialty_section(
    config: dict | None,
    content_format: str,
    target_audience: str,
) -> str:
    """
    学科包配置注入（v2.1）
    config 来自学科包 config.json，含 specialty_context, key_diseases, avoid_topics, hook_examples, children_analogies
    """
    if not config:
        return ""

    specialty_bg = config.get("specialty_context", "")
    key_diseases = config.get("key_diseases", [])
    avoid_topics = config.get("avoid_topics", [])
    hook_examples = config.get("hook_examples", [])
    children_analogies = config.get("children_analogies", [])

    # children 受众：注入儿童友好类比，不注入 hook_examples
    if target_audience == "children":
        children_section = ""
        if children_analogies:
            children_section = (
                "\n本学科推荐的儿童友好类比（可在内容中自然融入）：\n"
                + "\n".join(f"  · {a}" for a in children_analogies[:3])
            )
        return "\n".join(
            filter(
                None,
                [
                    "【学科专属背景（儿童友好版）】",
                    specialty_bg,
                    f"核心病种（用儿童能理解的方式描述）：{', '.join(key_diseases)}" if key_diseases else "",
                    children_section,
                ],
            )
        )

    # 非 children：hook_examples 适用形式含 comic_strip（v2.1）
    hook_formats = ("oral_script", "drama_script", "audio_script", "comic_strip")
    hook_section = ""
    if content_format in hook_formats and hook_examples:
        hook_section = (
            "\n本学科常用的开场钩子/第一格场景参考：\n"
            + "\n".join(f"  · {h}" for h in hook_examples[:3])
        )

    avoid_section = ""
    if avoid_topics:
        avoid_section = "\n【本学科禁止话题（不生成任何相关内容）】\n" + "\n".join(f"  · {t}" for t in avoid_topics)

    return "\n".join(
        filter(
            None,
            [
                "【学科专属背景】",
                specialty_bg,
                f"核心病种：{', '.join(key_diseases)}" if key_diseases else "",
                hook_section,
                avoid_section,
            ],
        )
    )


_GUIDELINE_NAME_MAP: dict[tuple[str, str], str] = {
    ("article", "intro"): "article_intro",
    ("article", "body"): "article_body",
    ("article", "case"): "article_case",
    ("article", "qa"): "article_qa",
    ("article", "summary"): "article_summary",
    ("article", "topic"): "topic_plan",
    ("article", "outline"): "outline",
    ("debunk", "myth_intro"): "debunk_intro",
    ("debunk", "myth_1"): "debunk_myth",
    ("debunk", "myth_2"): "debunk_myth",
    ("debunk", "myth_3"): "debunk_myth",
    ("debunk", "action_guide"): "debunk_action",
    ("qa_article", "qa_intro"): "qa_intro",
    ("qa_article", "qa_1"): "qa_single",
    ("qa_article", "qa_2"): "qa_single",
    ("qa_article", "qa_3"): "qa_single",
    ("qa_article", "qa_summary"): "qa_summary",
    ("story", "opening"): "story_opening",
    ("story", "development"): "story_development",
    ("story", "climax"): "story_climax",
    ("story", "resolution"): "story_resolution",
    ("story", "lesson"): "story_lesson",
    ("research_read", "background"): "research_background",
    ("research_read", "finding"): "research_finding",
    ("research_read", "implication"): "research_implication",
    ("research_read", "caution"): "research_caution",
    ("oral_script", "hook"): "oral_hook",
    ("oral_script", "body_1"): "oral_body",
    ("oral_script", "body_2"): "oral_body",
    ("oral_script", "body_3"): "oral_body",
    ("oral_script", "summary"): "oral_summary",
    ("oral_script", "cta"): "oral_cta",
    ("drama_script", "scene_setup"): "drama_scene_setup",
    ("drama_script", "scene_1"): "drama_dialogue",
    ("drama_script", "scene_2"): "drama_dialogue",
    ("drama_script", "scene_3"): "drama_dialogue",
    ("drama_script", "ending"): "drama_dialogue",
    ("storyboard", "planner"): "storyboard_planner",
    ("storyboard", "frame_1"): "storyboard_frame",
    ("storyboard", "frame_2"): "storyboard_frame",
    ("storyboard", "frame_3"): "storyboard_frame",
    ("storyboard", "frame_4"): "storyboard_frame",
    ("storyboard", "frame_5"): "storyboard_frame",
    ("storyboard", "frame_6"): "storyboard_frame",
    ("audio_script", "opening"): "audio_opening",
    ("audio_script", "topic_intro"): "audio_topic_intro",
    ("audio_script", "deep_dive"): "audio_deep_dive",
    ("audio_script", "extension"): "audio_extension",
    ("audio_script", "closing"): "audio_closing",
    ("card_series", "card_1"): "card_content",
    ("card_series", "card_2"): "card_content",
    ("card_series", "card_3"): "card_content",
    ("card_series", "card_4"): "card_content",
    ("card_series", "card_5"): "card_content",
    ("picture_book", "planner"): "picture_book_planner",
    ("picture_book", "page_1"): "picture_book_page",
    ("picture_book", "page_2"): "picture_book_page",
    ("picture_book", "page_3"): "picture_book_page",
    ("picture_book", "page_4"): "picture_book_page",
    ("picture_book", "page_5"): "picture_book_page",
    ("poster", "headline"): "poster_section",
    ("poster", "core_message"): "poster_section",
    ("poster", "data_points"): "poster_section",
    ("poster", "cta"): "poster_section",
    ("poster", "visual_desc"): "poster_section",
    ("long_image", "planner"): "long_image_planner",
    ("long_image", "section_1"): "long_image_section",
    ("long_image", "section_2"): "long_image_section",
    ("long_image", "section_3"): "long_image_section",
    ("long_image", "footer"): "long_image_footer",
    ("quiz_article", "quiz_intro"): "quiz_intro",
    ("quiz_article", "q_1"): "quiz_question",
    ("quiz_article", "q_2"): "quiz_question",
    ("quiz_article", "q_3"): "quiz_question",
    ("quiz_article", "q_4"): "quiz_question",
    ("quiz_article", "q_5"): "quiz_question",
    ("quiz_article", "summary"): "quiz_summary",
    ("h5_outline", "page_1"): "h5_page",
    ("h5_outline", "page_2"): "h5_page",
    ("h5_outline", "page_3"): "h5_page",
    ("h5_outline", "page_cover"): "h5_section",
    ("h5_outline", "page_end"): "h5_section",
}


def _load_writing_guideline(content_format: str, section_type: str) -> str:
    """加载外部写作规范模板，作为标准化参考注入增强层。

    外部 .txt 模板文件不替换基础提示词，而是作为写作标准、格式要求、
    风格规范的参考材料注入到 prompt 中，供 LLM 在生成内容时参照。
    """
    if content_format == "comic_strip":
        name = "planner" if section_type == "planner" else "panel"
        guideline = load_comic_guideline(name)
    elif content_format == "patient_handbook":
        hb_map = {
            "cover_copy": "cover", "disease_intro": "disease_intro",
            "symptoms": "symptoms", "treatment": "treatment",
            "daily_care": "daily_care", "visit_tips": "visit_tips",
        }
        name = hb_map.get(section_type, "fallback")
        guideline = load_handbook_guideline(name)
    else:
        name = _GUIDELINE_NAME_MAP.get((content_format, section_type))
        guideline = load_task_guideline(name) if name else None
    if not guideline:
        return ""
    return f"""【写作规范参考（标准化模板）】
以下是本章节的写作规范模板，描述了格式要求、风格标准和结构范例。
你的基础写作指令（在下方）已包含完整的上下文和任务细节。
此规范仅作为参考，帮助你对齐格式和风格标准，不替代基础指令中的具体要求。

---
{guideline}
---"""


def _build_prior_sections_block(prior_sections_context: str) -> str:
    """构建前序章节上下文块，确保写作连贯性"""
    if not prior_sections_context:
        return ""
    return f"""【本文已完成章节（必须保持一致性）】
以下是同一篇文章中已生成的前序章节内容，你正在撰写的章节必须与其保持人物、场景、语气、知识点的一致性，不得出现矛盾或重复。严禁新增与前序章节不同的人物、地点或设定。

{prior_sections_context}

---
请基于以上已有内容，继续撰写当前章节。"""


async def build_enhanced_prompt(
    base_prompt: str,
    topic: str,
    section_type: str,
    content_format: str,
    target_audience: str = "public",
    platform: str = "wechat",
    specialty: str | None = None,
    article_id: int | None = None,
    rag_context: list[dict] | None = None,
    examples: list[dict] | None = None,
    domain_terms: list[dict] | None = None,
    specialty_config: dict | None = None,
    prior_sections_context: str = "",
    user_id: int | None = None,
) -> tuple[str, dict]:
    """
    四层增强：RAG + Few-shot + 术语 + 个人语料 + 写作规范 + 前序章节上下文
    组装顺序：RAG → 示例 → 术语 → 个人语料 → 学科 → 写作规范 → 前序上下文 → 任务提示词（base_prompt）
    外部 .txt 模板作为「写作规范参考」注入，不替换 base_prompt。
    返回 (prompt, meta)
    """
    meta = {"ollama_unavailable": False}

    # RAG（传入 specialty 用于学科知识优先排序）
    if rag_context is None:
        rag_chunks, ollama_unavailable = await rag_retriever.retrieve(
            query=f"{topic} {section_type}",
            article_id=article_id,
            section_type=section_type,
            top_k=5 if content_format not in SCRIPT_IMAGE_FORMATS else 3,
            specialty=specialty,
        )
        meta["ollama_unavailable"] = ollama_unavailable
    else:
        rag_chunks = rag_context
    rag_section = _build_rag_section(rag_chunks, content_format)

    # Few-shot
    if examples is None:
        examples = await example_retriever.retrieve(
            content_format=content_format,
            section_type=section_type,
            target_audience=target_audience,
            platform=platform,
            specialty=specialty or None,
            top_k=2,
        )
    example_section = _build_example_section(examples, section_type, content_format)

    # 术语
    if domain_terms is None:
        domain_terms = await term_injector.get_terms_for_audience(
            topic=topic,
            target_audience=target_audience,
            specialty=specialty,
            top_k=12 if target_audience in ("student", "professional") else 10,
        )
    term_section = _build_term_section(domain_terms, target_audience)

    uid = user_id if user_id is not None else 1
    personal_section = await _personal_corpus_section(uid)

    # 学科包配置（v2.1）：优先传入的 specialty_config，否则从内置配置查找
    resolved_config = _resolve_specialty_config(specialty, specialty_config)
    specialty_section = _build_specialty_section(resolved_config, content_format, target_audience)

    # 写作规范参考（外部 .txt 模板，仅作为标准化参考）
    guideline_block = _load_writing_guideline(content_format, section_type)

    # 前序章节上下文（通用上下文记忆）
    prior_block = _build_prior_sections_block(prior_sections_context)

    parts = list(
        filter(
            None,
            [rag_section, example_section, term_section, personal_section, specialty_section,
             guideline_block, prior_block, base_prompt],
        )
    )
    return "\n\n".join(parts), meta
