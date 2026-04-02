"""Multi-source search coordinator."""
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass

from app.core.config import settings
from app.services.literature.sources.pubmed import PubMedSource
from app.services.literature.sources.crossref import CrossRefSource
from app.services.literature.sources.semantic_scholar import SemanticScholarSource
from app.services.literature.result_merger import ResultMerger


@dataclass
class SearchRequest:
    query: str
    sources: list[str]
    year_from: int | None = None
    year_to: int | None = None
    pub_types: list[str] | None = None
    max_per_source: int = 20
    language: str = "all"


@dataclass
class SourceResult:
    source: str
    results: list[dict]
    error: str | None = None
    elapsed_ms: int = 0


class SearchCoordinator:
    SOURCE_TIMEOUT = 30.0
    LANGUAGE_POLICIES = {
        "pubmed": "query_tag",
        "crossref": "metadata",
        "semantic_scholar": "heuristic",
    }

    def __init__(self):
        self.source_instances = {
            "crossref": CrossRefSource(),
        }

    async def search(
        self,
        req: SearchRequest,
        ncbi_api_key: str | None = None,
        s2_api_key: str | None = None,
    ) -> dict:
        tasks: dict[str, asyncio.Future] = {}
        for s in req.sources:
            if s == "pubmed":
                inst = PubMedSource(api_key=ncbi_api_key or getattr(settings, "ncbi_api_key", None))
                tasks[s] = self._search_with_timeout(s, inst, req)
            elif s == "semantic_scholar":
                inst = SemanticScholarSource(api_key=s2_api_key or getattr(settings, "s2_api_key", None))
                tasks[s] = self._search_with_timeout(s, inst, req)
            elif s in self.source_instances:
                tasks[s] = self._search_with_timeout(s, self.source_instances[s], req)
        if not tasks:
            return {"query": req.query, "sources": {}, "total": 0, "results": []}

        src_results_list: list[SourceResult] = await asyncio.gather(*tasks.values())
        by_source = dict(zip(tasks.keys(), src_results_list))
        merged = ResultMerger().merge({k: v.results for k, v in by_source.items()})
        return {
            "query": req.query,
            "sources": {
                s: {
                    "count": len(r.results),
                    "error": r.error,
                    "elapsed": r.elapsed_ms,
                    "language_policy": self.LANGUAGE_POLICIES.get(s, "none"),
                }
                for s, r in by_source.items()
            },
            "total": len(merged),
            "results": merged,
        }

    async def _search_with_timeout(self, source: str, instance: object, req: SearchRequest, progress_cb=None) -> SourceResult:
        start = time.perf_counter()
        try:
            results = await asyncio.wait_for(
                instance.search(
                    query=req.query,
                    year_from=req.year_from,
                    year_to=req.year_to,
                    pub_types=req.pub_types,
                    max_results=req.max_per_source,
                    language=req.language,
                    progress_cb=progress_cb,
                ),
                timeout=self.SOURCE_TIMEOUT,
            )
            return SourceResult(source=source, results=results, elapsed_ms=int((time.perf_counter() - start) * 1000))
        except asyncio.TimeoutError:
            return SourceResult(source=source, results=[], error=f"检索超时（>{self.SOURCE_TIMEOUT}s）", elapsed_ms=int(self.SOURCE_TIMEOUT * 1000))
        except Exception as e:
            return SourceResult(source=source, results=[], error=str(e)[:120], elapsed_ms=int((time.perf_counter() - start) * 1000))
