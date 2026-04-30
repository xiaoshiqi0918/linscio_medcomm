"""
Few-shot 示例检索
按 content_format / section_type / target_audience / platform / specialty 检索，
支持按文章主题做 embedding 语义重排序（自动检测可用性，不可用时退化为 SQL 排序）。
"""
import logging
from typing import Optional

from sqlalchemy import select, or_
from app.core.database import AsyncSessionLocal
from app.models.example import WritingExample

_log = logging.getLogger(__name__)


class ExampleRetriever:
    """示例检索器 - 从 writing_examples 表按多维度检索 + 可选语义重排"""

    async def retrieve(
        self,
        content_format: str,
        section_type: str,
        target_audience: Optional[str] = None,
        platform: Optional[str] = None,
        specialty: Optional[str] = None,
        topic: Optional[str] = None,
        top_k: int = 3,
    ) -> list[dict]:
        """返回 [{content_json, content_text, ...}, ...]

        Args:
            topic: 当前文章主题，用于语义重排序；为空则跳过重排
        """
        pool_k = max(top_k * 3, 9)
        rows = await self._query(content_format, section_type, target_audience, platform, specialty, pool_k)
        if not rows and (target_audience or platform or specialty):
            rows = await self._query(content_format, section_type, None, None, None, pool_k)

        candidates = self._rows_to_dicts(rows)

        if topic and len(candidates) > top_k:
            reranked = await self._semantic_rerank(topic, candidates, top_k)
            if reranked is not None:
                return reranked

        return candidates[:top_k]

    # ── 内部方法 ──

    @staticmethod
    def _rows_to_dicts(rows: list) -> list[dict]:
        out = []
        for r in rows:
            if r.content_text or r.content_json:
                out.append({
                    "content_json": r.content_json,
                    "content_text": r.content_text or "",
                    "content": r.content_text or "",
                    "content_format": r.content_format,
                    "section_type": r.section_type,
                    "platform": r.platform or "",
                    "target_audience": r.target_audience or "",
                    "specialty": r.specialty or "",
                    "analysis_text": getattr(r, "analysis_text", None) or "",
                })
        return out

    async def _semantic_rerank(self, topic: str, candidates: list[dict], top_k: int) -> Optional[list[dict]]:
        """尝试用 embedding 做语义重排，失败返回 None"""
        try:
            from app.services.enhancement.rag_retriever import (
                _saas_embed_available,
                _saas_rerank_chunks,
                _ollama_rerank_chunks,
            )
        except ImportError:
            return None

        pool = [
            {"content": (c.get("content_text") or c.get("content") or "")[:2000]}
            for c in candidates
        ]
        idx_map = list(range(len(candidates)))

        try:
            if _saas_embed_available():
                ranked, ok = await _saas_rerank_chunks(topic, pool, top_k)
            else:
                ranked, ok = await _ollama_rerank_chunks(topic, pool, top_k)

            if not ok or not ranked:
                return None

            result = []
            for r in ranked:
                content = r.get("content", "")
                for i in idx_map:
                    c = candidates[i]
                    if (c.get("content_text") or c.get("content") or "")[:2000] == content:
                        result.append(c)
                        idx_map.remove(i)
                        break
            return result[:top_k] if result else None

        except Exception as exc:
            _log.debug("ExampleRetriever semantic rerank failed: %s", exc)
            return None

    async def _query(self, cf: str, st: str, ta, pl, sp, top_k: int) -> list:
        async with AsyncSessionLocal() as db:
            q = (
                select(WritingExample)
                .where(WritingExample.is_active == 1)
                .where(WritingExample.content_format == cf)
                .where(WritingExample.section_type == st)
            )
            if ta:
                q = q.where(or_(WritingExample.target_audience == ta, WritingExample.target_audience == "public", WritingExample.target_audience.is_(None)))
            if pl:
                q = q.where(or_(WritingExample.platform == pl, WritingExample.platform == "universal", WritingExample.platform.is_(None)))
            if sp:
                q = q.where(or_(WritingExample.specialty == sp, WritingExample.specialty.is_(None)))
            q = q.order_by(WritingExample.created_at.desc()).limit(top_k)
            r = await db.execute(q)
            return list(r.scalars().all())
