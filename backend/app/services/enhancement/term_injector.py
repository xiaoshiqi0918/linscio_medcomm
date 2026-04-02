"""
医学术语注入
按受众分级：public/patient 注入 layman_explain + analogy
student/professional 注入标准术语 + 缩写
"""
from typing import Optional

from sqlalchemy import select, or_
from app.core.database import AsyncSessionLocal
from app.models.term import MedicalTerm


# 受众 → 匹配的 audience_level
AUDIENCE_LEVEL_MAP = {
    "public": ["public", "patient"],
    "patient": ["public", "patient"],
    "student": ["student", "professional"],
    "professional": ["professional"],
}


class TermInjector:
    """术语注入器 - 从 medical_terms 表按受众分级检索"""

    async def get_terms_for_audience(
        self,
        topic: str,
        target_audience: str = "public",
        specialty: Optional[str] = None,
        top_k: int = 5,
    ) -> list[dict]:
        """返回 [{term, layman_explain, analogy, abbreviation, audience_level}, ...]"""
        levels = AUDIENCE_LEVEL_MAP.get(target_audience, ["public", "patient"])
        async with AsyncSessionLocal() as session:
            q = select(MedicalTerm).where(MedicalTerm.audience_level.in_(levels))
            if specialty:
                q = q.where(or_(MedicalTerm.specialty == specialty, MedicalTerm.specialty.is_(None)))
            if topic:
                kw = topic.strip()[:30]
                if kw:
                    q = q.where(MedicalTerm.term.contains(kw))
            q = q.limit(top_k * 2)
            result = await session.execute(q)
            rows = result.scalars().all()

        out = []
        article_topic = (topic or "").strip()
        topic_lower = article_topic.lower()
        for r in rows:
            if r.term:
                # v2.3：related_tip 统一规则——仅当术语名称出现在 article_topic 中时生成
                related_tip = ""
                if topic_lower and r.term and r.term.lower() in topic_lower:
                    # 与本文主题高度相关，生成简要关联提示（≤30字）
                    related_tip = (r.layman_explain or r.term)[:30]
                    if (r.layman_explain or "") and len(r.layman_explain) > 30:
                        related_tip = related_tip.rstrip("…") + "…"
                out.append({
                    "term": r.term,
                    "abbreviation": r.abbreviation,
                    "layman_explain": r.layman_explain or "",
                    "analogy": r.analogy or "",
                    "audience_level": r.audience_level or "public",
                    "related_tip": related_tip,
                })
        if not out and topic:
            return await self.get_terms_for_audience("", target_audience, specialty, top_k)
        return out[:top_k]
