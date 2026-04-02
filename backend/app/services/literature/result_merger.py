"""Merge and deduplicate external search results."""
from __future__ import annotations

import difflib
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.literature import LiteraturePaper


class ResultMerger:
    TITLE_SIM_THRESHOLD = 0.88

    def merge(self, source_results: dict[str, list[dict]]) -> list[dict]:
        all_items: list[dict] = []
        for _, items in source_results.items():
            all_items.extend(items or [])
        if not all_items:
            return []

        doi_index: dict[str, dict] = {}
        pmid_index: dict[str, dict] = {}
        seen_titles: list[tuple[str, dict]] = []
        merged: list[dict] = []

        for item in all_items:
            doi = (item.get("doi") or "").strip().lower()
            pmid = str(item.get("pmid") or "").strip()
            if doi and doi in doi_index:
                self._merge_fields(doi_index[doi], item)
                continue
            if pmid and pmid in pmid_index:
                self._merge_fields(pmid_index[pmid], item)
                continue
            title = (item.get("title") or "").lower().strip()
            dup = self._find_title_dup(title, seen_titles)
            if dup:
                self._merge_fields(dup, item)
                continue

            if doi:
                doi_index[doi] = item
            if pmid:
                pmid_index[pmid] = item
            seen_titles.append((title, item))
            merged.append(item)

        merged.sort(key=lambda x: (0 if x.get("doi") else 1, -(x.get("cite_count") or 0), -(x.get("year") or 0)))
        return merged

    def _merge_fields(self, target: dict, supplement: dict) -> None:
        fields = ["abstract", "doi", "pmid", "url", "open_access_url", "cite_count", "pub_types"]
        for f in fields:
            if not target.get(f) and supplement.get(f):
                target[f] = supplement[f]
        sources = target.get("_sources", [target.get("source", "")])
        src = supplement.get("source", "")
        if src and src not in sources:
            sources.append(src)
        target["_sources"] = sources

    def _find_title_dup(self, title: str, seen: list[tuple[str, dict]]) -> dict | None:
        for seen_title, seen_item in seen[-50:]:
            sim = difflib.SequenceMatcher(None, title, seen_title).ratio()
            if sim >= self.TITLE_SIM_THRESHOLD:
                return seen_item
        return None


async def annotate_with_local_status(results: list[dict], db: AsyncSession, user_id: int | None = None) -> list[dict]:
    dois = [str(r.get("doi") or "").strip().lower() for r in results if str(r.get("doi") or "").strip()]
    pmids = [str(r.get("pmid") or "").strip() for r in results if str(r.get("pmid") or "").strip()]
    existing_dois = {}
    existing_pmids = {}
    if dois:
        stmt = (
            select(LiteraturePaper.doi, LiteraturePaper.id)
            .where(LiteraturePaper.doi.in_(dois))
            .where(LiteraturePaper.deleted_at.is_(None))
        )
        if user_id is not None:
            stmt = stmt.where(LiteraturePaper.user_id == user_id)
        rows = (await db.execute(stmt)).fetchall()
        existing_dois = {row.doi: row.id for row in rows}
    if pmids:
        stmt = (
            select(LiteraturePaper.pmid, LiteraturePaper.id)
            .where(LiteraturePaper.pmid.in_(pmids))
            .where(LiteraturePaper.deleted_at.is_(None))
        )
        if user_id is not None:
            stmt = stmt.where(LiteraturePaper.user_id == user_id)
        rows = (await db.execute(stmt)).fetchall()
        existing_pmids = {str(row.pmid): row.id for row in rows}

    for r in results:
        doi = str(r.get("doi") or "").strip().lower()
        pmid = str(r.get("pmid") or "").strip()
        if doi and doi in existing_dois:
            r["local_status"] = "saved"
            r["local_id"] = existing_dois[doi]
        elif pmid and pmid in existing_pmids:
            r["local_status"] = "saved"
            r["local_id"] = existing_pmids[pmid]
        else:
            r["local_status"] = "not_saved"
            r["local_id"] = None
    return results
