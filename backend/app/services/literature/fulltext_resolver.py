"""
文献全文解析：PDF 已有索引优先；否则尝试开放获取全文（Europe PMC / NCBI PMC）并写入 paper_chunks。
摘要 alone 不计入「全文」；产品要求见 literature_papers.fulltext_status。
"""
from __future__ import annotations

import json
import logging
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx
from sqlalchemy import func, select

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.models.literature import LiteraturePaper
from app.models.paper import PaperChunk

logger = logging.getLogger(__name__)

HEADERS = {"User-Agent": "LinScio MedComm/1.0 (mailto:support@linscio.com)"}
EUROPE_PMC_SEARCH = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
EUROPE_PMC_FULLTEXT = "https://www.ebi.ac.uk/europepmc/webservices/rest/PMC/{pmcid}/fullTextXML"
NCBI_ELINK = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/elink.fcgi"
NCBI_EFETCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"


@dataclass
class ParsedPaper:
    """PMC XML 解析后的结构化论文数据"""
    abstract: str = ""
    keywords: list[str] = field(default_factory=list)
    sections: list[dict[str, str]] = field(default_factory=list)  # [{section, chunk_type, text}]
    references: list[str] = field(default_factory=list)
    raw_text: str = ""


_SECTION_TYPE_MAP = {
    "introduction": "introduction",
    "background": "background",
    "method": "methods",
    "materials": "methods",
    "experimental": "methods",
    "result": "results",
    "finding": "results",
    "discussion": "discussion",
    "conclusion": "conclusion",
    "summary": "conclusion",
    "limitation": "discussion",
    "reference": "references",
    "bibliography": "references",
    "supplementary": "supplementary",
    "appendix": "supplementary",
    "acknowledgment": "supplementary",
    "acknowledgement": "supplementary",
    "funding": "supplementary",
    "declaration": "supplementary",
    "conflict": "supplementary",
    "author contribution": "supplementary",
}


def _infer_section_type(title: str) -> str:
    low = title.lower().strip()
    for keyword, stype in _SECTION_TYPE_MAP.items():
        if keyword in low:
            return stype
    return "body"


def _element_text(el: ET.Element) -> str:
    parts = []
    for t in el.itertext():
        s = (t or "").strip()
        if s:
            parts.append(s)
    return re.sub(r"\s+", " ", " ".join(parts)).strip()


def _pmc_xml_to_sections(xml_text: str) -> ParsedPaper:
    """解析 PMC JATS XML 为结构化论文：abstract、keywords、分段正文、references"""
    result = ParsedPaper()
    if not xml_text or not xml_text.strip():
        return result

    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return result

    # Abstract
    for ab in root.iter("abstract"):
        result.abstract = _element_text(ab)
        break

    # Keywords
    for kw_group in root.iter("kwd-group"):
        for kw in kw_group.iter("kwd"):
            t = (kw.text or "").strip()
            if t:
                result.keywords.append(t)

    # Body sections
    body = root.find(".//body")
    if body is not None:
        for sec in body.findall("sec"):
            title_el = sec.find("title")
            title = (title_el.text or "").strip() if title_el is not None else ""
            text = _element_text(sec)
            if title and text.startswith(title):
                text = text[len(title):].strip()
            if not text:
                continue
            chunk_type = _infer_section_type(title) if title else "body"
            result.sections.append({
                "section": title,
                "chunk_type": chunk_type,
                "text": text,
            })

    # References
    ref_list = root.find(".//ref-list")
    if ref_list is not None:
        for ref in ref_list.findall(".//ref"):
            ref_text = _element_text(ref)
            if ref_text:
                result.references.append(ref_text)

    # raw_text fallback (all text)
    all_parts = []
    for t in root.itertext():
        s = (t or "").strip()
        if s:
            all_parts.append(s)
    result.raw_text = re.sub(r"\s+", " ", " ".join(all_parts)).strip()

    return result


def _pmc_xml_to_plain(xml_text: str) -> str:
    """兼容旧调用：返回纯文本"""
    parsed = _pmc_xml_to_sections(xml_text)
    return parsed.raw_text


async def _europepmc_search(client: httpx.AsyncClient, pmid: str | None, doi: str | None) -> dict | None:
    """Europe PMC search，返回第一条完整结果 dict（含 abstractText, keywordList 等）"""
    params: dict[str, Any] = {"format": "json", "resultType": "core", "pageSize": 1}
    if pmid and pmid.strip():
        params["query"] = f"EXT_ID:{pmid.strip()} AND SRC:MED"
    elif doi and doi.strip():
        d = doi.strip().replace('"', "")
        params["query"] = f'DOI:"{d}"'
    else:
        return None
    try:
        r = await client.get(EUROPE_PMC_SEARCH, params=params, headers=HEADERS)
        r.raise_for_status()
        data = r.json()
        lst = (data.get("resultList") or {}).get("result") or []
        return lst[0] if lst else None
    except Exception as e:
        logger.debug("Europe PMC search failed: %s", e)
        return None


async def _europepmc_find_pmcid(client: httpx.AsyncClient, pmid: str | None, doi: str | None) -> str | None:
    item = await _europepmc_search(client, pmid, doi)
    if not item:
        return None
    return (item.get("pmcid") or "").strip() or None


async def _fetch_pmc_xml_europepmc(client: httpx.AsyncClient, pmcid: str) -> str:
    pid = pmcid if pmcid.upper().startswith("PMC") else f"PMC{pmcid}"
    url = EUROPE_PMC_FULLTEXT.format(pmcid=pid)
    r = await client.get(url, headers=HEADERS)
    r.raise_for_status()
    return r.text or ""


async def _ncbi_elink_pmcid(client: httpx.AsyncClient, pmid: str) -> str | None:
    params = {
        "dbfrom": "pubmed",
        "db": "pmc",
        "linkname": "pubmed_pmc",
        "id": pmid.strip(),
        "retmode": "json",
    }
    try:
        r = await client.get(NCBI_ELINK, params=params, headers=HEADERS)
        r.raise_for_status()
        data = r.json()
        for ls in data.get("linksets") or []:
            for ldb in ls.get("linksetdbs") or []:
                if ldb.get("dbto") == "pmc":
                    links = ldb.get("links") or []
                    if links:
                        lid = str(links[0])
                        return f"PMC{lid}" if not lid.upper().startswith("PMC") else lid
        return None
    except Exception as e:
        logger.debug("NCBI elink failed: %s", e)
        return None


async def _fetch_pmc_xml_ncbi(client: httpx.AsyncClient, pmcid: str) -> str:
    pid = pmcid[3:] if pmcid.upper().startswith("PMC") else pmcid
    params = {"db": "pmc", "id": pid, "retmode": "xml"}
    r = await client.get(NCBI_EFETCH, params=params, headers=HEADERS)
    r.raise_for_status()
    return r.text or ""


async def _fetch_and_parse_oa(pmid: str | None, doi: str | None) -> tuple[ParsedPaper | None, dict | None]:
    """拉取 OA 全文 XML 并结构化解析。返回 (ParsedPaper, search_meta)"""
    pmid = (pmid or "").strip() or None
    doi = (doi or "").strip() or None
    if not pmid and not doi:
        return None, None

    async with httpx.AsyncClient(timeout=120.0, follow_redirects=True) as client:
        search_meta = await _europepmc_search(client, pmid, doi)
        pmcid = (search_meta.get("pmcid") or "").strip() if search_meta else None
        if not pmcid and pmid:
            pmcid = await _ncbi_elink_pmcid(client, pmid)
        if not pmcid:
            return None, search_meta

        xml_text = ""
        try:
            xml_text = await _fetch_pmc_xml_europepmc(client, pmcid)
        except Exception as e:
            logger.debug("Europe PMC fullTextXML failed %s: %s", pmcid, e)
        if not (xml_text or "").strip():
            try:
                xml_text = await _fetch_pmc_xml_ncbi(client, pmcid)
            except Exception as e:
                logger.debug("NCBI efetch pmc failed %s: %s", pmcid, e)

        parsed = _pmc_xml_to_sections(xml_text)
        if len(parsed.raw_text) < 400 and not parsed.sections:
            return None, search_meta
        return parsed, search_meta


async def fetch_open_access_fulltext(pmid: str | None, doi: str | None) -> str | None:
    """兼容旧接口：返回纯文本"""
    parsed, _ = await _fetch_and_parse_oa(pmid, doi)
    if parsed and parsed.raw_text and len(parsed.raw_text) >= 400:
        return parsed.raw_text
    return None


def _strip_html_tags(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text).strip()


async def _backfill_paper_meta(paper_id: int, parsed: ParsedPaper | None, search_meta: dict | None) -> None:
    """用解析结果回填 paper 的 abstract / keywords（仅在原值为空时）"""
    abstract = ""
    keywords: list[str] = []

    if parsed:
        abstract = parsed.abstract
        keywords = parsed.keywords

    if search_meta and not abstract:
        abstract = _strip_html_tags(search_meta.get("abstractText") or "")

    if search_meta and not keywords:
        kw_list = (search_meta.get("keywordList") or {}).get("keyword") or []
        keywords = [str(k).strip() for k in kw_list if str(k).strip()]

    if not abstract and not keywords:
        return

    async with AsyncSessionLocal() as db:
        p = await db.get(LiteraturePaper, paper_id)
        if not p:
            return
        if abstract and not (p.abstract or "").strip():
            p.abstract = abstract
        if keywords:
            existing = []
            try:
                existing = json.loads(p.keywords or "[]")
            except (json.JSONDecodeError, TypeError):
                pass
            if not existing:
                p.keywords = json.dumps(keywords, ensure_ascii=False)
        await db.commit()


async def resolve_fulltext_for_paper(paper_id: int) -> None:
    """
    统一全文入口：若已有 chunk 则标记 full；否则尝试 PDF 再尝试 OA。
    OA 路径会结构化解析 XML，回填 abstract/keywords 并按论文章节存储 chunks。
    """
    from app.services.literature.paper_indexer import (
        index_structured_fulltext_for_paper,
        parse_and_index_paper,
    )

    async with AsyncSessionLocal() as db:
        n_existing = await db.scalar(
            select(func.count()).select_from(PaperChunk).where(PaperChunk.paper_id == paper_id)
        )
    if (n_existing or 0) > 0:
        async with AsyncSessionLocal() as db:
            p = await db.get(LiteraturePaper, paper_id)
            if p:
                p.fulltext_status = "full"
                p.pdf_indexed = 1
                await db.commit()
        return

    async with AsyncSessionLocal() as db:
        paper = await db.get(LiteraturePaper, paper_id)
        if not paper:
            return
        pdf_path = (paper.pdf_path or "").strip()

    if pdf_path:
        full_path = Path(settings.app_data_root) / pdf_path.lstrip("/")
        if full_path.exists():
            async with AsyncSessionLocal() as db:
                count, status = await parse_and_index_paper(paper_id, pdf_path, db)
            if count > 0 and status == "done":
                async with AsyncSessionLocal() as db:
                    p = await db.get(LiteraturePaper, paper_id)
                    if p:
                        p.fulltext_status = "full"
                        p.pdf_indexed = 1
                        await db.commit()
                return

    async with AsyncSessionLocal() as db:
        paper = await db.get(LiteraturePaper, paper_id)
        if not paper:
            return
        pmid = (paper.pmid or "").strip() or None
        doi = (paper.doi or "").strip() or None

    parsed, search_meta = await _fetch_and_parse_oa(pmid, doi)

    await _backfill_paper_meta(paper_id, parsed, search_meta)

    if parsed and (parsed.sections or len(parsed.raw_text) >= 400):
        async with AsyncSessionLocal() as db:
            n, st = await index_structured_fulltext_for_paper(paper_id, parsed, db)
        if n > 0 and st == "done":
            async with AsyncSessionLocal() as db:
                p = await db.get(LiteraturePaper, paper_id)
                if p:
                    p.fulltext_status = "full"
                    p.pdf_indexed = 1
                    await db.commit()
            return

    async with AsyncSessionLocal() as db:
        p = await db.get(LiteraturePaper, paper_id)
        if p:
            p.fulltext_status = "no_fulltext"
            p.pdf_indexed = 0
            await db.commit()


async def resolve_fulltext_batch(paper_ids: list[int]) -> None:
    for pid in paper_ids:
        try:
            await resolve_fulltext_for_paper(pid)
        except Exception as e:
            logger.warning("resolve_fulltext_for_paper(%s) failed: %s", pid, e)
