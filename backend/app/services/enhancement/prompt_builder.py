"""
四层 Prompt 架构增强提示词构建（v4.0）
参照《医学科普写作系统—四层Prompt架构》设计：
  Layer 0-1 — System Message（宪法层，在 base.py 中组装）
  Part 1   — 写作能力增强（语言转化 + 结构模板 + 段落节奏 + 术语 + 学科 + 规范）
  Part 2   — 内容事实来源（结构化文献注入 + 分析报告，唯一事实依据）
  Part 3   — 写作任务（文章元信息 + 前序章节 + 任务指令 + 回指）
"""
import json
from typing import Optional
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


def _infer_evidence_level(title: str, abstract: str, journal: str) -> str:
    """基于标题/摘要/期刊关键词推断证据等级，供模型匹配证据语言规则"""
    text = f"{title} {abstract}".lower()
    if any(k in text for k in ("guideline", "指南", "推荐", "共识", "consensus", "recommendation")):
        return "指南推荐"
    if any(k in text for k in ("meta-analysis", "meta analysis", "systematic review", "荟萃分析", "系统综述", "系统评价")):
        return "Meta分析"
    if any(k in text for k in (
        "randomized controlled", "randomised controlled", "rct",
        "随机对照", "随机双盲", "double-blind", "placebo-controlled",
    )):
        return "RCT"
    if any(k in text for k in ("cohort", "case-control", "cross-sectional", "队列", "病例对照", "横断面")):
        return "观察性研究"
    if any(k in text for k in ("expert opinion", "commentary", "editorial", "专家意见", "述评")):
        return "专家意见"
    if any(k in text for k in ("animal", "mouse", "rat", "in vitro", "cell line", "动物", "小鼠", "体外")):
        return "动物/体外实验"
    return "其他"


async def _fetch_binding_order(article_id: int | None) -> list[int]:
    """获取 binding 表中按 priority 排序的 paper_id 列表，保证编号与导出/前端一致"""
    if not article_id:
        return []
    from sqlalchemy import select
    from app.core.database import AsyncSessionLocal
    from app.models.article import ArticleLiteratureBinding
    try:
        async with AsyncSessionLocal() as db:
            stmt = (
                select(ArticleLiteratureBinding.paper_id)
                .where(ArticleLiteratureBinding.article_id == article_id)
                .order_by(
                    ArticleLiteratureBinding.priority.asc(),
                    ArticleLiteratureBinding.id.asc(),
                )
            )
            result = await db.execute(stmt)
            seen = set()
            ordered = []
            for row in result.fetchall():
                pid = row[0]
                if pid not in seen:
                    seen.add(pid)
                    ordered.append(pid)
            return ordered
    except Exception:
        return []


async def _fetch_paper_meta(paper_ids: list[int]) -> dict[int, dict]:
    """批量获取文献元数据，返回 {paper_id: meta_dict}，含自动推断的证据等级"""
    if not paper_ids:
        return {}
    from sqlalchemy import select
    from app.core.database import AsyncSessionLocal
    from app.models.literature import LiteraturePaper
    try:
        async with AsyncSessionLocal() as db:
            stmt = select(LiteraturePaper).where(LiteraturePaper.id.in_(paper_ids))
            result = await db.execute(stmt)
            papers = result.scalars().all()
            meta = {}
            for p in papers:
                authors_raw = p.authors or "[]"
                try:
                    authors_list = json.loads(authors_raw) if isinstance(authors_raw, str) else (authors_raw or [])
                    author_names = [a.get("name", "") for a in authors_list if isinstance(a, dict) and a.get("name")]
                except Exception:
                    author_names = []
                title = p.title or ""
                abstract = p.abstract or ""
                journal = p.journal or ""
                meta[p.id] = {
                    "title": title,
                    "authors": author_names,
                    "journal": journal,
                    "year": p.year,
                    "volume": p.volume or "",
                    "issue": p.issue or "",
                    "pages": p.pages or "",
                    "doi": p.doi or "",
                    "url": p.url or "",
                    "abstract": abstract[:300],
                    "evidence_level": _infer_evidence_level(title, abstract, journal),
                }
            return meta
    except Exception:
        return {}


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
    if specialty_config:
        return specialty_config
    if specialty and specialty in _BUILTIN_SPECIALTY_CONFIGS:
        return _BUILTIN_SPECIALTY_CONFIGS[specialty]
    return None


SCRIPT_IMAGE_FORMATS = {
    "oral_script", "drama_script", "storyboard", "comic_strip",
    "card_series", "poster", "picture_book", "long_image",
}


# ════════════════════════════════════════════════════════════════
# Part 1 构建：写作能力增强
# ════════════════════════════════════════════════════════════════

_LANGUAGE_TRANSFORM_RULES = """## 一、语言转化规则

### 1.1 术语处理策略
- 首次出现专业术语时，紧跟通俗解释。格式：专业术语（通俗解释）
- 后续出现同一术语可直接使用，不必重复解释。
- 每段正文中专业术语不超过2个，超出时拆分段落。

### 1.2 类比使用规则
- 类比用于辅助理解，但每个类比后必须补充限定语，说明类比的边界。
  ✓ "免疫系统就像身体的警察部队，负责识别和清除入侵者。当然，真实的免疫反应远比这个比喻复杂。"
  ✗ "免疫系统就是身体的警察。"（过度简化且未限定）
- 类比三步还原检验：①还原为字面含义 ②检查是否与真实医学机制一致 ③检查是否会导致错误治疗期望

### 1.3 数字呈现规则
- 大数字用对比方式呈现：✓ "大约每11个成年人中就有1人"  ✗ "463,000,000名"
- 风险数据用自然频率：✓ "每1000人中约3人"  ✗ "发生率0.3%"
- 所有数字必须来自「内容事实来源」区域，本规则仅规定呈现方式。"""

_STRUCTURE_TEMPLATES = """## 二、结构模板库

### 模板A：疾病科普（标准型）
标题（含通俗关键词，避免纯术语标题）
导语（1-2句话概括核心信息 + 阅读价值）
一、这是什么病？（一句话定义 + 通俗解释）
二、谁容易得？（高危人群 + 风险因素）
三、身体会发出什么信号？（症状描述，从常见到少见）
四、医生怎么确诊？（检查流程，降低就医焦虑）
五、怎么治疗？（治疗路径概览，不涉及具体方案选择）
六、日常怎么管理/预防？（可操作的行为建议）
七、什么时候必须去医院？（就医红旗信号）
结语（核心信息回顾 + 就医鼓励）

### 模板B：辟谣/误区纠正型
标题（"XX是真的吗？"或"关于XX，你可能想错了"）
导语（流传说法 + 为什么需要澄清）
一、这个说法从哪来的？（溯源流传路径）
二、科学证据怎么说？（逐条对照证据）
三、正确的理解是什么？（澄清后的准确信息）
四、为什么这个误区容易流传？（认知偏差分析）
五、实际应该怎么做？（行动建议）
结语

### 模板C：健康行为/生活方式型
标题（行为导向，如"XX个习惯帮你XX"）
导语（行为与健康的关联 + 改变的价值）
一、为什么这件事重要？（机制简述）
二、具体怎么做？（分步骤行动指南，每步配原理简释）
三、常见的坑和误区（避雷指南）
四、不同人群的调整建议（按年龄/基础病/生活场景）
五、怎么判断有没有效？（可观测的指标）
结语（鼓励性收尾 + 就医提示）

【使用说明】根据文章类型选择对应模板。Part 3 的「对应模板」字段指明使用哪一个。
如果文章类型不属于以上三类，可参考最接近的模板灵活调整。"""

_PARAGRAPH_RHYTHM_RULES = """## 三、段落与节奏控制

### 3.1 段落规则
- 每段聚焦一个信息点，不混合多个独立事实。
- 正文段落长度：60-150字为宜，不超过200字。
- 每3-4个信息密集段落后，插入过渡段或总结句。

### 3.2 开头策略
- 优先使用"场景代入"式开头，让读者产生关联感。
  ✓ "体检报告上写着'血脂偏高'，很多人的第一反应是：我不胖啊，怎么会血脂高？"
  ✗ "高脂血症是指血液中脂质成分异常升高的代谢性疾病。"

### 3.3 衔接规则
- 章节之间用过渡句建立逻辑连贯性。
- 避免"下面我们来介绍""接下来讲讲"等机械过渡。

## 四、读者互动与可读性

### 4.1 互动策略
- 适当使用设问句引导思考，但每篇不超过3-5处。
- 可以使用"你可能会问""很多人好奇"等代入语，但不可过度。

### 4.2 禁止事项
- 禁止使用"震惊""竟然""99%的人不知道"等夸张话术。
- 禁止使用恐吓性表述来驱动行为改变。
  ✗ "如果不控制血糖，你的脚可能会烂掉。"
  ✓ "长期血糖控制不佳可能影响下肢血管和神经，因此定期监测和管理很重要。"
- 禁止做出绝对性承诺。
  ✗ "坚持这5个习惯，保证你远离高血压。"
  ✓ "这些习惯有助于降低高血压风险，但个体差异存在，建议配合定期体检。\""""


def _build_knowledge_section(knowledge_chunks: list[dict]) -> str:
    """知识库内容注入：作为写作方法论参考，不是内容来源"""
    if not knowledge_chunks:
        return ""
    chunks_text = "\n".join(
        f"· {c.get('content', '')[:200]}" for c in knowledge_chunks[:3]
    )
    return f"""〔知识库方法论参考〕
{chunks_text}"""


def _format_example_type_header(e: dict, content_format: str) -> str:
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
    header = _format_example_type_header(e, content_format)
    analysis = (e.get("analysis_text") or "").strip()

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
    if not examples:
        return ""
    examples_text = "\n\n---\n\n".join(
        _build_single_example(e, e.get("content_format", content_format))
        for i, e in enumerate(examples[:2])
    )
    return f"""〔风格示例〕
参考以下示例的语言风格、结构方式和表达技巧：

{examples_text}"""


def _build_term_section(terms: list[dict], target_audience: str) -> str:
    if not terms:
        return ""
    term_key = "term"
    if target_audience in ("student", "professional"):
        term_lines = [
            f"· {t.get(term_key, '')}（{t.get('abbreviation', '')}）"
            for t in terms[:12]
        ]
        return f"""〔术语规范〕
{chr(10).join(term_lines)}"""
    if target_audience == "children":
        term_lines = [
            f"· {t.get(term_key, '')}：小朋友的说法是「{t.get('layman_explain', '')}」。"
            + (f" 可以比喻成：{t.get('analogy', '')}" if t.get("analogy") else "")
            for t in terms[:6]
        ]
        return f"""〔儿童友好术语〕
{chr(10).join(term_lines)}"""
    term_lines = [
        f"· {t.get(term_key, '')}：通俗说法为「{t.get('layman_explain', '')}」。"
        + (f"推荐类比：{t.get('analogy', '')}" if t.get("analogy") else "")
        for t in terms[:10]
    ]
    return f"""〔术语通俗化规则〕
{chr(10).join(term_lines)}"""


def _build_specialty_section(
    config: dict | None,
    content_format: str,
    target_audience: str,
) -> str:
    if not config:
        return ""

    specialty_bg = config.get("specialty_context", "")
    key_diseases = config.get("key_diseases", [])
    avoid_topics = config.get("avoid_topics", [])
    hook_examples = config.get("hook_examples", [])
    children_analogies = config.get("children_analogies", [])

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
                    "〔学科背景（儿童版）〕",
                    specialty_bg,
                    f"核心病种：{', '.join(key_diseases)}" if key_diseases else "",
                    children_section,
                ],
            )
        )

    hook_formats = ("oral_script", "drama_script", "audio_script", "comic_strip")
    hook_section = ""
    if content_format in hook_formats and hook_examples:
        hook_section = (
            "\n本学科常用的开场钩子/第一格场景参考：\n"
            + "\n".join(f"  · {h}" for h in hook_examples[:3])
        )

    avoid_section = ""
    if avoid_topics:
        avoid_section = "\n禁止话题（不生成任何相关内容）：\n" + "\n".join(f"  · {t}" for t in avoid_topics)

    return "\n".join(
        filter(
            None,
            [
                "〔学科背景〕",
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
    ("debunk", "rumor_present"): "debunk_rumor_present",
    ("debunk", "verdict"): "debunk_verdict",
    ("debunk", "debunk_1"): "debunk_point",
    ("debunk", "debunk_2"): "debunk_point",
    ("debunk", "debunk_3"): "debunk_point",
    ("debunk", "correct_practice"): "debunk_correct_practice",
    ("debunk", "anti_fraud"): "debunk_anti_fraud",
    ("qa_article", "qa_intro"): "qa_intro",
    ("qa_article", "qa_1"): "qa_single",
    ("qa_article", "qa_2"): "qa_single",
    ("qa_article", "qa_3"): "qa_single",
    ("qa_article", "qa_4"): "qa_single",
    ("qa_article", "qa_5"): "qa_single",
    ("qa_article", "qa_summary"): "qa_summary",
    ("story", "hook"): "story_hook",
    ("story", "development"): "story_development",
    ("story", "turning_point"): "story_turning_point",
    ("story", "science_core"): "story_science_core",
    ("story", "resolution"): "story_resolution",
    ("story", "action_list"): "story_action_list",
    ("story", "closing_quote"): "story_closing_quote",
    ("research_read", "one_liner"): "research_one_liner",
    ("research_read", "study_card"): "research_study_card",
    ("research_read", "why_matters"): "research_why_matters",
    ("research_read", "methods"): "research_methods",
    ("research_read", "findings"): "research_findings",
    ("research_read", "implication"): "research_implication",
    ("research_read", "limitation"): "research_limitation",
    ("oral_script", "script_plan"): "oral_script_plan",
    ("oral_script", "golden_hook"): "oral_golden_hook",
    ("oral_script", "problem_setup"): "oral_problem_setup",
    ("oral_script", "core_knowledge"): "oral_core_knowledge",
    ("oral_script", "practical_tips"): "oral_practical_tips",
    ("oral_script", "closing_hook"): "oral_closing_hook",
    ("oral_script", "extras"): "oral_extras",
    ("drama_script", "drama_plan"): "drama_plan",
    ("drama_script", "cast_table"): "drama_cast_table",
    ("drama_script", "act_1"): "drama_act",
    ("drama_script", "act_2"): "drama_act",
    ("drama_script", "act_3"): "drama_act",
    ("drama_script", "act_4"): "drama_act",
    ("drama_script", "act_5"): "drama_act",
    ("drama_script", "finale"): "drama_finale",
    ("drama_script", "filming_notes"): "drama_filming_notes",
    ("storyboard", "anim_plan"): "storyboard_anim_plan",
    ("storyboard", "char_design"): "storyboard_char_design",
    ("storyboard", "reel_1"): "storyboard_reel",
    ("storyboard", "reel_2"): "storyboard_reel",
    ("storyboard", "reel_3"): "storyboard_reel",
    ("storyboard", "reel_4"): "storyboard_reel",
    ("storyboard", "reel_5"): "storyboard_reel",
    ("storyboard", "prod_notes"): "storyboard_prod_notes",
    ("audio_script", "opening"): "audio_opening",
    ("audio_script", "topic_intro"): "audio_topic_intro",
    ("audio_script", "deep_dive"): "audio_deep_dive",
    ("audio_script", "extension"): "audio_extension",
    ("audio_script", "closing"): "audio_closing",
    ("card_series", "series_plan"): "card_content",
    ("card_series", "cover_card"): "card_content",
    ("card_series", "card_1"): "card_content",
    ("card_series", "card_2"): "card_content",
    ("card_series", "card_3"): "card_content",
    ("card_series", "card_4"): "card_content",
    ("card_series", "card_5"): "card_content",
    ("card_series", "card_6"): "card_content",
    ("card_series", "card_7"): "card_content",
    ("card_series", "ending_card"): "card_content",
    ("picture_book", "book_plan"): "picture_book_planner",
    ("picture_book", "cover"): "picture_book_page",
    ("picture_book", "spread_1"): "picture_book_page",
    ("picture_book", "spread_2"): "picture_book_page",
    ("picture_book", "spread_3"): "picture_book_page",
    ("picture_book", "spread_4"): "picture_book_page",
    ("picture_book", "spread_5"): "picture_book_page",
    ("picture_book", "spread_6"): "picture_book_page",
    ("picture_book", "spread_7"): "picture_book_page",
    ("picture_book", "back_cover"): "picture_book_page",
    ("poster", "poster_brief"): "poster_section",
    ("poster", "headline"): "poster_section",
    ("poster", "body_visual"): "poster_section",
    ("poster", "cta_footer"): "poster_section",
    ("poster", "design_spec"): "poster_section",
    ("long_image", "image_plan"): "long_image_planner",
    ("long_image", "title_block"): "long_image_section",
    ("long_image", "intro_block"): "long_image_section",
    ("long_image", "core_1"): "long_image_section",
    ("long_image", "core_2"): "long_image_section",
    ("long_image", "core_3"): "long_image_section",
    ("long_image", "core_4"): "long_image_section",
    ("long_image", "tips_block"): "long_image_section",
    ("long_image", "warning_block"): "long_image_section",
    ("long_image", "summary_cta"): "long_image_footer",
    ("long_image", "footer_info"): "long_image_footer",
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
    if content_format == "comic_strip":
        name = "planner" if section_type == "planner" else "panel"
        guideline = load_comic_guideline(name)
    elif content_format == "patient_handbook":
        hb_map = {
            "handbook_plan": "cover", "cover": "cover",
            "disease_know": "disease_intro", "treatment": "treatment",
            "daily_care": "daily_care", "followup": "visit_tips",
            "emergency": "symptoms", "faq": "fallback", "back_cover": "cover",
        }
        name = hb_map.get(section_type, "fallback")
        guideline = load_handbook_guideline(name)
    else:
        name = _GUIDELINE_NAME_MAP.get((content_format, section_type))
        guideline = load_task_guideline(name) if name else None
    if not guideline:
        return ""
    return f"""〔写作规范模板〕
{guideline}"""


# ════════════════════════════════════════════════════════════════
# Part 2 构建：内容事实来源
# ════════════════════════════════════════════════════════════════

async def _build_literature_section(
    lit_chunks: list[dict],
    content_format: str,
    paper_meta: dict[int, dict] | None = None,
    binding_order: list[int] | None = None,
) -> str:
    """结构化文献注入：按 binding 表 priority 顺序编号，保证与导出/前端一致"""
    if not lit_chunks:
        return ""

    if paper_meta is None:
        paper_meta = {}

    if content_format in SCRIPT_IMAGE_FORMATS:
        chunks_text = "\n".join(
            f"· {c.get('content', '')[:150]}..." for c in lit_chunks[:3]
        )
        return f"""以下内容来自用户选定的参考文献，用于确保内容准确性：
{chunks_text}"""

    by_paper: dict[int, list[dict]] = {}
    orphans: list[dict] = []
    for c in lit_chunks:
        pid = c.get("paper_id")
        if pid and pid in paper_meta:
            by_paper.setdefault(pid, []).append(c)
        else:
            orphans.append(c)

    ordered_pids = binding_order or list(by_paper.keys())
    pid_to_idx: dict[int, int] = {}
    for i, pid in enumerate(ordered_pids, 1):
        if pid not in pid_to_idx:
            pid_to_idx[pid] = i

    sections: list[str] = []
    for pid in ordered_pids:
        if pid not in by_paper:
            continue
        chunks = by_paper.pop(pid)
        idx = pid_to_idx[pid]
        meta = paper_meta[pid]
        authors_str = ", ".join(meta["authors"][:3])
        if len(meta["authors"]) > 3:
            authors_str += " et al."
        source = meta["journal"] or "未知来源"
        year = meta["year"] or "未知年份"
        evidence = meta.get("evidence_level", "其他")

        content_parts = "\n".join(
            f"  {c.get('content', '')[:300]}" for c in chunks[:3]
        )

        block = f"""### 文献{idx}
- 编号：[{idx}]
- 标题：{meta['title']}
- 作者：{authors_str}
- 来源：{source}
- 发表时间：{year}
- 证据等级：{evidence}
- 核心内容：
{content_parts}"""
        sections.append(block)

    extra_idx = len(ordered_pids) + 1
    for pid, chunks in by_paper.items():
        meta = paper_meta.get(pid)
        if meta:
            content_parts = "\n".join(f"  {c.get('content', '')[:300]}" for c in chunks[:3])
            block = f"""### 文献{extra_idx}
- 编号：[{extra_idx}]
- 标题：{meta['title']}
- 核心内容：
{content_parts}"""
        else:
            content_parts = "\n".join(f"  {c.get('content', '')[:300]}" for c in chunks[:3])
            block = f"""### 文献{extra_idx}
- 编号：[{extra_idx}]
- 核心内容：
{content_parts}"""
        sections.append(block)
        extra_idx += 1

    for c in orphans:
        content = c.get("content", "")[:300]
        block = f"""### 文献{extra_idx}
- 编号：[{extra_idx}]
- 核心内容：
  {content}"""
        sections.append(block)
        extra_idx += 1

    return "\n\n".join(sections)


def _build_analysis_report_block(analysis_report: dict | None) -> str:
    """文献分析报告注入"""
    if not analysis_report:
        return ""
    parts = []
    if analysis_report.get("research_topic"):
        parts.append(f"核心研究主题：{analysis_report['research_topic']}")
    if analysis_report.get("key_findings"):
        findings = "\n".join(f"  - {f}" for f in analysis_report["key_findings"])
        parts.append(f"关键发现：\n{findings}")
    if analysis_report.get("methodology_summary"):
        parts.append(f"研究方法：{analysis_report['methodology_summary']}")
    if analysis_report.get("population"):
        parts.append(f"研究对象：{analysis_report['population']}")
    if analysis_report.get("clinical_significance"):
        parts.append(f"临床意义：{analysis_report['clinical_significance']}")
    if analysis_report.get("key_data_points"):
        data_lines = "\n".join(
            f"  - {d.get('label', '')}: {d.get('value', '')} (来源: {d.get('source', '')})"
            for d in analysis_report["key_data_points"]
        )
        parts.append(f"核心数据：\n{data_lines}")
    if analysis_report.get("writing_angles"):
        angles = "\n".join(f"  - {a}" for a in analysis_report["writing_angles"])
        parts.append(f"推荐写作角度：\n{angles}")
    if analysis_report.get("limitations"):
        lims = "\n".join(f"  - {l}" for l in analysis_report["limitations"])
        parts.append(f"研究局限性（写作时须客观提及）：\n{lims}")
    if not parts:
        return ""
    body = "\n".join(parts)
    return f"""### 文献分析报告（基于上述文献的结构化分析）

{body}

约束：分析报告中的数据和结论均源自上方文献，可直接引用。报告未覆盖的方面，用 [[待补充：需要关于XX的文献支持]] 占位。"""


# ════════════════════════════════════════════════════════════════
# Part 3 构建：写作任务
# ════════════════════════════════════════════════════════════════

_QA_SECTION_TYPES = {"qa", "qa_intro", "qa_1", "qa_2", "qa_3", "qa_4", "qa_5", "qa_summary"}
_SUMMARY_SECTION_TYPES = {"summary", "qa_summary", "cta"}
_STORY_SECTION_TYPES = {"hook", "development", "turning_point", "science_core",
                        "resolution", "action_list", "closing_quote"}
_DEBUNK_SECTION_TYPES = {"rumor_present", "verdict", "debunk_1", "debunk_2", "debunk_3",
                         "correct_practice", "anti_fraud"}

def _build_prior_sections_block(prior_sections_context: str, section_type: str = "",
                                content_format: str = "") -> str:
    if not prior_sections_context:
        return ""

    if content_format == "qa_article" and section_type in _QA_SECTION_TYPES:
        return f"""## 前序问答内容（严格保持问答链连贯性，严禁重复）
{prior_sections_context}

▌问答科普连贯性强制要求（逐条检查）

1. 问题角度不重复
   - 阅读前序已生成的所有问题，本题必须从完全不同的角度切入
   - 不能换个说法问同一个事——如果前序问了"能不能XX"，不能再问"XX行不行"

2. 回答内容不重复
   - 前序已经解释过的知识点、类比、数据，后续问答不得重复
   - 如果前序用了某个比喻，后续必须用不同的比喻

3. 层级递进
   - 问题链从入门→进阶→实操→特殊情况，逐步深入
   - 后续问答可以建立在前序的基础上，但不能重复内容

4. 阅读节奏
   - 可以在回答末尾自然引出下一个问题的方向，形成连贯的阅读体验"""

    if section_type in _QA_SECTION_TYPES:
        return f"""## 前序内容（Q&A 必须与正文互补，严禁重复）
{prior_sections_context}

Q&A 去重要求：正文已阐述的知识点不得再次解释；问题须是读者看完正文后仍有的新疑惑。"""

    if section_type in _SUMMARY_SECTION_TYPES:
        return f"""## 前序内容（小结必须与正文互补，严禁复述）
{prior_sections_context}

小结去重要求：
- 正文中已出现的知识点解释、类比、数据、行动建议，不得在小结中重复出现
- 小结应从更高视角提炼 1-2 个核心认知，而非逐条复述正文
- 行动要点须用全新的精炼语言，不能照搬正文原句"""

    if content_format == "story" and section_type in _STORY_SECTION_TYPES:
        return f"""## 前序故事内容（严格保持叙事连贯性）
{prior_sections_context}

▌叙事连贯性强制要求（逐条检查）

1. 人物一致性
   - 主角姓名、化名、年龄、职业、性别、家庭关系必须与前序内容完全一致，不得出现新名字或属性矛盾
   - 配角（家属、同事、医生）如已出场，后续出现时身份信息不能变化

2. 情节因果链
   - 本节内容必须自然承接前序最后的情节状态，不能跳过或遗忘已发生的事件
   - 如前序提到某个症状/事件，后续不能当它没发生过
   - 时间线要连贯：不能突然从白天跳到三个月后而不加交代

3. 情感弧线递进
   - 读者的情绪是被前序一步步建立的，本节必须延续并推进这条弧线
   - 不能出现情绪跳跃（如前序还在紧张，本节突然轻松，中间缺少过渡）

4. 医学信息一致
   - 前序提及的疾病/症状名称、诊断结论必须前后统一
   - 已经由医生说过的话不要换个人重复说

5. 过渡与衔接
   - 本节的第一句/第一段必须让读者感觉是前序自然延续，而非另起一篇文章
   - 可通过时间推移（"第二天"）、场景切换（"走出诊室"）、情绪延续（"心里还是放不下"）等方式过渡"""

    if content_format == "debunk" and section_type in _DEBUNK_SECTION_TYPES:
        return f"""## 前序辟谣内容（严格保持逻辑一致性，不得矛盾或重复）
{prior_sections_context}

▌辟谣文连贯性强制要求（逐条检查）

1. 谣言指代一致性
   - 全文针对的是同一条谣言，后续章节不能偏离或混入其他谣言
   - 谣言原文只在"谣言还原"中完整呈现一次，后续用简短指代（"前述说法""该谣言"）

2. 论据不重复（严格检查）
   - 阅读前序拆解内容，提取已使用的：漏洞类型、核心论点、类比、证据来源
   - 当前章节必须使用完全不同的漏洞类型和论证角度
   - 如果前序用了"偷换概念"，本条必须选择"剂量忽略""事实错误""恐惧利用"等其他类型
   - 前序已经使用过的类比（如"面粉≠面包""食盐中毒"），后续绝对不能重复使用

3. 结论一致性
   - "真相判定"中给出的判定结论（纯属谣言/夸大/张冠李戴/过时）贯穿全文
   - 后续拆解和正确做法必须与判定结论逻辑自洽，不能自相矛盾

4. 语气一致性
   - 全文保持"帮助读者理解"的友善语气，不出现嘲讽、说教
   - 前序如果用了某种风格（如轻松幽默/严肃权威），后续保持一致

5. 证据层级递进
   - 拆解点之间有层次感：从最明显的漏洞到较深层的问题
   - "正确做法"是在全部拆解完成后的行动指引，不提前泄露"""

    if content_format == "long_image" and section_type not in ("image_plan",):
        return f"""## 前序区块内容（保持长图的信息递进与视觉一致性）
{prior_sections_context}

▌竖版长图连贯性要求
1. 信息不重复：前序区块已讲的知识点/数据/建议，后续区块不重复
2. 配色一致：image_prompt 的色调描述与 image_plan 定义的 color_theme 一致
3. 逻辑递进：区块间有明确的信息递进关系（认知→理解→行动）
4. 每块独立：即使读者跳读，每个区块也能独立成立
5. 正文短句：控制每段不超过3行，正文用数字/动词开头"""

    if content_format == "picture_book" and section_type not in ("book_plan",):
        return f"""## 前序绘本内容（严格保持绘本故事与视觉连贯性）
{prior_sections_context}

▌科普绘本连贯性强制要求
1. 角色一致：主角和配角的名字、外貌、标志物、性格与 book_plan 和前序页完全一致
2. 叙事连贯：每个跨页只推进一个情节节点，且必须自然承接前一跨页的结尾
3. 画风统一：illustration_desc 的风格关键词（画风、配色、氛围）前后一致
4. 翻页悬念：前一跨页的 page_turn_hook 必须在本跨页得到回应/揭晓
5. 知识嵌入自然：知识点通过角色行动/对话带出，不突然切换为"科普模式"
6. 情绪递进：情绪基调要有变化弧线（好奇→困惑→发现→喜悦），不能平铺直叙
7. 文字节奏：page_text 风格保持一致——如果前序用了短句+感叹号的节奏，后续延续"""

    if content_format == "card_series" and section_type not in ("series_plan",):
        return f"""## 前序卡片内容（保持系列视觉与内容连贯性）
{prior_sections_context}

▌知识卡片系列连贯性要求
1. 视觉统一：配色、字体风格、图标风格与 series_plan 定义的保持一致
2. 编号连续：卡片编号必须与系列规划一致
3. 知识不重复：前序卡片已讲过的知识点，后续卡不重复
4. 信息密度一致：每张卡的信息量保持均衡，不出现前密后疏
5. illustration_desc 风格统一：所有卡片的配图描述保持相同的画风关键词"""

    if content_format == "oral_script" and section_type not in ("script_plan",):
        return f"""## 前序脚本内容（严格保持口播脚本的节奏与内容连贯性）
{prior_sections_context}

▌口播脚本连贯性强制要求
1. 人设一致：出镜人的身份、口吻风格、第一人称与 script_plan 完全一致
2. 信息不重复：前序段落已讲过的知识点/数据/建议，后续不重复
3. 节奏递进：开头→铺垫→科普→建议→收尾，信息密度与情绪有明确弧线
4. 口语统一：全段用"因为""所以""但是"，不用"由于""因此""然而"
5. 自然过渡：前段结尾与本段开头之间有自然衔接语，像在同一次录制中
6. 句子短：每句≤20字，让观众跟得上
7. 一个视频一个知识点：不贪多，不偏离 script_plan 的核心知识点"""

    if content_format == "drama_script" and section_type not in ("drama_plan", "cast_table"):
        return f"""## 前序剧本内容（严格保持情景剧的叙事连贯性与角色一致性）
{prior_sections_context}

▌情景剧本连贯性强制要求
1. 角色一致：角色姓名、身份、性格、外在表现与 cast_table 完全一致，不新增角色
2. 情节因果链：本场必须自然承接前一场的结尾状态，不跳过已发生的事件
3. 剧情弧线：日常建立→冲突触发→错误应对→专业介入→结局升华，每场只推进一个节拍
4. 台词风格一致：对白像"这个人真的会说的话"，不是念课文，保持口语化
5. 知识不重复：前序场景已传递的知识点，后续不重复
6. 医生角色不要"全知全能"：从倾听开始再给建议，不满口术语
7. 搞笑可以有，但不消解健康问题的严肃性"""

    if content_format == "storyboard" and section_type.startswith("reel_"):
        return f"""## 前序分镜内容（严格保持动画分镜的视觉与叙事连贯性）
{prior_sections_context}

▌动画分镜连贯性强制要求
1. 角色/元素一致：角色形象、拟人化方案与 char_design 完全一致，不新增不在设定中的视觉元素
2. 画面-旁白同步：旁白和画面必须同步对应，不能"说A画面还在B"
3. 景别节奏：景别要有变化（全景/中景/近景/特写交替），避免全程中景
4. 信息密度控制：每镜画面停留2-4秒，信息量不能太大
5. 旁白节奏：每句间留0.5-1秒气口，观众需要呼吸，核心段旁白速度放慢
6. 可视化比喻一致：机制解释段使用的可视化比喻前后统一
7. 知识不重复：前序幕已讲过的知识点后续不重复
8. 色调风格一致：画面色调和动画风格与 anim_plan 设定一致"""

    if content_format == "comic_strip" and section_type.startswith("panel_"):
        return f"""## 前序格内容（严格保持条漫的视觉与叙事连贯性）
{prior_sections_context}

▌条漫连贯性强制要求
1. 角色一致：角色的名字、外貌（服装/发型/标志物）、称呼必须与planner和前序格完全一致
2. 叙事承接：本格必须自然衔接前一格的情节，不跳跃、不矛盾
3. 画风统一：scene_desc 的风格描述（色调、画风）与前序格保持一致
4. 知识不重复：前序格已讲过的知识点，本格不重复，每格只讲一个新知识点
5. 对白风格统一：前序格如果是轻松口语风格，后续不突然变成学术腔"""

    _HB_CONTENT_TYPES = {"disease_know", "treatment", "daily_care", "followup", "emergency", "faq"}
    if content_format == "patient_handbook" and section_type in _HB_CONTENT_TYPES:
        return f"""## 前序手册内容（严格保持患者手册的信息一致性与实用导向）
{prior_sections_context}

▌患者手册连贯性强制要求
1. 疾病信息一致：前序部分提及的疾病名称、病因、严重程度描述后续不得矛盾
2. 称呼统一：全程用"你"称呼患者，不用"患者应当"
3. 语言直白：所有医学术语必须配通俗解释，或直接用大白话替代
4. 不提及具体药物名称或剂量：用药清单由患者/医生填写
5. 勾选框和表格：充分利用⬜勾选框和表格，手册是被"用"的
6. 结论一致：前序"可控"的信心基调贯穿全文，不自相矛盾"""

    _RESEARCH_READ_TYPES = {"one_liner", "study_card", "why_matters", "methods",
                             "findings", "implication", "limitation"}
    if content_format == "research_read" and section_type in _RESEARCH_READ_TYPES:
        return f"""## 前序内容（严格保持研究速读的信息一致性）
{prior_sections_context}

▌研究速读连贯性要求
1. 数据一致：前序提及的研究数据（样本量、随访时间、关键数字）后续引用时不能变化
2. 结论递进：一句话摘要→核心发现→对普通人的意义，信息逐步展开但不矛盾
3. 不提前泄露：背景和方法部分不透露结果，结果部分不讨论局限
4. 证据强度一致：对同一发现的因果/相关性判断前后统一"""

    return f"""## 前序内容（保持一致性，不得矛盾或重复）
{prior_sections_context}"""


_CONTENT_FORMAT_TO_ARTICLE_TYPE: dict[str, tuple[str, str]] = {
    "article": ("疾病科普", "模板A"),
    "debunk": ("辟谣纠正", "模板B"),
    "qa_article": ("问答科普", "模板D"),
    "story": ("健康行为", "模板C"),
    "research_read": ("研究速读", "模板E"),
    "oral_script": ("口播脚本", "短视频口播"),
    "drama_script": ("情景剧本", "短视频情景剧"),
    "audio_script": ("其他", "自定义"),
    "comic_strip": ("条漫科普", "条漫模板"),
    "storyboard": ("动画分镜", "科普动画分镜"),
    "card_series": ("知识卡片", "卡片模板"),
    "picture_book": ("科普绘本", "绘本模板"),
    "poster": ("科普海报", "海报模板"),
    "long_image": ("竖版长图", "长图模板"),
    "quiz_article": ("其他", "自定义"),
    "h5_outline": ("其他", "自定义"),
    "patient_handbook": ("患者教育手册", "患者手册模板"),
}

_AUDIENCE_TO_KNOWLEDGE_LEVEL: dict[str, str] = {
    "public": "无医学背景",
    "patient": "有基础健康知识",
    "student": "有一定医学基础",
    "professional": "有一定医学基础",
    "children": "无医学背景",
}

_AUDIENCE_TO_TONE: dict[str, str] = {
    "public": "亲和平易",
    "patient": "亲和平易",
    "student": "专业严谨",
    "professional": "专业严谨",
    "children": "轻松活泼",
}


_TEMPLATE_SECTION_MAPPING: dict[str, dict[str, str]] = {
    "article": {
        "intro": "标题 + 导语",
        "body": "一~七（按模板核心章节展开）",
        "case": "穿插在正文中的案例/场景",
        "qa": "模板外的补充 Q&A，内容须与正文互补",
        "summary": "结语（核心信息回顾 + 就医鼓励）",
    },
    "debunk": {
        "rumor_present": "标题 + 谣言还原（完整呈现谣言原文、传播场景、为何听起来有道理）",
        "verdict": "真相判定（一句话结论前置：纯属谣言/严重夸大/张冠李戴/过时信息）",
        "debunk_1": "逐条拆解·漏洞1（谣言说法 → 事实是 → 证据来源）",
        "debunk_2": "逐条拆解·漏洞2（谣言说法 → 事实是 → 证据来源）",
        "debunk_3": "逐条拆解·漏洞3（谣言说法 → 事实是 → 证据来源）",
        "correct_practice": "正确做法（可操作建议 + 就医信号 + 权威参考）",
        "anti_fraud": "防骗指南（3条通用谣言辨别方法）",
    },
}


def _build_article_meta_block(
    topic: str,
    content_format: str,
    section_type: str,
    target_audience: str,
    platform: str,
    target_word_count: int | None = None,
    tone: str | None = None,
) -> str:
    """结构化文章元信息，对应参考架构 Part 3 的「文章基本信息」"""
    format_name = FORMAT_NAMES.get(content_format, content_format)
    section_name = SECTION_TITLES.get(content_format, {}).get(section_type, section_type)
    audience_name = AUDIENCE_NAMES.get(target_audience, target_audience)
    platform_name = PLATFORM_NAMES.get(platform, platform)

    article_type, template_name = _CONTENT_FORMAT_TO_ARTICLE_TYPE.get(
        content_format, ("其他", "自定义")
    )
    knowledge_level = _AUDIENCE_TO_KNOWLEDGE_LEVEL.get(target_audience, "无医学背景")
    resolved_tone = tone or _AUDIENCE_TO_TONE.get(target_audience, "亲和平易")

    _PLATFORM_DEFAULT_WC = {
        "wechat": 1200, "xiaohongshu": 800, "douyin": 300,
        "journal": 3000, "offline": 2000,
    }
    effective_wc = target_word_count or _PLATFORM_DEFAULT_WC.get(platform, 1500)
    word_count_str = f"全文严格控制在 {effective_wc} 字以内"

    template_hint = _TEMPLATE_SECTION_MAPPING.get(content_format, {}).get(section_type, "")
    mapping_line = f"\n- 当前章节对应模板位置：{template_hint}" if template_hint else ""

    return f"""## 文章基本信息
- 主题：{topic}
- 文章类型：{article_type}
- 对应模板：{template_name}
- 内容形式：{format_name}
- 当前章节：{section_name}{mapping_line}
- 目标读者：{audience_name}
- 读者知识水平：{knowledge_level}
- 目标字数：{word_count_str}
- 语气风格：{resolved_tone}
- 发布平台：{platform_name}"""


# ════════════════════════════════════════════════════════════════
# 主装配函数
# ════════════════════════════════════════════════════════════════

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
    analysis_report: dict | None = None,
    target_word_count: int | None = None,
    tone: str | None = None,
) -> tuple[str, dict]:
    """
    四层 Prompt 架构 — User Message 装配（Part 1 + Part 2 + Part 3）。
    Layer 0-1 由 base.py 的 _build_system_prompt 负责。
    返回 (prompt, meta)
    """
    meta = {"ollama_unavailable": False}

    # ── 文献通道（Part 2 的内容来源）──
    if rag_context is None:
        lit_chunks, ollama_unavailable = await rag_retriever.retrieve_literature(
            query=f"{topic} {section_type}",
            article_id=article_id,
            section_type=section_type,
            top_k=5 if content_format not in SCRIPT_IMAGE_FORMATS else 3,
        )
        meta["ollama_unavailable"] = ollama_unavailable
    else:
        lit_chunks = rag_context

    # ── 获取 binding 顺序和文献元数据（用于 Part 2 结构化注入）──
    binding_order = await _fetch_binding_order(article_id)
    paper_ids = list({c.get("paper_id") for c in lit_chunks if c.get("paper_id")})
    all_ids = list(set(binding_order) | set(paper_ids))
    paper_meta = await _fetch_paper_meta(all_ids)

    # ── 知识通道（Part 1 的能力增强）──
    knowledge_chunks = await rag_retriever.retrieve_knowledge(
        query=f"{topic} {section_type}",
        specialty=specialty,
        top_k=3,
    )

    # ── Few-shot ──
    if examples is None:
        examples = await example_retriever.retrieve(
            content_format=content_format,
            section_type=section_type,
            target_audience=target_audience,
            platform=platform,
            specialty=specialty or None,
            top_k=2,
        )

    # ── 术语 ──
    if domain_terms is None:
        domain_terms = await term_injector.get_terms_for_audience(
            topic=topic,
            target_audience=target_audience,
            specialty=specialty,
            top_k=12 if target_audience in ("student", "professional") else 10,
        )

    uid = user_id if user_id is not None else 1
    personal_section = await _personal_corpus_section(uid)
    resolved_config = _resolve_specialty_config(specialty, specialty_config)

    # ════════════════════════════════════════════════════════════════
    # Part 1: 写作能力增强（教你怎么写）
    # 按章节裁剪以控制后期章节的 token 预算：
    #   完整注入：intro / body / case / debunk_* / rumor_present / verdict 等主体章节
    #   精简注入：qa / summary / anti_fraud / correct_practice —— 不需要结构模板和知识库方法论
    # ════════════════════════════════════════════════════════════════
    _LIGHT_SECTIONS = {"qa", "summary", "closing_quote", "action_list", "resolution",
                        "anti_fraud", "correct_practice", "qa_summary", "qa_intro",
                        "one_liner", "study_card", "limitation", "series_plan",
                        "cover_card", "ending_card", "poster_brief", "design_spec",
                        "cta_footer", "book_plan", "cover", "back_cover",
                        "image_plan", "footer_info", "summary_cta", "warning_block",
                        "script_plan", "closing_hook", "extras",
                        "drama_plan", "cast_table", "finale", "filming_notes",
                        "anim_plan", "char_design", "prod_notes",
                        "handbook_plan", "cover", "back_cover", "faq"}
    is_light = section_type in _LIGHT_SECTIONS

    if is_light:
        p1_parts = list(filter(None, [
            _LANGUAGE_TRANSFORM_RULES,
            _PARAGRAPH_RHYTHM_RULES,
            personal_section,
            _load_writing_guideline(content_format, section_type),
        ]))
    else:
        p1_parts = list(filter(None, [
            _LANGUAGE_TRANSFORM_RULES,
            _STRUCTURE_TEMPLATES,
            _build_term_section(domain_terms, target_audience),
            _build_example_section(examples, section_type, content_format),
            _PARAGRAPH_RHYTHM_RULES,
            _build_knowledge_section(knowledge_chunks),
            personal_section,
            _build_specialty_section(resolved_config, content_format, target_audience),
            _load_writing_guideline(content_format, section_type),
        ]))

    part1 = ""
    if p1_parts:
        part1 = f"""═══ 写作能力增强 ═══
【声明】以下内容用于提升写作质量，提供写作方法和范式参考。
本区域不是内容来源。具体约束：
- 本区域中出现的任何具体数字、实验结果、统计数据不得出现在正文中，
  除非在「内容事实来源」的文献中也能找到对应来源
- 如果本区域的术语用法与系统规则的证据语言规则冲突，以系统规则为准
- 如果本区域的内容与「内容事实来源」的文献有事实性矛盾，以文献为准
═══════════════════

{chr(10).join(p1_parts)}"""

    # ════════════════════════════════════════════════════════════════
    # Part 2: 内容事实来源（告诉你写什么）
    # ════════════════════════════════════════════════════════════════
    lit_section = await _build_literature_section(lit_chunks, content_format, paper_meta, binding_order)
    report_section = _build_analysis_report_block(analysis_report)
    p2_parts = list(filter(None, [lit_section, report_section]))

    if p2_parts:
        part2 = f"""═══ 内容事实来源 ═══
【声明】以下文献是本次写作任务的唯一事实性内容来源。
正文中基于文献的事实性陈述必须来自以下文献。
文献编号仅供你内部参考以定位内容来源，正文中不要输出[文献1]等编号标注（由系统自动处理）。
{'如果以下文献不足以支撑写作任务的某些部分，直接用定性描述代替，不要留任何占位符标签。' if content_format in ("qa_article", "debunk", "story", "research_read") else '如果以下文献不足以支撑写作任务的某些部分，使用 [[待补充：需要关于XX的文献支持]] 占位，不得从其他来源补充。'}
═══════════════════

{chr(10).join(p2_parts)}"""
    else:
        if content_format in {"qa_article", "debunk", "story", "research_read"}:
            part2 = """═══ 内容事实来源 ═══
当前无可用文献。请基于公认医学知识撰写，用自然语言表达来源可信度（如"医学指南建议""目前普遍认为"），不得自行编造数据或引用来源。
═══════════════════"""
        else:
            part2 = """═══ 内容事实来源 ═══
当前无可用文献。所有内容将标注为[共识]或[[待补充]]，不得自行编造数据或引用来源。
═══════════════════"""

    # ════════════════════════════════════════════════════════════════
    # Part 3: 写作任务（具体执行什么）
    # ════════════════════════════════════════════════════════════════
    meta_block = _build_article_meta_block(
        topic=topic,
        content_format=content_format,
        section_type=section_type,
        target_audience=target_audience,
        platform=platform,
        target_word_count=target_word_count,
        tone=tone,
    )
    prior_block = _build_prior_sections_block(prior_sections_context, section_type, content_format)

    p3_parts = list(filter(None, [meta_block, prior_block, base_prompt]))

    _READER_FACING_FORMATS = {"qa_article", "debunk", "story", "research_read", "comic_strip", "card_series", "poster", "picture_book", "long_image", "oral_script", "drama_script", "storyboard", "patient_handbook"}
    is_reader_facing = content_format in _READER_FACING_FORMATS

    if is_reader_facing:
        annotation_rules = """4. 🚨 禁止任何内部标注标签——不输出 [共识]、[推断]、[推断:基于XX]、[文献X]、[[待补充]]、[[待补充:XX]]。
   这些是内部处理标签，读者看到会困惑。如需表达来源可信度，用自然语言（如"医学指南建议""目前普遍认为"）。
5. 如文献不足以支撑某段内容，直接用定性描述代替，不要留占位符"""
    else:
        annotation_rules = """4. 公认医学知识必须在句末标注[共识]——包括但不限于：疾病定义、发病机制通识、通用饮食/运动原则、
   公认危险因素等。只要该事实不来自上方文献，就必须标注[共识]，不可裸写。
   推断性内容标注[推断:基于XX]
5. 如文献不足以覆盖某些内容，使用 [[待补充：需要XX类型的文献支持]] 占位"""

    part3 = f"""═══ 写作任务 ═══

{chr(10).join(p3_parts)}

## 执行指令
请严格遵循系统规则，参考上方「写作能力增强」中的方法，
仅基于上方「内容事实来源」中的文献生成当前章节。

输出要求：
1. 按照对应模板的结构组织当前章节
2. 严格遵守当前章节的字数限制（见上方「写作要求」中的字数行），宁可精炼不可超字
3. 文献引用编号由系统自动处理，正文中不要自行添加[1][2]等编号；
   可自然标注来源归属（如"研究显示……""指南建议……"），前提是来自「内容事实来源」
{annotation_rules}
6. 不要在本章节末尾附参考文献列表或溯源摘要（均由系统自动处理）

⚠ 回顾提醒：正文中每个事实性陈述的依据只能来自上方「内容事实来源」区域的文献，
「写作能力增强」区域的材料仅供参考写法，其中的数据和结论不可直接使用。"""

    # ── 合并 ──
    final_parts = list(filter(None, [part1, part2, part3]))
    return "\n\n\n".join(final_parts), meta
