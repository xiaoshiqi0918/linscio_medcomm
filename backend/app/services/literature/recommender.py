"""文献相似推荐（优先向量，失败时关键词降级）"""
import json
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.paper import PaperChunk
from app.models.literature import LiteraturePaper


class SimilarPaperRecommender:
    """基于 sqlite-vec（可选）+ 关键词重叠的相似推荐。"""

    async def recommend(
        self,
        paper_id: int,
        db: AsyncSession,
        top_k: int = 5,
    ) -> list[dict]:
        target = await db.execute(
            select(PaperChunk.embedding)
            .where(PaperChunk.paper_id == paper_id)
            .where(PaperChunk.embedding.is_not(None))
            .limit(1)
        )
        row = target.fetchone()

        if row and row[0]:
            try:
                results = await db.execute(
                    text(
                        """
                        SELECT p.id, p.title, p.authors, p.year, p.journal,
                               vec_distance_cosine(c.embedding, :target_vec) AS distance
                        FROM paper_chunks c
                        JOIN literature_papers p ON c.paper_id = p.id
                        WHERE c.paper_id != :paper_id
                          AND p.deleted_at IS NULL
                          AND c.embedding IS NOT NULL
                        ORDER BY distance ASC
                        LIMIT :top_k
                        """
                    ),
                    {"target_vec": row[0], "paper_id": paper_id, "top_k": top_k},
                )
                return [dict(r._mapping) for r in results.fetchall()]
            except Exception:
                # sqlite-vec 不可用时自动降级
                pass

        return await self._keyword_fallback(db, paper_id, top_k)

    async def _keyword_fallback(self, db: AsyncSession, paper_id: int, top_k: int) -> list[dict]:
        paper_result = await db.execute(
            select(LiteraturePaper).where(
                LiteraturePaper.id == paper_id,
                LiteraturePaper.deleted_at.is_(None),
            )
        )
        paper = paper_result.scalar_one_or_none()
        if not paper:
            return []

        try:
            keywords = json.loads(paper.keywords) if isinstance(paper.keywords, str) else (paper.keywords or [])
        except Exception:
            keywords = []
        target_kw = {str(k).strip().lower() for k in keywords if str(k).strip()}
        if not target_kw:
            return []

        candidates_result = await db.execute(
            select(LiteraturePaper).where(
                LiteraturePaper.id != paper_id,
                LiteraturePaper.deleted_at.is_(None),
            ).limit(300)
        )
        scored: list[dict] = []
        for cand in candidates_result.scalars().all():
            try:
                cand_keywords = json.loads(cand.keywords) if isinstance(cand.keywords, str) else (cand.keywords or [])
            except Exception:
                cand_keywords = []
            cand_kw = {str(k).strip().lower() for k in cand_keywords if str(k).strip()}
            if not cand_kw:
                continue
            overlap = len(target_kw & cand_kw)
            if overlap <= 0:
                continue
            scored.append(
                {
                    "id": cand.id,
                    "title": cand.title,
                    "authors": cand.authors,
                    "year": cand.year,
                    "journal": cand.journal,
                    "keyword_overlap": overlap,
                    "distance": None,
                }
            )

        scored.sort(key=lambda x: x["keyword_overlap"], reverse=True)
        return scored[:top_k]
