"""
RAG 多源加权检索
paper_chunks 0.6 + knowledge_chunks 0.4
Ollama 可用时用 embeddings 对 FTS 候选重排序；不可用时仅 FTS5
"""
import math
import os
from typing import Optional

RETRIEVAL_WEIGHTS = {
    "paper_chunks": 0.6,
    "knowledge_chunks": 0.4,
}

# 章节类型 → chunk_type 映射（用于 paper 检索过滤）
SECTION_TO_CHUNK_TYPE = {
    "intro": ["background", "objective"],
    "body": ["methods", "results"],
    "case": ["results", "conclusion"],
    "qa": ["conclusion", "limitation"],
    "summary": ["conclusion", "abstract"],
    "opening": ["background"],  # story, audio_script
    "development": ["methods", "results"],
    "climax": ["results"],
    "resolution": ["conclusion"],
    "lesson": ["conclusion"],
    "myth_intro": ["background"],
    "myth_1": ["results"],
    "myth_2": ["results"],
    "myth_3": ["results"],
    "action_guide": ["conclusion"],
    "finding": ["results"],
    "implication": ["conclusion"],
    "caution": ["limitation"],
    "qa_intro": ["background"],
    "qa_1": ["conclusion", "limitation"],
    "qa_2": ["conclusion", "limitation"],
    "qa_3": ["conclusion", "limitation"],
    "qa_summary": ["conclusion", "abstract"],
    "hook": ["background"],
    "body_1": ["methods"],
    "body_2": ["methods", "results"],
    "body_3": ["methods", "results"],
    "summary": ["conclusion", "abstract"],
    "cta": ["conclusion"],
    "scene_setup": ["background"],
    "scene_1": ["methods", "results"],
    "scene_2": ["methods", "results"],
    "scene_3": ["results"],
    "ending": ["conclusion"],
    "frame_1": ["background"],
    "frame_2": ["methods", "results"],
    "frame_3": ["methods", "results"],
    "frame_4": ["results"],
    "frame_5": ["results"],
    "frame_6": ["conclusion"],
    "topic_intro": ["background"],
    "deep_dive": ["methods", "results"],
    "extension": ["conclusion"],
    "closing": ["conclusion"],
    "disease_intro": ["background"],
    "symptoms": ["results"],
    "treatment": ["conclusion"],
    "daily_care": ["conclusion"],
    "visit_tips": ["conclusion", "limitation"],
    "panel_1": ["background"],
    "panel_2": ["methods", "results"],
    "panel_3": ["results"],
    "panel_4": ["results"],
    "panel_5": ["results"],
    "panel_6": ["conclusion"],
    "card_1": ["background"],
    "card_2": ["methods", "results"],
    "card_3": ["results"],
    "card_4": ["results"],
    "card_5": ["conclusion"],
    "headline": ["background"],
    "core_message": ["results"],
    "data_points": ["results"],
    "visual_desc": ["results"],
    "page_1": ["background"],
    "page_2": ["methods", "results"],
    "page_3": ["results"],
    "page_4": ["results"],
    "page_5": ["conclusion"],
    "cover": ["background"],
    "section_1": ["methods", "results"],
    "section_2": ["results"],
    "section_3": ["results"],
    "footer": ["conclusion"],
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
    """对 FTS 候选用 Ollama /api/embeddings 重排序；成功返回 (top_k 条, True)。"""
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
    """RAG 多源加权检索：paper_chunks 0.6 + knowledge_chunks 0.4，Ollama 不可用时仅 FTS5"""

    async def retrieve(
        self,
        query: str,
        article_id: Optional[int] = None,
        section_type: Optional[str] = None,
        top_k: int = 5,
        specialty: Optional[str] = None,
    ) -> tuple[list[dict], bool]:
        """
        加权检索，返回 (chunks, ollama_unavailable)
        chunks: [{content, source, score}, ...]
        ollama_unavailable: 是否因 Ollama 不可用而仅用 FTS5
        specialty: 文章学科，用于对同学科知识块加权
        """
        from sqlalchemy import select
        from app.models.article import ArticleSection, ArticleLiteratureBinding
        from app.services.vector.fts5 import fts_search, paper_fts_search

        ollama_ok = _ollama_available()
        ollama_unavailable = not ollama_ok

        paper_types = SECTION_TO_CHUNK_TYPE.get(section_type) if section_type else None

        kw_paper = top_k if not paper_types else max(top_k, 3)
        kw_knowledge = top_k if not paper_types else max(top_k, 3)
        if ollama_ok:
            kw_paper = max(kw_paper, 15)
            kw_knowledge = max(kw_knowledge, 15)

        # 文章/章节绑定文献优先检索（若存在）
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
                    bind_stmt = bind_stmt.order_by(ArticleLiteratureBinding.priority.asc(), ArticleLiteratureBinding.id.asc())
                    bind_res = await session.execute(bind_stmt)
                    bound_paper_ids = [r[0] for r in bind_res.fetchall()]

        bound_rows = []
        if bound_paper_ids:
            bound_rows = await paper_fts_search(
                query,
                top_k=max(top_k, 3),
                with_content=True,
                chunk_types=paper_types,
                paper_ids=bound_paper_ids,
                only_fulltext_literature=True,
            )

        paper_rows = await paper_fts_search(
            query,
            top_k=kw_paper,
            with_content=True,
            chunk_types=paper_types,
            only_fulltext_literature=True,
        )
        knowledge_rows = await fts_search(query, top_k=kw_knowledge)

        wp = RETRIEVAL_WEIGHTS["paper_chunks"]
        wk = RETRIEVAL_WEIGHTS["knowledge_chunks"]

        scored: list[tuple[float, dict]] = []
        # 绑定文献加权更高，确保同等条件优先入选
        for r in bound_rows:
            c = r.get("content", r.get("snippet", ""))
            scored.append((min(1.0, wp + 0.25), {
                "content": c,
                "source": "paper_chunks_bound",
                "score": min(1.0, wp + 0.25),
                "paper_id": r.get("paper_id"),
                "chunk_id": r.get("chunk_id"),
            }))
        for r in paper_rows:
            c = r.get("content", r.get("snippet", ""))
            scored.append((wp, {
                "content": c,
                "source": "paper_chunks",
                "score": wp,
                "paper_id": r.get("paper_id"),
                "chunk_id": r.get("chunk_id"),
            }))
        for r in knowledge_rows:
            c = r.get("content", r.get("snippet", ""))
            chunk_specialty = r.get("specialty")
            boost = 0.15 if (specialty and chunk_specialty == specialty) else 0.0
            s = min(1.0, wk + boost)
            scored.append((s, {
                "content": c,
                "source": "knowledge_chunks",
                "score": s,
                "chunk_id": r.get("chunk_id"),
            }))

        scored.sort(key=lambda x: -x[0])
        candidates = [s[1] for s in scored]
        pool_size = max(20, top_k * 4)
        pool = candidates[:pool_size]
        if ollama_ok:
            reranked, ok = await _ollama_rerank_chunks(query, pool, top_k)
            if ok and reranked:
                return reranked, False
        return pool[:top_k], ollama_unavailable
