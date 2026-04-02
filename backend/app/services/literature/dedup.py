"""文献去重：DOI 精确 + 标题模糊"""
import difflib
from dataclasses import dataclass, field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.literature import LiteraturePaper


@dataclass
class DupCheckResult:
    exact_match: bool = False
    fuzzy_matches: list = field(default_factory=list)
    paper_id: int | None = None


class DuplicateChecker:
    """
    两级去重：
    Level 1: DOI 精确匹配（唯一优先，准确率 100%）
    Level 2: 标题 + 作者 + 年份相似度匹配（触发提示，由用户决定）
    """
    TITLE_SIMILARITY_THRESHOLD = 0.85
    FUZZY_CANDIDATE_LIMIT = 5
    TITLE_WEIGHT = 0.7
    AUTHOR_WEIGHT = 0.3

    def __init__(self, db: AsyncSession, user_id: int | None = None):
        self.db = db
        self.user_id = user_id

    async def check(
        self,
        doi: str | None,
        title: str,
        authors: list | None = None,
        year: int | None = None,
        pmid: str | None = None,
    ) -> DupCheckResult:
        authors = authors or []

        # Level 1a: DOI 精确匹配（含回收站中的记录：表上 doi 全局唯一，软删后仍占位）
        if doi:
            doi_clean = doi.strip().lower()
            if doi_clean.startswith("https://doi.org/"):
                doi_clean = doi_clean[len("https://doi.org/"):]
            if doi_clean:
                q = (
                    select(LiteraturePaper.id, LiteraturePaper.title)
                    .where(LiteraturePaper.doi == doi_clean)
                )
                if self.user_id is not None:
                    q = q.where(LiteraturePaper.user_id == self.user_id)
                result = await self.db.execute(q)
                row = result.fetchone()
                if row:
                    return DupCheckResult(exact_match=True, paper_id=row[0])

        # Level 1b: PMID 精确匹配（同上，pmid 列唯一）
        pmid_clean = str(pmid).strip() if pmid not in (None, "") else ""
        if pmid_clean:
            q = (
                select(LiteraturePaper.id, LiteraturePaper.title)
                .where(LiteraturePaper.pmid == pmid_clean)
            )
            if self.user_id is not None:
                q = q.where(LiteraturePaper.user_id == self.user_id)
            result = await self.db.execute(q)
            row = result.fetchone()
            if row:
                return DupCheckResult(exact_match=True, paper_id=row[0])

        # Level 2: 标题模糊匹配
        title_lower = (title or "").lower().strip()
        if not title_lower:
            return DupCheckResult(exact_match=False, fuzzy_matches=[])

        year_range = (year - 1, year + 1) if year else (None, None)
        candidates = await self._fetch_candidates(year_range)

        fuzzy_matches = []
        source_author_names = self._normalize_author_names(authors)
        for cand in candidates:
            title_sim = difflib.SequenceMatcher(
                None, title_lower, (cand["title"] or "").lower().strip()
            ).ratio()
            author_sim = self._author_similarity(source_author_names, self._normalize_author_names(cand["authors"]))
            sim = (title_sim * self.TITLE_WEIGHT) + (author_sim * self.AUTHOR_WEIGHT)
            if sim >= self.TITLE_SIMILARITY_THRESHOLD:
                fuzzy_matches.append({
                    "paper_id": cand["id"],
                    "title": cand["title"],
                    "year": cand["year"],
                    "title_similarity": round(title_sim, 3),
                    "author_similarity": round(author_sim, 3),
                    "similarity": round(sim, 3),
                })

        fuzzy_matches.sort(key=lambda x: -x["similarity"])
        return DupCheckResult(
            exact_match=False,
            fuzzy_matches=fuzzy_matches[: self.FUZZY_CANDIDATE_LIMIT],
        )

    async def _fetch_candidates(self, year_range: tuple) -> list[dict]:
        q = select(
            LiteraturePaper.id,
            LiteraturePaper.title,
            LiteraturePaper.year,
            LiteraturePaper.authors,
        ).where(LiteraturePaper.deleted_at.is_(None))
        if self.user_id is not None:
            q = q.where(LiteraturePaper.user_id == self.user_id)

        if year_range[0] is not None:
            q = q.where(LiteraturePaper.year.between(year_range[0], year_range[1]))

        result = await self.db.execute(q.limit(2000))
        return [dict(r._mapping) for r in result.fetchall()]

    def _normalize_author_names(self, authors: list | None) -> set[str]:
        if not authors:
            return set()
        names: set[str] = set()
        for a in authors:
            if isinstance(a, dict):
                name = (a.get("name") or "").strip().lower()
            else:
                name = str(a).strip().lower()
            if name:
                names.add(name)
        return names

    def _author_similarity(self, source: set[str], target: set[str]) -> float:
        if not source or not target:
            return 0.0
        inter = len(source & target)
        union = len(source | target)
        if union == 0:
            return 0.0
        return inter / union
