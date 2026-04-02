"""
Few-shot 示例检索
按 content_format / section_type / target_audience / platform / specialty 检索
"""
from typing import Optional

from sqlalchemy import select, or_
from app.core.database import AsyncSessionLocal
from app.models.example import WritingExample


class ExampleRetriever:
    """示例检索器 - 从 writing_examples 表按多维度检索"""

    async def retrieve(
        self,
        content_format: str,
        section_type: str,
        target_audience: Optional[str] = None,
        platform: Optional[str] = None,
        specialty: Optional[str] = None,
        top_k: int = 3,
    ) -> list[dict]:
        """返回 [{content_json, content_text, ...}, ...]，无匹配时放宽可选维度"""
        rows = await self._query(content_format, section_type, target_audience, platform, specialty, top_k)
        if not rows and (target_audience or platform or specialty):
            rows = await self._query(content_format, section_type, None, None, None, top_k)
        out = []
        for r in rows:
            if (r.content_text or r.content_json) and len(out) < top_k:
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
        return out[:top_k]

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
            q = q.order_by(WritingExample.created_at.desc()).limit(top_k * 2)
            r = await db.execute(q)
            return list(r.scalars().all())
