"""Semantic Scholar source (P1)."""
from __future__ import annotations

import asyncio
import httpx
import re
import random


class SemanticScholarSource:
    SEARCH_URL = "https://api.semanticscholar.org/graph/v1/paper/search"
    FIELDS = (
        "paperId,title,authors,year,journal,volume,publicationTypes,"
        "externalIds,abstract,citationCount,openAccessPdf,url"
    )

    def __init__(self, api_key: str | None = None):
        self.api_key = (api_key or "").strip() or None

    def _headers(self) -> dict:
        h: dict = {}
        if self.api_key:
            h["x-api-key"] = self.api_key
        return h

    async def search(
        self,
        query: str,
        year_from: int | None = None,
        year_to: int | None = None,
        pub_types: list[str] | None = None,
        max_results: int = 20,
        language: str = "all",
        progress_cb=None,
    ) -> list[dict]:
        if progress_cb:
            await progress_cb("请求 Semantic Scholar", 35)

        effective_query = query
        if re.search(r"[\u4e00-\u9fff\u3400-\u4dbf]", query):
            if progress_cb:
                await progress_cb("翻译中文关键词", 25)
            try:
                from app.services.literature.sources.pubmed import _translate_query_to_english
                effective_query = await _translate_query_to_english(query)
                print(
                    f"[SemanticScholar] Chinese query detected: '{query}' -> '{effective_query}'",
                    flush=True,
                )
            except Exception:
                pass

        params: dict = {
            "query": effective_query,
            "fields": self.FIELDS,
            "limit": min(max_results, 100),
        }
        if year_from or year_to:
            y_from = year_from or 1900
            y_to = year_to or 2099
            params["year"] = f"{y_from}-{y_to}"
        if pub_types:
            ss_map = {
                "review": "Review",
                "rct": "ClinicalTrial",
                "meta": "MetaAnalysis",
                "guideline": "ClinicalStudy",
            }
            types = [ss_map[t] for t in pub_types if t in ss_map]
            if types:
                params["publicationTypes"] = ",".join(types)

        max_attempts = 3
        last_err: Exception | None = None
        # Semantic Scholar：400 可能和 fields 组合/参数有关，做一次参数降级重试
        params_variants: list[dict] = []
        params_variants.append(dict(params))
        degraded_fields = dict(params)
        # 最小化 fields，避免字段组合触发 400
        if "fields" in degraded_fields:
            degraded_fields["fields"] = "paperId,title,authors,year,journal,abstract,externalIds,citationCount,url"
            params_variants.append(degraded_fields)
        # 再退一步：完全不传 fields
        params_variants.append({k: v for k, v in params.items() if k != "fields"})

        async with httpx.AsyncClient(timeout=8.0, headers=self._headers()) as client:
            for attempt in range(max_attempts):
                try:
                    # 从更完整到更保守逐步降级
                    pv = params_variants[min(attempt, len(params_variants) - 1)]
                    resp = await client.get(self.SEARCH_URL, params=pv)
                    if resp.status_code == 429:
                        # 429：遵循 Retry-After；否则指数退避
                        last_err = RuntimeError("Semantic Scholar 429 Too Many Requests")
                        ra = resp.headers.get("Retry-After")
                        if ra:
                            try:
                                wait_s = float(ra)
                            except Exception:
                                wait_s = min(4.0, 0.8 * (2**attempt)) + random.random() * 0.3
                        else:
                            wait_s = min(4.0, 0.8 * (2**attempt)) + random.random() * 0.3
                        await asyncio.sleep(wait_s)
                        continue
                    resp.raise_for_status()
                    data = resp.json().get("data", [])
                    break
                except httpx.HTTPStatusError as e:
                    last_err = e
                    if e.response is not None and e.response.status_code == 400:
                        # 400：继续用更保守的参数重试（下一轮 attempt 会切 variants）
                        await asyncio.sleep(0.3 + random.random() * 0.3)
                        continue
                    if e.response is not None and e.response.status_code >= 500:
                        await asyncio.sleep(min(4.0, 0.8 * (2**attempt)) + random.random() * 0.3)
                        continue
                    raise
                except Exception as e:
                    last_err = e
                    await asyncio.sleep(0.3 + random.random() * 0.3)
                    continue
            else:
                raise last_err or RuntimeError("Semantic Scholar request failed")
        if progress_cb:
            await progress_cb("解析结果", 75)
        parsed = [self._parse(it) for it in data]
        if language == "all":
            return parsed
        return [p for p in parsed if self._match_language(p, language)]

    def _parse(self, item: dict) -> dict:
        ext = item.get("externalIds") or {}
        journal = item.get("journal") or {}
        oa = item.get("openAccessPdf") or {}
        doi = (ext.get("DOI") or "").lower() or None
        pmid = ext.get("PubMed") or ""
        return {
            "source": "semantic_scholar",
            "source_id": item.get("paperId", ""),
            "title": item.get("title", ""),
            "authors": [{"name": a.get("name", ""), "affil": ""} for a in item.get("authors", [])],
            "journal": journal.get("name", "") or "",
            "year": item.get("year"),
            "volume": journal.get("volume", "") if isinstance(journal, dict) else "",
            "pages": journal.get("pages", "") if isinstance(journal, dict) else "",
            "doi": doi,
            "pmid": pmid,
            "abstract": item.get("abstract", "") or "",
            "pub_types": item.get("publicationTypes", []) or [],
            "cite_count": int(item.get("citationCount") or 0),
            "open_access_url": oa.get("url", "") or "",
            "url": item.get("url", "") or "",
        }

    def _match_language(self, paper: dict, target: str) -> bool:
        text = f"{paper.get('title', '')} {paper.get('abstract', '')}".strip()
        if not text:
            return True
        if target == "zh":
            return bool(re.search(r"[\u4e00-\u9fff]", text))
        if target == "en":
            # 保守策略：包含大量拉丁字母即视作英文可读
            latin = len(re.findall(r"[A-Za-z]", text))
            cjk = len(re.findall(r"[\u4e00-\u9fff]", text))
            return latin >= cjk
        return True

