"""
文献全文解析 — 5 级瀑布式管道

优先级（从高到低）：
0. DB 已有 paper_chunks → 直接标记 full
1. 本地 PDF（用户上传）→ pypdf 解析
2. PMC OA XML（Europe PMC / NCBI EFetch）
3. Unpaywall API（根据 DOI 查合法 OA PDF）
4. Semantic Scholar open_access_url（搜索结果保存的 OA 链接）
5. DOI 直链 OA 出版商（PLOS、BMC、Frontiers 等免费 PDF）

每级失败后自动降级到下一级，全部失败才标记 no_fulltext。
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx
from sqlalchemy import func, select

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.models.literature import LiteraturePaper
from app.models.paper import PaperChunk

logger = logging.getLogger("uvicorn.error")

HEADERS = {"User-Agent": "LinScio MedComm/1.0 (mailto:support@linscio.com)"}
CONTACT_EMAIL = "support@linscio.com"

EUROPE_PMC_SEARCH = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
EUROPE_PMC_FULLTEXT = "https://www.ebi.ac.uk/europepmc/webservices/rest/PMC/{pmcid}/fullTextXML"
NCBI_ELINK = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/elink.fcgi"
NCBI_EFETCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
UNPAYWALL_API = "https://api.unpaywall.org/v2/{doi}"

_OA_PUBLISHER_DOMAINS = (
    "plos.org", "biomedcentral.com", "frontiersin.org",
    "mdpi.com", "biorxiv.org", "medrxiv.org",
    "elifesciences.org", "peerj.com", "hindawi.com",
    "jmir.org", "scielo",
)

_PDF_MAX_SIZE = 80 * 1024 * 1024  # 80 MB


# ══════════════════════════════════════════════════════════════════════
#  数据结构
# ══════════════════════════════════════════════════════════════════════

@dataclass
class ParsedPaper:
    """PMC XML 解析后的结构化论文数据"""
    abstract: str = ""
    keywords: list[str] = field(default_factory=list)
    sections: list[dict[str, str]] = field(default_factory=list)
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


# ══════════════════════════════════════════════════════════════════════
#  通用工具
# ══════════════════════════════════════════════════════════════════════

async def _http_get_with_retry(
    client: httpx.AsyncClient,
    url: str,
    *,
    params: dict | None = None,
    headers: dict | None = None,
    max_attempts: int = 2,
    label: str = "",
) -> httpx.Response:
    """带重试的 GET 请求，指数退避。"""
    last_err: Exception | None = None
    for attempt in range(max_attempts):
        try:
            r = await client.get(url, params=params, headers=headers or HEADERS)
            r.raise_for_status()
            return r
        except (httpx.HTTPStatusError, httpx.TimeoutException, httpx.ConnectError) as e:
            last_err = e
            if isinstance(e, httpx.HTTPStatusError) and e.response.status_code == 404:
                raise
            if attempt < max_attempts - 1:
                await asyncio.sleep(1.5 * (attempt + 1))
                logger.debug("[fulltext] %s attempt %d failed: %s", label, attempt + 1, e)
    raise last_err  # type: ignore[misc]


def _strip_html_tags(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text).strip()


# ══════════════════════════════════════════════════════════════════════
#  PMC XML 解析 (保留原有逻辑)
# ══════════════════════════════════════════════════════════════════════

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
    """解析 PMC JATS XML 为结构化论文"""
    result = ParsedPaper()
    if not xml_text or not xml_text.strip():
        return result
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return result

    for ab in root.iter("abstract"):
        result.abstract = _element_text(ab)
        break
    for kw_group in root.iter("kwd-group"):
        for kw in kw_group.iter("kwd"):
            t = (kw.text or "").strip()
            if t:
                result.keywords.append(t)

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
            result.sections.append({"section": title, "chunk_type": chunk_type, "text": text})

    ref_list = root.find(".//ref-list")
    if ref_list is not None:
        for ref in ref_list.findall(".//ref"):
            ref_text = _element_text(ref)
            if ref_text:
                result.references.append(ref_text)

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


# ══════════════════════════════════════════════════════════════════════
#  Level 2: PMC OA XML (Europe PMC + NCBI EFetch)
# ══════════════════════════════════════════════════════════════════════

async def _europepmc_search(client: httpx.AsyncClient, pmid: str | None, doi: str | None) -> dict | None:
    params: dict[str, Any] = {"format": "json", "resultType": "core", "pageSize": 1}
    if pmid and pmid.strip():
        params["query"] = f"EXT_ID:{pmid.strip()} AND SRC:MED"
    elif doi and doi.strip():
        d = doi.strip().replace('"', "")
        params["query"] = f'DOI:"{d}"'
    else:
        return None
    try:
        r = await _http_get_with_retry(client, EUROPE_PMC_SEARCH, params=params, label="EuropePMC-search")
        data = r.json()
        lst = (data.get("resultList") or {}).get("result") or []
        return lst[0] if lst else None
    except Exception as e:
        logger.debug("[fulltext] Europe PMC search failed: %s", e)
        return None


async def _europepmc_find_pmcid(client: httpx.AsyncClient, pmid: str | None, doi: str | None) -> str | None:
    item = await _europepmc_search(client, pmid, doi)
    if not item:
        return None
    return (item.get("pmcid") or "").strip() or None


async def _fetch_pmc_xml_europepmc(client: httpx.AsyncClient, pmcid: str) -> str:
    pid = pmcid if pmcid.upper().startswith("PMC") else f"PMC{pmcid}"
    url = EUROPE_PMC_FULLTEXT.format(pmcid=pid)
    r = await _http_get_with_retry(client, url, label="EuropePMC-xml")
    return r.text or ""


async def _ncbi_elink_pmcid(client: httpx.AsyncClient, pmid: str) -> str | None:
    params = {"dbfrom": "pubmed", "db": "pmc", "linkname": "pubmed_pmc", "id": pmid.strip(), "retmode": "json"}
    try:
        r = await _http_get_with_retry(client, NCBI_ELINK, params=params, label="NCBI-elink")
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
        logger.debug("[fulltext] NCBI elink failed: %s", e)
        return None


async def _fetch_pmc_xml_ncbi(client: httpx.AsyncClient, pmcid: str) -> str:
    pid = pmcid[3:] if pmcid.upper().startswith("PMC") else pmcid
    params = {"db": "pmc", "id": pid, "retmode": "xml"}
    r = await _http_get_with_retry(client, NCBI_EFETCH, params=params, label="NCBI-efetch")
    return r.text or ""


async def _fetch_and_parse_oa(
    client: httpx.AsyncClient, pmid: str | None, doi: str | None,
) -> tuple[ParsedPaper | None, dict | None]:
    """拉取 OA 全文 XML 并结构化解析。返回 (ParsedPaper, search_meta)"""
    pmid = (pmid or "").strip() or None
    doi = (doi or "").strip() or None
    if not pmid and not doi:
        return None, None

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
        logger.debug("[fulltext] Europe PMC fullTextXML failed %s: %s", pmcid, e)
    if not (xml_text or "").strip():
        try:
            xml_text = await _fetch_pmc_xml_ncbi(client, pmcid)
        except Exception as e:
            logger.debug("[fulltext] NCBI efetch pmc failed %s: %s", pmcid, e)

    parsed = _pmc_xml_to_sections(xml_text)
    if len(parsed.raw_text) < 400 and not parsed.sections:
        return None, search_meta
    return parsed, search_meta


async def fetch_open_access_fulltext(pmid: str | None, doi: str | None) -> str | None:
    """兼容旧接口：返回纯文本"""
    async with httpx.AsyncClient(timeout=120.0, follow_redirects=True) as client:
        parsed, _ = await _fetch_and_parse_oa(client, pmid, doi)
    if parsed and parsed.raw_text and len(parsed.raw_text) >= 400:
        return parsed.raw_text
    return None


# ══════════════════════════════════════════════════════════════════════
#  Level 3: Unpaywall API
# ══════════════════════════════════════════════════════════════════════

async def _unpaywall_find_pdf(client: httpx.AsyncClient, doi: str) -> str | None:
    """Unpaywall: 根据 DOI 查找合法 OA PDF 直链"""
    doi = (doi or "").strip()
    if not doi:
        return None
    url = UNPAYWALL_API.format(doi=doi)
    try:
        r = await _http_get_with_retry(
            client, url, params={"email": CONTACT_EMAIL}, label="Unpaywall",
        )
        data = r.json()
        best = data.get("best_oa_location") or {}
        pdf_url = best.get("url_for_pdf") or ""
        if pdf_url:
            return pdf_url
        landing = best.get("url") or ""
        if landing and _url_looks_like_pdf(landing):
            return landing
        for loc in data.get("oa_locations") or []:
            u = loc.get("url_for_pdf") or ""
            if u:
                return u
        return None
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            return None
        logger.debug("[fulltext] Unpaywall failed for %s: %s", doi, e)
        return None
    except Exception as e:
        logger.debug("[fulltext] Unpaywall failed for %s: %s", doi, e)
        return None


# ══════════════════════════════════════════════════════════════════════
#  Level 5: DOI 直链 OA 出版商解析
# ══════════════════════════════════════════════════════════════════════

def _url_looks_like_pdf(url: str) -> bool:
    return url.lower().rstrip("/").endswith(".pdf")


def _is_oa_publisher(url: str) -> bool:
    """判断 URL 是否属于已知的 OA 出版商域名"""
    try:
        host = urlparse(url).hostname or ""
    except Exception:
        return False
    host = host.lower()
    return any(domain in host for domain in _OA_PUBLISHER_DOMAINS)


async def _doi_resolve_oa_pdf(client: httpx.AsyncClient, doi: str) -> str | None:
    """通过 DOI 跳转解析 OA 出版商的 PDF 链接"""
    doi = (doi or "").strip()
    if not doi:
        return None
    doi_url = f"https://doi.org/{doi}"
    try:
        r = await client.head(doi_url, headers=HEADERS, follow_redirects=True)
        final_url = str(r.url)
    except Exception as e:
        logger.debug("[fulltext] DOI HEAD resolve failed for %s: %s", doi, e)
        return None

    if not _is_oa_publisher(final_url):
        return None

    if _url_looks_like_pdf(final_url):
        return final_url

    return _try_construct_pdf_url(final_url, doi)


def _try_construct_pdf_url(landing_url: str, doi: str) -> str | None:
    """尝试从落地页 URL 构造 PDF 直链（覆盖主流 OA 出版商模式）"""
    low = landing_url.lower()

    # PLOS: https://journals.plos.org/plosone/article?id=... → .../article/file?id=...&type=printable
    if "plos.org" in low and "/article?" in low:
        return landing_url.replace("/article?", "/article/file?") + "&type=printable"

    # Frontiers: https://www.frontiersin.org/articles/10.3389/... → .../full → .../pdf
    if "frontiersin.org" in low:
        base = landing_url.rstrip("/")
        if base.endswith("/full"):
            base = base[:-5]
        return base + "/pdf"

    # MDPI: https://www.mdpi.com/2077-0383/12/5/1234 → .../pdf
    if "mdpi.com" in low and re.search(r"/\d+/\d+/\d+", low):
        return landing_url.rstrip("/") + "/pdf"

    # bioRxiv / medRxiv: https://www.biorxiv.org/content/10.1101/... → .../content/10.1101/....full.pdf
    if "biorxiv.org" in low or "medrxiv.org" in low:
        base = landing_url.rstrip("/")
        if not base.endswith(".pdf"):
            base = re.sub(r"(v\d+)?$", "", base)
            return base + ".full.pdf"

    # PeerJ: https://peerj.com/articles/12345/ → .../articles/12345.pdf
    if "peerj.com" in low and "/articles/" in low:
        return landing_url.rstrip("/") + ".pdf"

    # eLife: https://elifesciences.org/articles/12345 → .../download/...
    if "elifesciences.org" in low and "/articles/" in low:
        return landing_url.rstrip("/") + ".pdf"

    # BMC / Nature OA: 尝试通用 .pdf 后缀
    if "biomedcentral.com" in low or "nature.com" in low:
        return landing_url.rstrip("/") + ".pdf"

    # Hindawi: https://www.hindawi.com/journals/xxx/2023/1234567/ → PDF link
    if "hindawi.com" in low:
        return landing_url.rstrip("/") + ".pdf"

    # JMIR: 一般落地页追加 /pdf 路径
    if "jmir.org" in low:
        return landing_url.rstrip("/") + "/pdf"

    return None


# ══════════════════════════════════════════════════════════════════════
#  通用 PDF 下载 + 索引管道
# ══════════════════════════════════════════════════════════════════════

async def _download_and_index_pdf(paper_id: int, pdf_url: str, source: str) -> bool:
    """下载远程 PDF → 保存到本地 → 解析并索引到 paper_chunks。

    成功返回 True，失败返回 False。
    """
    from app.services.literature.paper_indexer import parse_and_index_paper

    pdf_dir = Path(settings.app_data_root) / "literature" / "pdfs"
    pdf_dir.mkdir(parents=True, exist_ok=True)

    filename = f"{paper_id}_{source}.pdf"
    local_path = pdf_dir / filename
    rel_path = f"literature/pdfs/{filename}"

    try:
        async with httpx.AsyncClient(timeout=120.0, follow_redirects=True) as dl_client:
            r = await dl_client.get(pdf_url, headers=HEADERS)
            r.raise_for_status()
            content_type = (r.headers.get("content-type") or "").lower()
            if len(r.content) < 1000:
                logger.info("[fulltext] PDF too small (%d bytes) from %s", len(r.content), source)
                return False
            if len(r.content) > _PDF_MAX_SIZE:
                logger.info("[fulltext] PDF too large (%d bytes) from %s", len(r.content), source)
                return False
            if "html" in content_type and b"%PDF" not in r.content[:20]:
                logger.info("[fulltext] Got HTML instead of PDF from %s: %s", source, pdf_url[:120])
                return False
    except Exception as e:
        logger.info("[fulltext] PDF download failed from %s: %s", source, e)
        return False

    logger.info(
        "[fulltext] paper %d: downloaded %d bytes from %s (content-type=%s)",
        paper_id, len(r.content), source, content_type[:60],
    )
    local_path.write_bytes(r.content)

    try:
        async with AsyncSessionLocal() as db:
            count, status = await parse_and_index_paper(paper_id, rel_path, db)
    except Exception as e:
        logger.info("[fulltext] paper %d: parse_and_index failed from %s: %s", paper_id, source, e)
        local_path.unlink(missing_ok=True)
        return False

    if count > 0 and status == "done":
        async with AsyncSessionLocal() as db:
            p = await db.get(LiteraturePaper, paper_id)
            if p:
                p.pdf_path = rel_path
                p.fulltext_status = "full"
                p.pdf_indexed = 1
                await db.commit()
        logger.info("[fulltext] paper %d: PDF indexed via %s (%d chunks)", paper_id, source, count)
        return True

    logger.info("[fulltext] paper %d: PDF from %s parsed but got %d chunks (status=%s)", paper_id, source, count, status)
    local_path.unlink(missing_ok=True)
    return False


# ══════════════════════════════════════════════════════════════════════
#  元数据回填
# ══════════════════════════════════════════════════════════════════════

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


# ══════════════════════════════════════════════════════════════════════
#  5 级瀑布式管道
# ══════════════════════════════════════════════════════════════════════

async def _mark_fulltext(paper_id: int, status: str, indexed: int = 0) -> None:
    async with AsyncSessionLocal() as db:
        p = await db.get(LiteraturePaper, paper_id)
        if p:
            p.fulltext_status = status
            p.pdf_indexed = indexed
            await db.commit()


async def resolve_fulltext_for_paper(paper_id: int) -> None:
    """
    5 级瀑布式全文获取管道。
    Level 0: DB 已有 chunks → full
    Level 1: 本地 PDF → pypdf 解析
    Level 2: PMC OA XML
    Level 3: Unpaywall API → 下载 PDF
    Level 4: paper.open_access_url (S2 等来源)
    Level 5: DOI 直链 OA 出版商
    """
    from app.services.literature.paper_indexer import (
        index_structured_fulltext_for_paper,
        parse_and_index_paper,
    )

    # ── Level 0: 已有 chunks ──────────────────────────────────────
    async with AsyncSessionLocal() as db:
        n_existing = await db.scalar(
            select(func.count()).select_from(PaperChunk).where(PaperChunk.paper_id == paper_id)
        )
    if (n_existing or 0) > 0:
        await _mark_fulltext(paper_id, "full", 1)
        logger.info("[fulltext] paper %d: already has %d chunks", paper_id, n_existing)
        return

    # 加载 paper 元数据
    async with AsyncSessionLocal() as db:
        paper = await db.get(LiteraturePaper, paper_id)
        if not paper:
            return
        pdf_path = (paper.pdf_path or "").strip()
        pmid = (paper.pmid or "").strip() or None
        doi = (paper.doi or "").strip() or None
        oa_url = (getattr(paper, "open_access_url", None) or "").strip() or None

    # ── Level 1: 本地 PDF ─────────────────────────────────────────
    if pdf_path:
        full_path = Path(settings.app_data_root) / pdf_path.lstrip("/")
        if full_path.exists():
            async with AsyncSessionLocal() as db:
                count, status = await parse_and_index_paper(paper_id, pdf_path, db)
            if count > 0 and status == "done":
                await _mark_fulltext(paper_id, "full", 1)
                logger.info("[fulltext] paper %d: indexed from local PDF (%d chunks)", paper_id, count)
                return

    if not pmid and not doi:
        await _mark_fulltext(paper_id, "no_fulltext", 0)
        logger.info("[fulltext] paper %d: no PMID/DOI, cannot resolve", paper_id)
        return

    async with httpx.AsyncClient(timeout=120.0, follow_redirects=True) as client:

        # ── Level 2: PMC OA XML ──────────────────────────────────
        logger.info("[fulltext] paper %d: trying PMC OA (pmid=%s, doi=%s)", paper_id, pmid, doi)
        parsed, search_meta = await _fetch_and_parse_oa(client, pmid, doi)
        await _backfill_paper_meta(paper_id, parsed, search_meta)

        if parsed and (parsed.sections or len(parsed.raw_text) >= 400):
            async with AsyncSessionLocal() as db:
                n, st = await index_structured_fulltext_for_paper(paper_id, parsed, db)
            if n > 0 and st == "done":
                await _mark_fulltext(paper_id, "full", 1)
                logger.info("[fulltext] paper %d: indexed from PMC OA XML (%d chunks)", paper_id, n)
                return

        # ── Level 3: Unpaywall ────────────────────────────────────
        if doi:
            logger.info("[fulltext] paper %d: trying Unpaywall (doi=%s)", paper_id, doi)
            unpaywall_url = await _unpaywall_find_pdf(client, doi)
            if unpaywall_url:
                logger.info("[fulltext] paper %d: Unpaywall found PDF: %s", paper_id, unpaywall_url)
                if await _download_and_index_pdf(paper_id, unpaywall_url, "unpaywall"):
                    return

        # ── Level 4: Semantic Scholar open_access_url ─────────────
        if oa_url:
            logger.info("[fulltext] paper %d: trying S2 OA URL: %s", paper_id, oa_url)
            if await _download_and_index_pdf(paper_id, oa_url, "s2_oa"):
                return

        # ── Level 5: DOI 直链 OA 出版商 ──────────────────────────
        if doi:
            logger.info("[fulltext] paper %d: trying DOI direct resolve (doi=%s)", paper_id, doi)
            direct_url = await _doi_resolve_oa_pdf(client, doi)
            if direct_url:
                logger.info("[fulltext] paper %d: DOI resolved to OA PDF: %s", paper_id, direct_url)
                if await _download_and_index_pdf(paper_id, direct_url, "doi_oa"):
                    return

    # ── 全部失败 ──────────────────────────────────────────────────
    await _mark_fulltext(paper_id, "no_fulltext", 0)
    logger.info("[fulltext] paper %d: all levels exhausted, marked no_fulltext", paper_id)


async def resolve_fulltext_batch(paper_ids: list[int]) -> None:
    for pid in paper_ids:
        try:
            await resolve_fulltext_for_paper(pid)
        except Exception as e:
            logger.warning("[fulltext] resolve_fulltext_for_paper(%s) failed: %s", pid, e)
