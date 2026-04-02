"""润色执行器：加载内容、调用 Agent、解析结果、写入 PolishChange"""
import json
import re
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.article import ArticleSection, ArticleContent, Article
from app.models.polish import PolishSession, PolishChange
from app.agents.polish.polish_agent import (
    LanguagePolishAgent,
    PlatformAdaptAgent,
    ScriptPolishAgent,
    VisualPolishAgent,
    HandbookPolishAgent,
)
from app.agents.prompts.loader import load_polish, load_writing_sop
from app.agents.prompts.anti_hallucination import MEDCOMM_EVIDENCE_LANGUAGE
from app.agents.prompts import MEDCOMM_ANTI_HALLUCINATION
from app.services.llm.openai_client import chat_completion

_POLISH_JSON_SYSTEM_BASE = load_polish("json_output_system") or "你是一个医学科普编辑助手。请严格按照要求的 JSON 格式输出，不要添加任何解释或额外文字。"

_WRITING_SOP_SUMMARY = """【润色参照标准——《医学科普文章写作与出版专家共识》要点】
润色时请以下列标准审视并改进内容：
· 科学性：确保内容基于可靠科学证据；证据分级使用匹配的程度副词
· 通俗性：专业术语须附通俗解释；语言适合目标受众
· 无损害性：不含具体用药剂量/个性化方案；案例匿名化；无视觉暴力
· 公正性：无商业推广；个人观点明确标注
· 结构性：脉络清晰、逻辑连贯、各部分不重复
· 时效性：优先使用最新权威证据"""

_SOP_TEXT = load_writing_sop()
_POLISH_JSON_SYSTEM = _POLISH_JSON_SYSTEM_BASE + ("\n\n" + _WRITING_SOP_SUMMARY if _SOP_TEXT else "")
_POLISH_JSON_SYSTEM += "\n\n" + MEDCOMM_ANTI_HALLUCINATION + "\n\n" + MEDCOMM_EVIDENCE_LANGUAGE


def _extract_text_from_doc(doc: dict) -> str:
    if isinstance(doc, str):
        return doc
    if not isinstance(doc, dict):
        return ""

    def _extract(node):
        if isinstance(node, str):
            return node
        if not isinstance(node, dict):
            return ""
        if node.get("type") == "text":
            return node.get("text", "")
        return "".join(_extract(c) for c in node.get("content", []))

    return _extract(doc)


async def load_section_content(section_id: int, db: AsyncSession) -> tuple[str, dict]:
    """加载章节内容及文章上下文，返回 (plain_text, article_ctx)"""
    result = await db.execute(
        select(ArticleSection, Article)
        .join(Article, ArticleSection.article_id == Article.id)
        .where(ArticleSection.id == section_id)
    )
    row = result.one_or_none()
    if not row:
        raise ValueError("Section not found")
    section, article = row
    if article.deleted_at:
        raise ValueError("Article not found")

    # 加载当前内容
    cont_result = await db.execute(
        select(ArticleContent).where(
            ArticleContent.section_id == section_id,
            ArticleContent.is_current == True,
        ).limit(1)
    )
    content_rec = cont_result.scalars().first()
    text = ""
    if content_rec and content_rec.content_json:
        try:
            doc = json.loads(content_rec.content_json) if isinstance(content_rec.content_json, str) else content_rec.content_json
            text = _extract_text_from_doc(doc)
        except Exception:
            pass

    ctx = {
        "topic": article.topic or "",
        "specialty": article.specialty or "",
        "target_audience": article.target_audience or "public",
        "platform": article.platform or "wechat",
        "content_format": article.content_format or "article",
    }
    return text or "", ctx


async def run_polish(
    session_id: int,
    db: AsyncSession,
) -> dict:
    """
    执行润色，写入 PolishChange
    返回 {"changes_count": N, "error": str|None}
    """
    result = await db.execute(
        select(PolishSession, ArticleSection, Article)
        .join(ArticleSection, PolishSession.section_id == ArticleSection.id)
        .join(Article, ArticleSection.article_id == Article.id)
        .where(PolishSession.id == session_id)
    )
    row = result.one_or_none()
    if not row:
        return {"changes_count": 0, "error": "Session not found"}
    session, section, article = row

    content, ctx = await load_section_content(session.section_id, db)
    if not content or len(content.strip()) < 20:
        return {"changes_count": 0, "error": "章节内容为空或过短"}

    polish_type = session.polish_type or "language"
    if polish_type == "language":
        agent = LanguagePolishAgent()
    elif polish_type == "platform":
        agent = PlatformAdaptAgent()
    elif polish_type == "script":
        agent = ScriptPolishAgent()
    elif polish_type == "visual":
        agent = VisualPolishAgent()
    elif polish_type == "handbook":
        agent = HandbookPolishAgent()
    else:
        agent = LanguagePolishAgent()

    prompt_template = agent.get_base_prompt(ctx)
    prompt = prompt_template.replace("{content}", content)

    messages = [
        {"role": "system", "content": _POLISH_JSON_SYSTEM},
        {"role": "user", "content": prompt},
    ]

    try:
        resp = await chat_completion(messages, stream=False)
        raw = (resp or "").strip()
    except Exception as e:
        return {"changes_count": 0, "error": str(e)}

    if polish_type in ("language", "script", "visual", "handbook"):
        # 解析 Track Changes：language/script/visual 为数组，handbook 为含 changes 的对象
        changes = []
        obj_match = re.search(r"\{[\s\S]*\}", raw)
        if polish_type == "handbook" and obj_match:
            try:
                obj = json.loads(obj_match.group())
                arr = obj.get("changes") or []
                for item in arr:
                    if isinstance(item, dict) and item.get("original"):
                        changes.append({
                            "original": item.get("original", ""),
                            "revised": item.get("revised", ""),
                            "reason": item.get("reason", ""),
                        })
            except json.JSONDecodeError:
                pass
        else:
            m = re.search(r"\[[\s\S]*\]", raw)
            if m:
                try:
                    arr = json.loads(m.group())
                    for item in arr:
                        if isinstance(item, dict) and item.get("original"):
                            changes.append({
                                "original": item.get("original", ""),
                                "revised": item.get("revised", ""),
                                "reason": item.get("reason", ""),
                            })
                except json.JSONDecodeError:
                    pass

        for c in changes:
            pc = PolishChange(
                session_id=session_id,
                original_text=c["original"],
                suggested_text=c["revised"],
                status="pending",
            )
            db.add(pc)
        session.status = "done"
        await db.commit()
        return {"changes_count": len(changes), "error": None}

    else:
        # platform adapt: 单条结果
        obj = {}
        m = re.search(r"\{[\s\S]*\}", raw)
        if m:
            try:
                obj = json.loads(m.group())
            except json.JSONDecodeError:
                pass

        adapted = obj.get("adapted_content", "")
        if adapted:
            pc = PolishChange(
                session_id=session_id,
                original_text=content,
                suggested_text=adapted,
                status="pending",
            )
            db.add(pc)
            session.status = "done"
            await db.commit()
            return {
                "changes_count": 1,
                "word_count": obj.get("word_count"),
                "changes_summary": obj.get("changes_summary"),
                "platform_tips": obj.get("platform_tips", []),
                "error": None,
            }
        return {"changes_count": 0, "error": "无法解析平台适配结果"}
