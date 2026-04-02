"""DOI / PMID 元数据拉取（CrossRef + NCBI）"""
import asyncio
from typing import Any

import httpx


class MetadataFetcher:
    """
    DOI → CrossRef API
    PMID → NCBI E-utilities API
    使用指数退避重试
    """
    CROSSREF_URL = "https://api.crossref.org/works/{doi}"
    NCBI_URL = (
        "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
        "?db=pubmed&id={pmid}&retmode=json"
    )
    HEADERS = {"User-Agent": "LinScio MedComm/1.0 (mailto:support@linscio.com)"}
    TIMEOUT = 10.0
    MAX_RETRIES = 3

    def _normalize_doi(self, doi: str) -> str:
        d = (doi or "").strip().lower()
        if d.startswith("https://doi.org/"):
            d = d[len("https://doi.org/"):]
        return d

    async def fetch_by_doi(self, doi: str) -> dict[str, Any] | None:
        doi = self._normalize_doi(doi)
        if not doi:
            return None
        url = self.CROSSREF_URL.format(doi=doi)
        last_err: Exception | None = None
        for attempt in range(self.MAX_RETRIES):
            try:
                async with httpx.AsyncClient(timeout=self.TIMEOUT) as client:
                    resp = await client.get(url, headers=self.HEADERS)
                    if resp.status_code == 404:
                        return None
                    resp.raise_for_status()
                data = resp.json().get("message", {})
                return self._parse_crossref(data)
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 404:
                    return None
                last_err = e
            except (httpx.TimeoutException, httpx.ConnectError) as e:
                last_err = e
            if attempt < self.MAX_RETRIES - 1:
                await asyncio.sleep(2**attempt)
        raise last_err  # type: ignore

    def _parse_crossref(self, msg: dict) -> dict[str, Any]:
        authors = [
            {
                "name": f"{a.get('given', '')} {a.get('family', '')}".strip(),
                "affil": (a.get("affiliation") or [{}])[0].get("name", "") if a.get("affiliation") else "",
            }
            for a in msg.get("author", [])
        ]
        journals = msg.get("container-title", []) or msg.get("short-container-title", [])
        journal = journals[0] if journals else ""
        pub_date = msg.get("published-print") or msg.get("published-online") or {}
        year = None
        parts = pub_date.get("date-parts", [[None]])
        if parts and parts[0]:
            year = parts[0][0]
        return {
            "title": (msg.get("title") or [""])[0],
            "authors": authors,
            "journal": journal,
            "year": year,
            "volume": str(msg.get("volume", "") or ""),
            "issue": str(msg.get("issue", "") or ""),
            "pages": str(msg.get("page", "") or ""),
            "doi": (msg.get("DOI") or "").lower(),
            "url": msg.get("URL", ""),
            "abstract": msg.get("abstract", ""),
            "keywords": [kw.get("value", "") for kw in msg.get("subject", [])][:10],
            "publisher": msg.get("publisher", ""),
        }

    async def fetch_by_pmid(self, pmid: str) -> dict[str, Any] | None:
        pmid = (pmid or "").strip()
        if not pmid:
            return None
        url = self.NCBI_URL.format(pmid=pmid)
        last_err: Exception | None = None
        for attempt in range(self.MAX_RETRIES):
            try:
                async with httpx.AsyncClient(timeout=self.TIMEOUT) as client:
                    resp = await client.get(url, headers=self.HEADERS)
                    resp.raise_for_status()
                result = resp.json().get("result", {})
                entry = result.get(pmid)
                if not entry or entry.get("error"):
                    return None
                return self._parse_pubmed(entry)
            except (httpx.HTTPStatusError, httpx.TimeoutException, httpx.ConnectError) as e:
                last_err = e
            if attempt < self.MAX_RETRIES - 1:
                await asyncio.sleep(2**attempt)
        raise last_err  # type: ignore

    def _parse_pubmed(self, entry: dict) -> dict[str, Any]:
        authors = [{"name": a.get("name", ""), "affil": ""} for a in entry.get("authors", [])]
        pub_date = entry.get("pubdate", "")
        year = int(pub_date[:4]) if pub_date and pub_date[:4].isdigit() else None
        doi = None
        for aid in entry.get("articleids", []):
            if aid.get("idtype") == "doi":
                doi = aid.get("value", "").lower()
                break
        return {
            "title": (entry.get("title") or "").rstrip("."),
            "authors": authors,
            "journal": entry.get("fulljournalname", "") or entry.get("source", ""),
            "year": year,
            "volume": entry.get("volume", ""),
            "issue": entry.get("issue", ""),
            "pages": entry.get("pages", ""),
            "pmid": str(entry.get("uid", "")),
            "doi": doi,
        }
