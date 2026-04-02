"""CrossRef source."""
from __future__ import annotations

import httpx


class CrossRefSource:
    SEARCH_URL = "https://api.crossref.org/works"
    HEADERS = {
        "User-Agent": "LinScio MedComm/1.0 (mailto:support@linscio.com)",
    }

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
            await progress_cb("请求 CrossRef", 35)
        params = {
            "query": query,
            "rows": max_results,
            # CrossRef 支持 sort=score（relevance 可能导致 400）
            "sort": "score",
            "select": (
                "DOI,title,author,published-print,published-online,"
                "container-title,volume,issue,page,abstract,type,URL,language"
            ),
        }
        if year_from:
            params["filter"] = f"from-pub-date:{year_from}"
        if year_to:
            ex = params.get("filter", "")
            params["filter"] = (ex + "," if ex else "") + f"until-pub-date:{year_to}"

        async with httpx.AsyncClient(timeout=12.0, headers=self.HEADERS) as client:
            # CrossRef 对部分参数组合（sort/select）不稳定，这里做多级兜底重试
            last_err: Exception | None = None
            for attempt in range(3):
                try:
                    resp = await client.get(self.SEARCH_URL, params=params)
                    resp.raise_for_status()
                    items = resp.json().get("message", {}).get("items", [])
                    break
                except httpx.HTTPStatusError as e:
                    last_err = e
                    if e.response is not None and e.response.status_code == 400:
                        if params.get("sort"):
                            params.pop("sort", None)
                            continue
                        if params.get("select"):
                            params.pop("select", None)
                            continue
                    raise
            else:
                if last_err:
                    raise last_err
                items = []
        if progress_cb:
            await progress_cb("解析结果", 75)
        parsed = [self._parse_item(item) for item in items]
        if language == "all":
            return parsed
        return [p for p in parsed if self._match_language(p.get("language", ""), language)]

    def _parse_item(self, item: dict) -> dict:
        titles = item.get("title", [])
        title = titles[0] if titles else ""
        authors = []
        for a in item.get("author", []):
            name = f"{a.get('given', '')} {a.get('family', '')}".strip()
            aff = (a.get("affiliation", [{}])[0] or {}).get("name", "") if a.get("affiliation") else ""
            authors.append({"name": name, "affil": aff})
        pub_date = item.get("published-print") or item.get("published-online") or {}
        year = (pub_date.get("date-parts") or [[None]])[0][0]
        journals = item.get("container-title", []) or item.get("short-container-title", [])
        return {
            "source": "crossref",
            "source_id": (item.get("DOI") or "").lower(),
            "title": title,
            "authors": authors,
            "journal": journals[0] if journals else "",
            "year": year,
            "volume": item.get("volume", ""),
            "issue": item.get("issue", ""),
            "pages": item.get("page", ""),
            "doi": (item.get("DOI") or "").lower(),
            "url": item.get("URL", ""),
            "abstract": item.get("abstract", ""),
            "pub_types": [item.get("type", "")],
            "language": (item.get("language", "") or "").lower(),
        }

    def _match_language(self, value: str, target: str) -> bool:
        lang = (value or "").lower().strip()
        if not lang:
            # 无语言元数据时保守放行，避免误伤召回
            return True
        if target == "en":
            return lang.startswith("en")
        if target == "zh":
            return lang.startswith("zh")
        return True
