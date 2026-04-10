"""
RAG 双通道检索：
  - 文献通道（paper_chunks）：用户选中的参考文献，作为正文内容事实来源
  - 知识通道（knowledge_chunks）：知识库/学科包内容，用于写作能力增强
两个通道独立检索、独立注入，永不混合。
"""
import math
import os
from typing import Optional

SECTION_TO_CHUNK_TYPE = {
    "intro": ["background", "objective"],
    "body": ["methods", "results"],
    "case": ["results", "conclusion"],
    "qa": ["conclusion", "limitation"],
    "summary": ["conclusion", "abstract"],
    "hook": ["background"],
    "development": ["methods", "results"],
    "turning_point": ["results"],
    "science_core": ["methods", "results", "background"],
    "resolution": ["conclusion"],
    "action_list": ["conclusion"],
    "closing_quote": ["conclusion"],
    "rumor_present": ["background"],
    "verdict": ["results", "conclusion"],
    "debunk_1": ["results", "methods"],
    "debunk_2": ["results", "methods"],
    "debunk_3": ["results", "methods"],
    "correct_practice": ["conclusion", "results"],
    "anti_fraud": ["conclusion"],
    "one_liner": ["abstract", "conclusion"],
    "study_card": ["abstract", "methods"],
    "why_matters": ["background", "objective"],
    "methods": ["methods"],
    "findings": ["results"],
    "implication": ["conclusion"],
    "limitation": ["limitation"],
    "qa_intro": ["background"],
    "qa_1": ["conclusion", "limitation"],
    "qa_2": ["conclusion", "limitation"],
    "qa_3": ["results", "conclusion"],
    "qa_4": ["methods", "results"],
    "qa_5": ["limitation", "conclusion"],
    "qa_summary": ["conclusion", "abstract"],
    "script_plan": ["abstract", "background"],
    "golden_hook": ["background"],
    "problem_setup": ["background", "methods"],
    "core_knowledge": ["methods", "results", "background"],
    "practical_tips": ["conclusion", "results"],
    "closing_hook": ["conclusion"],
    "extras": ["abstract"],
    "drama_plan": ["abstract", "background"],
    "cast_table": ["background"],
    "act_1": ["background"],
    "act_2": ["background", "methods"],
    "act_3": ["methods", "results"],
    "act_4": ["methods", "results", "conclusion"],
    "act_5": ["conclusion", "results"],
    "finale": ["conclusion"],
    "filming_notes": ["abstract"],
    "anim_plan": ["abstract", "background"],
    "char_design": ["abstract", "background"],
    "reel_1": ["background"],
    "reel_2": ["background", "methods"],
    "reel_3": ["methods", "results", "conclusion"],
    "reel_4": ["results", "conclusion"],
    "reel_5": ["conclusion"],
    "prod_notes": ["abstract"],
    "topic_intro": ["background"],
    "deep_dive": ["methods", "results"],
    "extension": ["conclusion"],
    "closing": ["conclusion"],
    "disease_intro": ["background"],
    "symptoms": ["results"],
    "handbook_plan": ["abstract", "background"],
    "disease_know": ["background"],
    "treatment": ["conclusion"],
    "daily_care": ["conclusion"],
    "followup": ["conclusion", "limitation"],
    "emergency": ["results", "conclusion"],
    "faq": ["background", "conclusion"],
    "visit_tips": ["conclusion", "limitation"],
    "panel_1": ["background"],
    "panel_2": ["background"],
    "panel_3": ["background", "results"],
    "panel_4": ["results"],
    "panel_5": ["results"],
    "panel_6": ["results", "methods"],
    "panel_7": ["results", "methods"],
    "panel_8": ["results"],
    "panel_9": ["conclusion", "results"],
    "panel_10": ["conclusion"],
    "panel_11": ["conclusion"],
    "panel_12": ["conclusion"],
    "series_plan": ["abstract", "conclusion"],
    "cover_card": ["abstract", "background"],
    "card_1": ["background"],
    "card_2": ["results", "methods"],
    "card_3": ["results"],
    "card_4": ["results"],
    "card_5": ["results", "conclusion"],
    "card_6": ["results", "conclusion"],
    "card_7": ["conclusion"],
    "ending_card": ["conclusion"],
    "poster_brief": ["abstract", "background"],
    "headline": ["background", "abstract"],
    "body_visual": ["results", "background"],
    "cta_footer": ["conclusion"],
    "design_spec": ["abstract"],
    "book_plan": ["abstract", "background"],
    "spread_1": ["background"],
    "spread_2": ["background", "methods"],
    "spread_3": ["methods", "results"],
    "spread_4": ["results"],
    "spread_5": ["results"],
    "spread_6": ["results", "conclusion"],
    "spread_7": ["conclusion"],
    "back_cover": ["conclusion"],
    "image_plan": ["abstract", "background"],
    "title_block": ["abstract", "background"],
    "intro_block": ["background"],
    "core_1": ["background", "methods"],
    "core_2": ["methods", "results"],
    "core_3": ["results"],
    "core_4": ["results", "conclusion"],
    "tips_block": ["conclusion"],
    "warning_block": ["results", "conclusion"],
    "summary_cta": ["conclusion"],
    "footer_info": ["conclusion"],
    "cover": ["background"],
    "cover_copy": ["background"],
    "quiz_intro": ["background"],
    "q_1": ["results"],
    "q_2": ["results"],
    "q_3": ["results"],
    "q_4": ["results"],
    "q_5": ["results"],
    "page_cover": ["background"],
    "page_end": ["conclusion"],
}


def _ollama_available() -> bool:
    try:
        import httpx
        r = httpx.get("http://127.0.0.1:11434/api/tags", timeout=2.0)
        return r.status_code == 200
    except Exception:
        return False


def _cosine_sim(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na < 1e-12 or nb < 1e-12:
        return 0.0
    return dot / (na * nb)


async def _ollama_rerank_chunks(query: str, pool: list[dict], top_k: int) -> tuple[list[dict], bool]:
    """对 FTS 候选用 Ollama /api/embeddings 重排序"""
    if not pool:
        return [], False
    model = os.environ.get("OLLAMA_EMBED_MODEL", "nomic-embed-text")
    try:
        import httpx
        async with httpx.AsyncClient(timeout=120.0) as client:
            rq = await client.post(
                "http://127.0.0.1:11434/api/embeddings",
                json={"model": model, "prompt": (query or "")[:4000]},
            )
            if rq.status_code != 200:
                return [], False
            qemb = rq.json().get("embedding")
            if not isinstance(qemb, list) or not qemb:
                return [], False
            scored: list[tuple[float, dict]] = []
            for ch in pool:
                text = (ch.get("content") or ch.get("snippet") or "")[:3000]
                if not text.strip():
                    continue
                er = await client.post(
                    "http://127.0.0.1:11434/api/embeddings",
                    json={"model": model, "prompt": text},
                )
                if er.status_code != 200:
                    continue
                emb = er.json().get("embedding")
                if not isinstance(emb, list) or not emb:
                    continue
                scored.append((_cosine_sim(qemb, emb), ch))
            if not scored:
                return [], False
            scored.sort(key=lambda x: -x[0])
            return [x[1] for x in scored[:top_k]], True
    except Exception:
        return [], False


class RAGRetriever:
    """双通道 RAG 检索器"""

    async def retrieve_literature(
        self,
        query: str,
        article_id: Optional[int] = None,
        section_type: Optional[str] = None,
        top_k: int = 5,
    ) -> tuple[list[dict], bool]:
        """文献通道：仅检索用户绑定的参考文献，返回 (chunks, ollama_unavailable)"""
        from sqlalchemy import select
        from app.models.article import ArticleSection, ArticleLiteratureBinding
        from app.services.vector.fts5 import paper_fts_search

        ollama_ok = _ollama_available()
        paper_types = SECTION_TO_CHUNK_TYPE.get(section_type) if section_type else None

        bound_paper_ids: list[int] = []
        if article_id:
            section_id = None
            if section_type:
                from app.core.database import AsyncSessionLocal
                async with AsyncSessionLocal() as session:
                    sec_res = await session.execute(
                        select(ArticleSection.id).where(
                            ArticleSection.article_id == article_id,
                            ArticleSection.section_type == section_type,
                        ).limit(1)
                    )
                    sec_row = sec_res.first()
                    section_id = sec_row[0] if sec_row else None

                    bind_stmt = select(ArticleLiteratureBinding.paper_id).where(
                        ArticleLiteratureBinding.article_id == article_id
                    )
                    if section_id:
                        bind_stmt = bind_stmt.where(
                            (ArticleLiteratureBinding.section_id == section_id) |
                            (ArticleLiteratureBinding.section_id.is_(None))
                        )
                    else:
                        bind_stmt = bind_stmt.where(ArticleLiteratureBinding.section_id.is_(None))
                    bind_stmt = bind_stmt.order_by(
                        ArticleLiteratureBinding.priority.asc(),
                        ArticleLiteratureBinding.id.asc(),
                    )
                    bind_res = await session.execute(bind_stmt)
                    bound_paper_ids = [r[0] for r in bind_res.fetchall()]

        if not bound_paper_ids:
            return [], not ollama_ok

        kw = max(top_k, 5)
        if ollama_ok:
            kw = max(kw, 15)

        rows = await paper_fts_search(
            query,
            top_k=kw,
            with_content=True,
            chunk_types=paper_types,
            paper_ids=bound_paper_ids,
            only_fulltext_literature=True,
        )

        chunks = [
            {
                "content": r.get("content", r.get("snippet", "")),
                "source": "paper_chunks_bound",
                "paper_id": r.get("paper_id"),
                "chunk_id": r.get("chunk_id"),
            }
            for r in rows
        ]

        if ollama_ok and chunks:
            reranked, ok = await _ollama_rerank_chunks(query, chunks, top_k)
            if ok and reranked:
                return reranked, False

        return chunks[:top_k], not ollama_ok

    async def retrieve_knowledge(
        self,
        query: str,
        specialty: Optional[str] = None,
        top_k: int = 3,
    ) -> list[dict]:
        """知识通道：检索知识库/学科包内容，用于写作能力增强（非内容来源）"""
        from app.services.vector.fts5 import fts_search

        rows = await fts_search(query, top_k=max(top_k, 5))

        scored: list[tuple[float, dict]] = []
        for r in rows:
            c = r.get("content", r.get("snippet", ""))
            chunk_specialty = r.get("specialty")
            boost = 0.15 if (specialty and chunk_specialty == specialty) else 0.0
            scored.append((0.5 + boost, {
                "content": c,
                "source": "knowledge_chunks",
                "specialty": chunk_specialty,
                "chunk_id": r.get("chunk_id"),
            }))

        scored.sort(key=lambda x: -x[0])
        return [s[1] for s in scored[:top_k]]

    async def retrieve(
        self,
        query: str,
        article_id: Optional[int] = None,
        section_type: Optional[str] = None,
        top_k: int = 5,
        specialty: Optional[str] = None,
    ) -> tuple[list[dict], bool]:
        """兼容旧接口：返回 (literature_chunks, ollama_unavailable)
        知识库通道需单独调用 retrieve_knowledge()"""
        return await self.retrieve_literature(
            query=query,
            article_id=article_id,
            section_type=section_type,
            top_k=top_k,
        )
