"""文献支撑库 API"""
import json
import time
import uuid
import asyncio
import logging
from datetime import datetime
from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile, Query, Request
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, delete, update, insert, text
from sqlalchemy.exc import IntegrityError
from pydantic import BaseModel, Field, field_validator
import os
import shutil
from pathlib import Path
from typing import Literal

import httpx

from app.core.database import AsyncSessionLocal, get_domain_lock
from app.models.paper import PaperChunk
from app.models.literature import (
    LiteraturePaper, LiteraturePaperTag, LiteratureTag, LiteratureCollection,
    LiteratureAttachment, LiteratureAnnotation,
)
from app.models.article import Article, ArticleSection, ArticleLiteratureBinding, ArticleExternalReference
from app.core.config import settings
from app.services.literature.dedup import DuplicateChecker
from app.services.literature.query_builder import PaperQueryBuilder
from app.services.literature.citation_formatter import CitationFormatter
from app.services.literature.search_coordinator import SearchCoordinator, SearchRequest
from app.services.literature.result_merger import annotate_with_local_status, ResultMerger
from app.services.literature.fulltext_resolver import resolve_fulltext_batch, resolve_fulltext_for_paper

router = APIRouter()
logger = logging.getLogger("linscio.medcomm.literature")

UPLOAD_DIR = Path(settings.app_data_root) / "uploads" / "papers"
ATTACHMENTS_DIR = Path(settings.app_data_root) / "uploads" / "literature_attachments"
IMPORT_ASYNC_THRESHOLD = 50
_import_tasks: dict[str, dict] = {}
ReadStatusLiteral = Literal["unread", "reading", "read"]
_search_coordinator = SearchCoordinator()
_search_cache_last_cleanup_ts = 0.0


async def _ensure_search_tables(db: AsyncSession) -> None:
    await db.execute(text("""
        CREATE TABLE IF NOT EXISTS literature_search_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL DEFAULT 1,
            query TEXT NOT NULL,
            sources TEXT NOT NULL DEFAULT '[]',
            filters TEXT NOT NULL DEFAULT '{}',
            result_count INTEGER DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """))
    await db.execute(text("""
        CREATE TABLE IF NOT EXISTS literature_search_cache (
            cache_key TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL DEFAULT 1,
            result_json TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            expires_at DATETIME NOT NULL
        )
    """))
    # 向后兼容：老库补充 user_id 字段
    hist_cols = (await db.execute(text("PRAGMA table_info(literature_search_history)"))).fetchall()
    if not any((c[1] == "user_id") for c in hist_cols):
        await db.execute(text("ALTER TABLE literature_search_history ADD COLUMN user_id INTEGER NOT NULL DEFAULT 1"))
    cache_cols = (await db.execute(text("PRAGMA table_info(literature_search_cache)"))).fetchall()
    if not any((c[1] == "user_id") for c in cache_cols):
        await db.execute(text("ALTER TABLE literature_search_cache ADD COLUMN user_id INTEGER NOT NULL DEFAULT 1"))
    await db.execute(text("CREATE INDEX IF NOT EXISTS idx_search_cache_expires ON literature_search_cache(expires_at)"))
    await db.execute(text("CREATE INDEX IF NOT EXISTS idx_search_cache_user_expires ON literature_search_cache(user_id, expires_at)"))
    await db.execute(text("CREATE INDEX IF NOT EXISTS idx_search_history_user_id ON literature_search_history(user_id, id DESC)"))
    await db.commit()


def _make_search_cache_key(req: "ExternalSearchRequest", user_id: int) -> str:
    import hashlib
    payload = {
        "user_id": int(user_id or 0),
        "q": (req.query or "").strip().lower(),
        "sources": sorted(req.sources or []),
        "year_from": req.year_from,
        "year_to": req.year_to,
        "pub_types": sorted(req.pub_types or []),
        "language": req.language,
        "max": req.max_per_source,
    }
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


async def _cleanup_expired_search_cache(db: AsyncSession) -> int:
    """清理过期检索缓存。"""
    result = await db.execute(
        text("DELETE FROM literature_search_cache WHERE expires_at <= CURRENT_TIMESTAMP")
    )
    await db.commit()
    return int(result.rowcount or 0)


def _safe_filename(name: str) -> str:
    """保留字母数字、点、横线、下划线"""
    if not name:
        return "unnamed"
    safe = "".join(c for c in name if c.isalnum() or c in "._-")
    return safe[:200] or "unnamed"


# --- Request/Response Models ---

class AuthorItem(BaseModel):
    name: str = ""
    affil: str = ""


class PaperCreateRequest(BaseModel):
    title: str
    authors: list[AuthorItem] = []
    journal: str = ""
    year: int | None = None
    volume: str = ""
    issue: str = ""
    pages: str = ""
    doi: str | None = None
    pmid: str | None = None
    url: str = ""
    abstract: str = ""
    keywords: list[str] = []
    language: str = "zh"
    read_status: ReadStatusLiteral = "unread"
    collection_id: int | None = None
    tag_ids: list[int] = []

    @field_validator("doi", mode="before")
    @classmethod
    def normalize_doi(cls, v):
        if not v:
            return None
        v = str(v).strip().lower()
        if v.startswith("https://doi.org/"):
            v = v[len("https://doi.org/"):]
        return v or None


class PaperUpdateRequest(BaseModel):
    title: str | None = None
    authors: list[AuthorItem] | None = None
    journal: str | None = None
    year: int | None = None
    volume: str | None = None
    issue: str | None = None
    pages: str | None = None
    doi: str | None = None
    pmid: str | None = None
    url: str | None = None
    abstract: str | None = None
    keywords: list[str] | None = None
    user_notes: str | None = None
    read_status: ReadStatusLiteral | None = None
    collection_id: int | None = None
    tag_ids: list[int] | None = None


class DupCheckRequest(BaseModel):
    doi: str | None = None
    pmid: str | None = None
    title: str = ""
    authors: list[AuthorItem] = []
    year: int | None = None


class FetchMetadataRequest(BaseModel):
    doi: str | None = None
    pmid: str | None = None


class BrowserCaptureRequest(BaseModel):
    title: str
    url: str
    doi: str | None = None
    abstract: str | None = None
    selected_text: str | None = None


class CollectionCreateRequest(BaseModel):
    name: str
    parent_id: int | None = None
    color: str = "#185FA5"
    icon: str = "folder"
    sort_order: int = 0


class TagCreateRequest(BaseModel):
    name: str
    color: str = "#1D9E75"


class TagUpdateRequest(BaseModel):
    name: str | None = None
    color: str | None = None


class CollectionUpdateRequest(BaseModel):
    name: str | None = None
    parent_id: int | None = None
    color: str | None = None
    icon: str | None = None
    sort_order: int | None = None


class ExportBatchRequest(BaseModel):
    ids: list[int] = Field(..., min_length=1)
    format: Literal["apa", "bibtex", "nlm", "gbt7714"] = "apa"


class UpdateTagsRequest(BaseModel):
    tag_ids: list[int] = []


class BatchOperationRequest(BaseModel):
    operation: Literal["tag", "move", "delete", "read_status", "restore", "permanent"]
    paper_ids: list[int]
    payload: dict = {}


class BatchOperationResponse(BaseModel):
    success: bool = True
    affected: int = 0


class ExternalSearchRequest(BaseModel):
    query: str
    sources: list[Literal["pubmed", "crossref", "semantic_scholar"]] = Field(default_factory=lambda: ["pubmed", "crossref"])
    year_from: int | None = None
    year_to: int | None = None
    pub_types: list[str] | None = None
    max_per_source: int = 20
    language: Literal["all", "en", "zh"] = "all"


class SearchResultItem(BaseModel):
    source: str
    source_id: str = ""
    title: str
    authors: list[AuthorItem] = Field(default_factory=list)
    journal: str = ""
    year: int | None = None
    volume: str = ""
    issue: str = ""
    pages: str = ""
    doi: str | None = None
    pmid: str | None = None
    url: str = ""
    abstract: str = ""
    pub_types: list[str] = Field(default_factory=list)
    cite_count: int = 0
    open_access_url: str = ""

    @field_validator("doi", "pmid", mode="before")
    @classmethod
    def _normalize_ids(cls, v):
        if v is None or v == "":
            return None
        s = str(v).strip()
        return s or None


class SaveSearchResultRequest(BaseModel):
    items: list[SearchResultItem] = Field(default_factory=list)
    collection_id: int | None = None
    tag_ids: list[int] = Field(default_factory=list)


class ExternalRefItem(BaseModel):
    source: str
    source_id: str = ""
    doi: str | None = None
    pmid: str | None = None
    title: str
    authors: list[AuthorItem] = Field(default_factory=list)
    journal: str = ""
    year: int | None = None
    url: str = ""
    abstract: str = ""


class BindExternalRefsRequest(BaseModel):
    items: list[ExternalRefItem] = Field(default_factory=list)
    section_id: int | None = None


class ReadStatusRequest(BaseModel):
    status: ReadStatusLiteral


class ReadStatusResponse(BaseModel):
    read_status: ReadStatusLiteral


class PaperListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[dict]


class CollectionResponse(BaseModel):
    id: int
    name: str
    parent_id: int | None = None
    color: str
    icon: str


class CollectionTreeItem(BaseModel):
    id: int
    name: str
    parent_id: int | None = None
    color: str
    icon: str
    sort_order: int
    count: int
    children: list[dict] = Field(default_factory=list)


class TagResponse(BaseModel):
    id: int
    name: str
    color: str


class TagListItemResponse(BaseModel):
    id: int
    name: str
    color: str
    paper_count: int


class PaperResponse(BaseModel):
    id: int
    title: str
    authors: list[dict]
    journal: str
    year: int | None = None
    doi: str | None = None
    pmid: str | None = None
    abstract: str
    keywords: list[str]
    pdf_path: str | None = None
    pdf_indexed: int
    fulltext_status: str = "pending"
    read_status: ReadStatusLiteral | str | None = None
    collection_id: int | None = None
    created_at: str | None = None
    deleted_at: str | None = None


class AttachmentResponse(BaseModel):
    id: int
    filename: str
    file_type: str
    file_size: int
    description: str = ""
    created_at: str | None = None


class AttachmentListResponse(BaseModel):
    items: list[AttachmentResponse]


class TagSimpleResponse(BaseModel):
    id: int
    name: str
    color: str


class PaperDetailResponse(PaperResponse):
    tags: list[TagSimpleResponse] = Field(default_factory=list)
    collection: CollectionResponse | None = None
    attachments: list[AttachmentResponse] = Field(default_factory=list)
    annotation_count: int = 0


class CitationExportResponse(BaseModel):
    format: Literal["apa", "bibtex", "nlm", "gbt7714"]
    citation: str


class TagSuggestResponse(BaseModel):
    existing_tags: list[dict]
    new_tag_suggestions: list[str]


class ErrorResponse(BaseModel):
    detail: str


class AnnotationResponse(BaseModel):
    id: int
    annotation_type: Literal["highlight", "note", "underline", "strikethrough"]
    page_number: int
    rect: dict | str
    color: str
    content: str
    selected_text: str


class AnnotationListResponse(BaseModel):
    items: list[AnnotationResponse]


class RectPayload(BaseModel):
    x1: float
    y1: float
    x2: float
    y2: float


class AnnotationCreateRequest(BaseModel):
    annotation_type: Literal["highlight", "note", "underline", "strikethrough"]
    page_number: int
    rect: RectPayload | str  # JSON {x1,y1,x2,y2}
    color: str = "#FFD700"
    content: str = ""
    selected_text: str = ""


class AnnotationUpdateRequest(BaseModel):
    annotation_type: Literal["highlight", "note", "underline", "strikethrough"] | None = None
    page_number: int | None = None
    rect: RectPayload | str | None = None
    color: str | None = None
    content: str | None = None
    selected_text: str | None = None


class BindPapersRequest(BaseModel):
    paper_ids: list[int]
    section_id: int | None = None
    priority: int = 100


async def _sync_tags(db: AsyncSession, paper_id: int, tag_ids: list[int]) -> None:
    from sqlalchemy import delete
    await db.execute(delete(LiteraturePaperTag).where(LiteraturePaperTag.paper_id == paper_id))
    for tag_id in tag_ids:
        db.add(LiteraturePaperTag(paper_id=paper_id, tag_id=tag_id))


async def _validate_collection_exists(db: AsyncSession, collection_id: int | None) -> None:
    if collection_id is None:
        return
    result = await db.execute(
        select(LiteratureCollection.id).where(LiteratureCollection.id == collection_id)
    )
    if not result.first():
        raise HTTPException(status_code=400, detail=f"集合不存在: {collection_id}")


async def _validate_tag_ids_exist(db: AsyncSession, tag_ids: list[int]) -> None:
    if not tag_ids:
        return
    ids = list(set(tag_ids))
    result = await db.execute(select(LiteratureTag.id).where(LiteratureTag.id.in_(ids)))
    existing_ids = {r[0] for r in result.fetchall()}
    missing = [i for i in ids if i not in existing_ids]
    if missing:
        raise HTTPException(status_code=400, detail=f"标签不存在: {', '.join(str(i) for i in missing)}")


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session


async def _index_paper_task(paper_id: int, file_path: str):
    from app.services.literature.paper_indexer import parse_and_index_paper

    try:
        async with AsyncSessionLocal() as db:
            await parse_and_index_paper(paper_id, file_path, db)
    except Exception as e:
        logger.warning("parse_and_index_paper failed paper_id=%s: %s", paper_id, e)
    await resolve_fulltext_for_paper(paper_id)


async def _index_attachment_task(att_id: int):
    from app.services.literature.paper_indexer import parse_and_index_paper

    paper_id: int | None = None
    try:
        async with AsyncSessionLocal() as db:
            att_result = await db.execute(
                select(LiteratureAttachment).where(LiteratureAttachment.id == att_id)
            )
            att = att_result.scalar_one_or_none()
            if not att:
                return
            paper_id = att.paper_id
            await parse_and_index_paper(paper_id, att.file_path, db)
    except Exception as e:
        logger.warning("parse_and_index attachment att_id=%s: %s", att_id, e)
    if paper_id is not None:
        await resolve_fulltext_for_paper(paper_id)


async def _bulk_import_records(
    papers_data: list[dict],
    source: str,
) -> dict:
    """批量入库，返回统计及失败明细。"""
    success, skipped, failed = 0, 0, 0
    paper_ids: list[int] = []
    errors: list[dict] = []
    async with AsyncSessionLocal() as db:
        for idx, pd in enumerate(papers_data, start=1):
            authors = pd.get("authors", [])
            title = pd.get("title", "未命名")
            try:
                dup = await DuplicateChecker(db).check(
                    doi=pd.get("doi"),
                    title=title,
                    authors=authors,
                    year=pd.get("year"),
                    pmid=pd.get("pmid"),
                )
                if dup.exact_match:
                    skipped += 1
                    errors.append({
                        "index": idx,
                        "title": title,
                        "code": "DUPLICATE_DOI",
                        "message": f"已存在相同 DOI（ID: {dup.paper_id}）",
                    })
                    continue
                _pm = str(pd.get("pmid") or "").strip()
                _doi = str(pd.get("doi") or "").strip()
                _ft = "pending" if (_pm or _doi) else "no_fulltext"
                paper = LiteraturePaper(
                    title=title,
                    authors=__json_authors(authors),
                    journal=pd.get("journal", ""),
                    year=pd.get("year"),
                    volume=str(pd.get("volume", "") or ""),
                    issue=str(pd.get("issue", "") or ""),
                    pages=str(pd.get("pages", "") or ""),
                    doi=pd.get("doi"),
                    pmid=pd.get("pmid"),
                    url=pd.get("url", ""),
                    abstract=pd.get("abstract", ""),
                    keywords=__json_list(pd.get("keywords", [])),
                    import_source=source,
                    fulltext_status=_ft,
                )
                db.add(paper)
                await db.flush()
                paper_ids.append(paper.id)
                success += 1
            except Exception as e:
                failed += 1
                errors.append({
                    "index": idx,
                    "title": title,
                    "code": "IMPORT_ERROR",
                    "message": str(e),
                })
        await db.commit()
    return {
        "success": success,
        "skipped": skipped,
        "failed": failed,
        "paper_ids": paper_ids,
        "errors": errors,
    }


async def _run_import_task(task_id: str, papers_data: list[dict], source: str):
    task = _import_tasks.get(task_id)
    if not task:
        return
    task["status"] = "running"
    task["started_at"] = datetime.utcnow().isoformat()
    try:
        result = await _bulk_import_records(papers_data, source=source)
        task["status"] = "done"
        task["result"] = result
        pids = result.get("paper_ids") or []
        if pids:
            await resolve_fulltext_batch(pids)
    except Exception as e:
        task["status"] = "failed"
        task["error"] = str(e)
    finally:
        task["finished_at"] = datetime.utcnow().isoformat()


from app.api.v1.auth import get_current_user
from app.models.user import User


@router.post("/search")
async def external_search(req: ExternalSearchRequest, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    global _search_cache_last_cleanup_ts
    await _ensure_search_tables(db)
    now_ts = time.time()
    # 低频清理：每 6 小时执行一次，防止缓存表无限增长
    if now_ts - _search_cache_last_cleanup_ts >= 21600:
        try:
            await _cleanup_expired_search_cache(db)
            _search_cache_last_cleanup_ts = now_ts
        except Exception:
            pass
    cache_key = _make_search_cache_key(req, user.id)
    cache_row = await db.execute(
        text("""
            SELECT result_json
            FROM literature_search_cache
            WHERE cache_key=:k AND user_id=:uid AND expires_at > CURRENT_TIMESTAMP
        """),
        {"k": cache_key, "uid": user.id},
    )
    cached = cache_row.fetchone()
    if cached and cached[0]:
        data = json.loads(cached[0])
        # 避免“空结果被缓存”导致后续一小时都拿不到真实结果
        if int(data.get("total") or 0) <= 0:
            print(f"[search] cached ignored total={data.get('total')} results={len(data.get('results') or [])}", flush=True)
            data = None
    else:
        data = None

    if data is None:
        # 用户级 NCBI API Key（优先于环境变量）
        user_id = user.id
        ncbi_key = None
        s2_key = None
        try:
            from app.services.user_settings import UserSettingService
            ncbi_key = await UserSettingService.get(db, user_id, "ncbi_api_key", default="")
            s2_key = await UserSettingService.get(db, user_id, "s2_api_key", default="")
        except Exception:
            ncbi_key = None
            s2_key = None
        data = await _search_coordinator.search(
            SearchRequest(
                query=req.query,
                sources=req.sources,
                year_from=req.year_from,
                year_to=req.year_to,
                pub_types=req.pub_types,
                max_per_source=req.max_per_source,
                language=req.language,
            ),
            ncbi_api_key=ncbi_key,
            s2_api_key=s2_key,
        )
        # 仅缓存“非空结果”，保证结果准确性优先
        if int(data.get("total") or 0) > 0:
            await db.execute(
                text("""
                    INSERT INTO literature_search_cache(cache_key, user_id, result_json, expires_at)
                    VALUES(:k, :uid, :j, datetime('now', '+1 hour'))
                    ON CONFLICT(cache_key) DO UPDATE SET
                        user_id=excluded.user_id,
                        result_json=excluded.result_json,
                        expires_at=excluded.expires_at
                """),
                {"k": cache_key, "uid": user.id, "j": json.dumps(data, ensure_ascii=False)},
            )
            await db.commit()

    data["results"] = await annotate_with_local_status(data.get("results", []), db, user_id=user.id)
    await db.execute(
        text("""
            INSERT INTO literature_search_history(user_id, query, sources, filters, result_count)
            VALUES(:uid, :q, :s, :f, :c)
        """),
        {
            "uid": user.id,
            "q": req.query,
            "s": json.dumps(req.sources, ensure_ascii=False),
            "f": json.dumps(
                {
                    "year_from": req.year_from,
                    "year_to": req.year_to,
                    "pub_types": req.pub_types or [],
                    "language": req.language,
                },
                ensure_ascii=False,
            ),
            "c": int(data.get("total", 0)),
        },
    )
    await db.commit()
    return data


@router.post("/search/stream")
async def external_search_stream(req: ExternalSearchRequest, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """
    SSE 流式检索进度：
    - 逐源返回进度
    - 最后返回合并结果（含 local_status）
    """
    await _ensure_search_tables(db)
    cache_key = _make_search_cache_key(req, user.id)
    cache_row = await db.execute(
        text("""
            SELECT result_json
            FROM literature_search_cache
            WHERE cache_key=:k AND user_id=:uid AND expires_at > CURRENT_TIMESTAMP
        """),
        {"k": cache_key, "uid": user.id},
    )
    cached = cache_row.fetchone()

    async def _gen():
        def _evt(payload: dict) -> str:
            # 避免把整份 results 打进日志，只做关键统计
            try:
                et = payload.get("type")
                p = payload.get("payload") or {}
                # NOTE: 用 print 确保在 Electron/uvicorn 日志里一定能看到
                if et == "source_start":
                    print(f"[search/stream] source_start source={p.get('source')}", flush=True)
                elif et == "source_stage":
                    print(
                        f"[search/stream] source_stage source={p.get('source')} stage={p.get('stage')} progress={p.get('progress')}",
                        flush=True,
                    )
                elif et == "source_done":
                    print(
                        f"[search/stream] source_done source={p.get('source')} count={p.get('count')} error={p.get('error')}",
                        flush=True,
                    )
                elif et == "final":
                    print(f"[search/stream] final total={p.get('total')} results={len(p.get('results') or [])}", flush=True)
                elif et == "cached":
                    print(
                        f"[search/stream] cached total={p.get('total')} results={len(p.get('results') or [])}",
                        flush=True,
                    )
            except Exception:
                pass
            return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"

        try:
            if cached and cached[0]:
                data = json.loads(cached[0])
                # 避免“空结果被缓存”导致后续一小时都拿不到真实结果
                if int(data.get("total") or 0) > 0:
                    data["results"] = await annotate_with_local_status(data.get("results", []), db, user_id=user.id)
                    yield _evt({"type": "cached", "payload": data})
                    return
                print(f"[search/stream] cached ignored total={data.get('total')} results={len(data.get('results') or [])}", flush=True)

            from app.services.user_settings import UserSettingService
            ncbi_key = await UserSettingService.get(db, user.id, "ncbi_api_key", default="")
            s2_key = await UserSettingService.get(db, user.id, "s2_api_key", default="")
            req_obj = SearchRequest(
                query=req.query,
                sources=req.sources,
                year_from=req.year_from,
                year_to=req.year_to,
                pub_types=req.pub_types,
                max_per_source=req.max_per_source,
                language=req.language,
            )

            from app.services.literature.sources.pubmed import PubMedSource
            from app.services.literature.sources.semantic_scholar import SemanticScholarSource
            stage_queue: asyncio.Queue[dict] = asyncio.Queue()
            tasks: list[asyncio.Task] = []
            for s in req_obj.sources:
                yield _evt({
                    "type": "source_start",
                    "payload": {
                        "source": s,
                        "stage": "started",
                        "completed_sources": 0,
                        "total_sources": len(req_obj.sources),
                        "language_policy": _search_coordinator.LANGUAGE_POLICIES.get(s, "none"),
                    },
                })
                if s == "pubmed":
                    inst = PubMedSource(
                        api_key=ncbi_key or getattr(settings, "ncbi_api_key", None)
                    )
                    async def _cb(stage: str, progress: int | None = None, source=s):
                        await stage_queue.put({"source": source, "stage": stage, "progress": progress})
                    t = asyncio.create_task(_search_coordinator._search_with_timeout(s, inst, req_obj, progress_cb=_cb))
                    t.set_name(s)
                    tasks.append(t)
                elif s == "semantic_scholar":
                    inst = SemanticScholarSource(
                        api_key=s2_key or getattr(settings, "s2_api_key", None)
                    )
                    async def _cb(stage: str, progress: int | None = None, source=s):
                        await stage_queue.put({"source": source, "stage": stage, "progress": progress})
                    t = asyncio.create_task(_search_coordinator._search_with_timeout(s, inst, req_obj, progress_cb=_cb))
                    t.set_name(s)
                    tasks.append(t)
                elif s in _search_coordinator.source_instances:
                    async def _cb(stage: str, progress: int | None = None, source=s):
                        await stage_queue.put({"source": source, "stage": stage, "progress": progress})
                    t = asyncio.create_task(
                        _search_coordinator._search_with_timeout(
                            s,
                            _search_coordinator.source_instances[s],
                            req_obj,
                            progress_cb=_cb,
                        )
                    )
                    t.set_name(s)
                    tasks.append(t)

            total = len(tasks)
            done = 0
            by_source: dict[str, object] = {}
            yield _evt({"type": "start", "payload": {"total_sources": total, "sources": req_obj.sources}})
            pending = set(tasks)
            while pending:
                stage_task = asyncio.create_task(stage_queue.get())
                done_set, _ = await asyncio.wait(pending | {stage_task}, return_when=asyncio.FIRST_COMPLETED)
                if stage_task in done_set:
                    msg = stage_task.result()
                    yield _evt({"type": "source_stage", "payload": msg})
                    done_set.remove(stage_task)
                else:
                    stage_task.cancel()

                for fut in list(done_set):
                    pending.remove(fut)
                    res = fut.result()
                    source = fut.get_name() if isinstance(fut, asyncio.Task) else res.source
                    by_source[source] = res
                    done += 1
                    yield _evt({
                        "type": "source_done",
                        "payload": {
                            "source": source,
                            "count": len(res.results),
                            "error": res.error,
                            "elapsed": res.elapsed_ms,
                            "completed_sources": done,
                            "total_sources": total,
                            "language_policy": _search_coordinator.LANGUAGE_POLICIES.get(source, "none"),
                        },
                    })

            merged = ResultMerger().merge({k: v.results for k, v in by_source.items()})
            data = {
                "query": req.query,
                "sources": {
                    s: {
                        "count": len(r.results),
                        "error": r.error,
                        "elapsed": r.elapsed_ms,
                        "language_policy": _search_coordinator.LANGUAGE_POLICIES.get(s, "none"),
                    }
                    for s, r in by_source.items()
                },
                "total": len(merged),
                "results": merged,
            }
            data["results"] = await annotate_with_local_status(data.get("results", []), db, user_id=user.id)

            # 仅缓存“非空结果”，保证结果准确性优先
            if int(data.get("total") or 0) > 0:
                await db.execute(
                    text("""
                        INSERT INTO literature_search_cache(cache_key, user_id, result_json, expires_at)
                        VALUES(:k, :uid, :j, datetime('now', '+1 hour'))
                        ON CONFLICT(cache_key) DO UPDATE SET
                            user_id=excluded.user_id,
                            result_json=excluded.result_json,
                            expires_at=excluded.expires_at
                    """),
                    {"k": cache_key, "uid": user.id, "j": json.dumps(data, ensure_ascii=False)},
                )

            await db.execute(
                text("""
                    INSERT INTO literature_search_history(user_id, query, sources, filters, result_count)
                    VALUES(:uid, :q, :s, :f, :c)
                """),
                {
                    "uid": user.id,
                    "q": req.query,
                    "s": json.dumps(req.sources, ensure_ascii=False),
                    "f": json.dumps(
                        {"year_from": req.year_from, "year_to": req.year_to, "pub_types": req.pub_types or [], "language": req.language},
                        ensure_ascii=False,
                    ),
                    "c": int(data.get("total") or 0),
                },
            )
            await db.commit()
            yield _evt({"type": "final", "payload": data})
        except Exception:
            print("[search/stream] exception during stream generation", flush=True)
            raise

    return StreamingResponse(_gen(), media_type="text/event-stream")


@router.get("/search/sources")
async def search_sources():
    return {
        "items": [
            {"id": "pubmed", "name": "PubMed", "enabled": True},
            {"id": "crossref", "name": "CrossRef", "enabled": True},
            {"id": "semantic_scholar", "name": "Semantic Scholar", "enabled": True},
        ]
    }


@router.get("/search/pubmed/{pmid}/abstract")
async def pubmed_abstract(
    pmid: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """按需拉取 PubMed 摘要（EFetch）"""
    from app.services.literature.sources.pubmed import PubMedSource
    from app.services.user_settings import UserSettingService

    user_id = user.id
    key = await UserSettingService.get(db, user_id, "ncbi_api_key", default="") or None
    inst = PubMedSource(api_key=key)
    abstract = await inst.fetch_abstract(pmid)
    return {"pmid": str(pmid), "abstract": abstract}


@router.get("/search/abstract")
async def search_abstract(
    pmid: str | None = Query(None),
    doi: str | None = Query(None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    统一摘要按需拉取：
    - ?pmid=... -> PubMed EFetch
    - ?doi=...  -> CrossRef 元数据摘要
    """
    if not pmid and not doi:
        raise HTTPException(status_code=400, detail="请提供 pmid 或 doi")
    if pmid and doi:
        raise HTTPException(status_code=400, detail="pmid 与 doi 二选一")

    if pmid:
        from app.services.literature.sources.pubmed import PubMedSource
        from app.services.user_settings import UserSettingService

        key = await UserSettingService.get(db, user.id, "ncbi_api_key", default="") or None
        inst = PubMedSource(api_key=key)
        abstract = await inst.fetch_abstract(str(pmid))
        return {"pmid": str(pmid), "doi": None, "abstract": abstract}

    from app.services.literature.metadata_fetcher import MetadataFetcher
    fetcher = MetadataFetcher()
    md = await fetcher.fetch_by_doi(str(doi))
    abstract = (md or {}).get("abstract", "") if isinstance(md, dict) else ""
    return {"pmid": None, "doi": str(doi), "abstract": abstract or ""}


@router.get("/search/history")
async def search_history(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db), limit: int = 30):
    await _ensure_search_tables(db)
    rows = await db.execute(
        text("""
            SELECT id, query, sources, filters, result_count, created_at
            FROM literature_search_history
            WHERE user_id=:uid
            ORDER BY id DESC
            LIMIT :n
        """),
        {"uid": user.id, "n": max(1, min(limit, 200))},
    )
    items = []
    for r in rows.fetchall():
        items.append({
            "id": r[0],
            "query": r[1],
            "sources": json.loads(r[2] or "[]"),
            "filters": json.loads(r[3] or "{}"),
            "result_count": r[4] or 0,
            "created_at": str(r[5]) if r[5] else None,
        })
    return {"items": items}


@router.delete("/search/history/{history_id}", status_code=204)
async def delete_search_history(history_id: int, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    await _ensure_search_tables(db)
    await db.execute(
        text("DELETE FROM literature_search_history WHERE id=:i AND user_id=:uid"),
        {"i": history_id, "uid": user.id},
    )
    await db.commit()


@router.post("/search/cache/cleanup")
async def cleanup_search_cache(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """手动清理过期检索缓存（按 expires_at）。"""
    deleted = await _cleanup_expired_search_cache(db)
    return {"deleted": deleted, "requested_by": user.id}


@router.post("/search/save")
async def save_search_result(
    req: SaveSearchResultRequest,
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        checker = DuplicateChecker(db, user_id=user.id)
        requested_tag_ids = list(set(req.tag_ids or []))
        valid_tag_ids: set[int] = set()
        if requested_tag_ids:
            rows = await db.execute(
                select(LiteratureTag.id).where(LiteratureTag.id.in_(requested_tag_ids))
            )
            valid_tag_ids = {int(r[0]) for r in rows.fetchall()}
        invalid_tag_ids = [tid for tid in requested_tag_ids if tid not in valid_tag_ids]
        details: list[dict] = []
        created_paper_ids: list[int] = []
        for item in req.items:
            dup = await checker.check(
                doi=item.doi,
                title=item.title,
                authors=[a.model_dump() for a in item.authors],
                year=item.year,
                pmid=item.pmid,
            )
            if dup.exact_match:
                details.append({"title": item.title, "status": "duplicate", "existing_id": dup.paper_id})
                continue
            try:
                async with db.begin_nested():
                    _sft = "pending" if (item.pmid or item.doi) else "no_fulltext"
                    paper = LiteraturePaper(
                        user_id=user.id,
                        title=item.title,
                        authors=json.dumps([a.model_dump() for a in item.authors], ensure_ascii=False),
                        journal=item.journal or "",
                        year=item.year,
                        volume=item.volume or "",
                        issue=item.issue or "",
                        pages=item.pages or "",
                        doi=(item.doi or None),
                        pmid=(str(item.pmid).strip() if item.pmid else None),
                        url=item.url or "",
                        abstract=item.abstract or "",
                        keywords=json.dumps([], ensure_ascii=False),
                        collection_id=req.collection_id,
                        import_source=f"search_{item.source}",
                        read_status="unread",
                        fulltext_status=_sft,
                    )
                    db.add(paper)
                    await db.flush()
                    if valid_tag_ids:
                        for tag_id in valid_tag_ids:
                            db.add(LiteraturePaperTag(paper_id=paper.id, tag_id=tag_id))
                        await db.flush()
                    details.append({"title": item.title, "status": "created", "paper_id": paper.id})
                    if _sft == "pending":
                        created_paper_ids.append(paper.id)
            except IntegrityError as e:
                details.append({
                    "title": item.title,
                    "status": "error",
                    "reason": "唯一约束冲突（DOI/PMID 可能已被占用或仍在回收站）",
                })
            except Exception as e:
                details.append({"title": item.title, "status": "error", "reason": str(e)[:120]})
        try:
            await db.commit()
        except IntegrityError as e:
            await db.rollback()
            raise HTTPException(
                status_code=409,
                detail=f"入库提交失败（唯一约束）: {str(e)[:200]}",
            ) from e
        if created_paper_ids:
            background_tasks.add_task(resolve_fulltext_batch, created_paper_ids)
        created = sum(1 for d in details if d["status"] == "created")
        skipped = sum(1 for d in details if d["status"] == "duplicate")
        return {
            "created": created,
            "skipped": skipped,
            "errors": len(details) - created - skipped,
            "details": details,
            "invalid_tag_ids": invalid_tag_ids,
        }
    except HTTPException:
        raise
    except Exception as e:
        try:
            await db.rollback()
        except Exception:
            pass
        logger.exception("search/save failed: %s", e)
        raise HTTPException(status_code=502, detail=f"入库失败: {str(e)[:240]}") from e


@router.post("/papers/fetch-metadata")
async def fetch_metadata(req: FetchMetadataRequest):
    """DOI/PMID 拉取元数据（预览，不创建）"""
    from app.services.literature.metadata_fetcher import MetadataFetcher
    fetcher = MetadataFetcher()
    try:
        if req.doi:
            result = await fetcher.fetch_by_doi(req.doi)
        elif req.pmid:
            result = await fetcher.fetch_by_pmid(req.pmid)
        else:
            raise HTTPException(status_code=400, detail="需要提供 doi 或 pmid")
        if result is None:
            raise HTTPException(
                status_code=404,
                detail={
                    "code": "METADATA_NOT_FOUND",
                    "message": f"未找到该 {'DOI' if req.doi else 'PMID'} 对应的文献，请检查格式或手动录入",
                },
            )
        return result
    except httpx.TimeoutException:
        raise HTTPException(
            status_code=504,
            detail={"code": "FETCH_TIMEOUT", "message": "元数据服务请求超时，请稍后重试或手动录入"},
        )
    except httpx.ConnectError:
        raise HTTPException(
            status_code=503,
            detail={"code": "NETWORK_ERROR", "message": "无法连接到元数据服务，请检查网络或手动录入"},
        )


@router.get("/papers/{paper_id}/similar")
async def recommend_similar_papers(
    paper_id: int,
    top_k: int = 5,
    db: AsyncSession = Depends(get_db),
):
    """相似文献推荐：优先向量相似，失败时降级关键词重叠。"""
    result = await db.execute(select(LiteraturePaper.id).where(LiteraturePaper.id == paper_id))
    if not result.first():
        raise HTTPException(status_code=404, detail="文献不存在")
    from app.services.literature.recommender import SimilarPaperRecommender

    rows = await SimilarPaperRecommender().recommend(
        paper_id=paper_id,
        db=db,
        top_k=max(1, min(top_k, 20)),
    )
    return {"items": rows, "top_k": top_k}


@router.get("/papers/{paper_id}/suggest-tags", response_model=TagSuggestResponse)
async def suggest_tags(paper_id: int, db: AsyncSession = Depends(get_db)):
    """基于关键词与期刊建议已有标签，并给出新标签建议。"""
    result = await db.execute(select(LiteraturePaper).where(LiteraturePaper.id == paper_id))
    paper = result.scalar_one_or_none()
    if not paper:
        raise HTTPException(status_code=404, detail="文献不存在")

    try:
        keywords = json.loads(paper.keywords) if isinstance(paper.keywords, str) else (paper.keywords or [])
    except Exception:
        keywords = []
    keywords = [str(k) for k in keywords if str(k).strip()]

    all_tags_result = await db.execute(select(LiteratureTag))
    all_tags = all_tags_result.scalars().all()
    match_pool = keywords + ([paper.journal] if paper.journal else [])
    existing_suggestions = []
    for tag in all_tags:
        tag_name = (tag.name or "").lower()
        if not tag_name:
            continue
        if any(tag_name in p.lower() or p.lower() in tag_name for p in match_pool if p):
            existing_suggestions.append({"id": tag.id, "name": tag.name, "color": tag.color})

    existing_names = {(t.name or "").lower() for t in all_tags}
    new_suggestions = [kw for kw in keywords[:5] if kw.lower() not in existing_names]

    return {
        "existing_tags": existing_suggestions[:5],
        "new_tag_suggestions": new_suggestions,
    }


@router.post("/papers/browser-capture")
async def browser_capture(
    req: BrowserCaptureRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """
    浏览器插件采集：支持 DOI 补全、去重检查、入库。
    """
    from app.services.literature.metadata_fetcher import MetadataFetcher

    metadata: dict = {}
    if req.doi:
        try:
            metadata = await MetadataFetcher().fetch_by_doi(req.doi) or {}
        except Exception:
            metadata = {}

    paper_data = {
        "title": metadata.get("title") or req.title,
        "authors": metadata.get("authors", []),
        "journal": metadata.get("journal", ""),
        "year": metadata.get("year"),
        "doi": metadata.get("doi") or req.doi,
        "url": req.url,
        "abstract": metadata.get("abstract") or req.abstract or "",
        "keywords": metadata.get("keywords") or [],
        "import_source": "browser",
    }

    dup = await DuplicateChecker(db).check(
        doi=paper_data["doi"],
        title=paper_data["title"],
        authors=paper_data["authors"],
        year=paper_data["year"],
    )
    if dup.exact_match:
        return {"status": "duplicate", "existing_id": dup.paper_id}

    _ft = "pending" if paper_data.get("doi") else "no_fulltext"
    paper = LiteraturePaper(
        title=paper_data["title"],
        authors=__json_authors(paper_data["authors"]),
        journal=paper_data["journal"],
        year=paper_data["year"],
        doi=paper_data["doi"],
        url=paper_data["url"],
        abstract=paper_data["abstract"],
        keywords=__json_list(paper_data["keywords"]),
        import_source="browser",
        fulltext_status=_ft,
    )
    db.add(paper)
    await db.commit()
    await db.refresh(paper)
    if paper_data.get("doi"):
        background_tasks.add_task(resolve_fulltext_for_paper, paper.id)
    return {"status": "created", "paper_id": paper.id}


@router.post("/papers/check-duplicate")
async def check_duplicate(req: DupCheckRequest, db: AsyncSession = Depends(get_db)):
    """去重检查（预检，不创建）"""
    authors = [{"name": a.name, "affil": a.affil} for a in req.authors] if req.authors else []
    result = await DuplicateChecker(db).check(
        doi=req.doi, title=req.title, authors=authors, year=req.year, pmid=req.pmid
    )
    return {
        "exact_match": result.exact_match,
        "paper_id": result.paper_id,
        "fuzzy_matches": result.fuzzy_matches or [],
    }


@router.post("/papers/batch", response_model=BatchOperationResponse)
async def batch_operation(req: BatchOperationRequest, db: AsyncSession = Depends(get_db)):
    """
    批量操作：tag（追加标签）/ move（移动集合）/ delete（软删除）/
    read_status（阅读状态）/ restore（从回收站恢复）
    """
    ids = req.paper_ids or []
    if not ids:
        raise HTTPException(status_code=400, detail="paper_ids 不能为空")
    if len(ids) > 200:
        raise HTTPException(status_code=400, detail="单次批量操作不超过 200 条")

    op = req.operation
    payload = req.payload or {}

    if op == "tag":
        tag_ids = payload.get("tag_ids") or []
        await _validate_tag_ids_exist(db, tag_ids)
        for paper_id in ids:
            for tag_id in tag_ids:
                stmt = insert(LiteraturePaperTag).prefix_with("OR IGNORE").values(
                    paper_id=paper_id, tag_id=tag_id
                )
                await db.execute(stmt)

    elif op == "move":
        collection_id = payload.get("collection_id")
        await _validate_collection_exists(db, collection_id)
        await db.execute(
            update(LiteraturePaper)
            .where(LiteraturePaper.id.in_(ids))
            .values(collection_id=collection_id, updated_at=datetime.utcnow())
        )

    elif op == "delete":
        now = datetime.utcnow()
        await db.execute(
            update(LiteraturePaper)
            .where(LiteraturePaper.id.in_(ids))
            .where(LiteraturePaper.deleted_at.is_(None))
            .values(deleted_at=now, deleted_at_ts=int(now.timestamp()), updated_at=now)
        )

    elif op == "read_status":
        status = payload.get("status")
        if status not in ("unread", "reading", "read"):
            raise HTTPException(status_code=400, detail="无效的阅读状态")
        await db.execute(
            update(LiteraturePaper)
            .where(LiteraturePaper.id.in_(ids))
            .values(read_status=status, updated_at=datetime.utcnow())
        )

    elif op == "restore":
        await db.execute(
            update(LiteraturePaper)
            .where(LiteraturePaper.id.in_(ids))
            .values(deleted_at=None, deleted_at_ts=None, updated_at=datetime.utcnow())
        )

    elif op == "permanent":
        from sqlalchemy import text

        result = await db.execute(
            select(LiteraturePaper)
            .where(LiteraturePaper.id.in_(ids))
            .where(LiteraturePaper.deleted_at.is_not(None))
        )
        papers_to_del = result.scalars().all()
        base_path = Path(settings.app_data_root)
        for paper in papers_to_del:
            if paper.pdf_path:
                (base_path / paper.pdf_path.lstrip("/")).unlink(missing_ok=True)
            att_result = await db.execute(
                select(LiteratureAttachment).where(LiteratureAttachment.paper_id == paper.id)
            )
            for att in att_result.scalars().all():
                (base_path / att.file_path.lstrip("/")).unlink(missing_ok=True)
            chunk_result = await db.execute(
                select(PaperChunk.id).where(PaperChunk.paper_id == paper.id)
            )
            chunk_ids = [r[0] for r in chunk_result.fetchall()]
            if chunk_ids:
                ph = ",".join(str(i) for i in chunk_ids)
                await db.execute(
                    text(
                        "INSERT INTO paper_fts(paper_fts, rowid) SELECT 'delete', rowid FROM paper_fts WHERE chunk_id IN (%s)"
                        % ph
                    )
                )
            await db.execute(delete(PaperChunk).where(PaperChunk.paper_id == paper.id))
            await db.delete(paper)
        await db.commit()
        return {"success": True, "affected": len(papers_to_del)}

    await db.commit()
    return {"success": True, "affected": len(ids)}


@router.post("/papers", status_code=201)
async def create_paper(
    req: PaperCreateRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """手动录入文献，录入前执行去重检查"""
    authors = [{"name": a.name, "affil": a.affil} for a in req.authors]
    await _validate_collection_exists(db, req.collection_id)
    await _validate_tag_ids_exist(db, req.tag_ids)
    dup = await DuplicateChecker(db).check(
        doi=req.doi, title=req.title, authors=authors, year=req.year, pmid=req.pmid
    )
    if dup.exact_match:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "DUPLICATE_DOI_OR_PMID",
                "message": f"已存在相同 DOI/PMID 的文献（ID: {dup.paper_id}）",
                "existing_id": dup.paper_id,
            },
        )

    _ft = "pending" if (req.pmid or req.doi) else "no_fulltext"
    paper = LiteraturePaper(
        title=req.title,
        authors=__json_authors(authors),
        journal=req.journal or "",
        year=req.year,
        volume=req.volume or "",
        issue=req.issue or "",
        pages=req.pages or "",
        doi=req.doi,
        pmid=req.pmid,
        url=req.url or "",
        abstract=req.abstract or "",
        keywords=__json_list(req.keywords),
        language=req.language or "zh",
        read_status=req.read_status,
        collection_id=req.collection_id,
        import_source="manual",
        fulltext_status=_ft,
    )
    db.add(paper)
    await db.flush()
    if req.tag_ids:
        await _sync_tags(db, paper.id, req.tag_ids)
    await db.commit()
    await db.refresh(paper)
    if req.pmid or req.doi:
        background_tasks.add_task(resolve_fulltext_for_paper, paper.id)
    return _paper_response(paper)


def __json_authors(authors: list[dict]) -> str:
    import json
    return json.dumps(authors, ensure_ascii=False)


def __json_list(lst: list) -> str:
    import json
    return json.dumps(lst, ensure_ascii=False)


def _paper_response(p: LiteraturePaper) -> dict:
    import json
    return {
        "id": p.id,
        "title": p.title,
        "authors": json.loads(p.authors) if isinstance(p.authors, str) else p.authors,
        "journal": p.journal,
        "year": p.year,
        "doi": p.doi,
        "pmid": p.pmid,
        "abstract": p.abstract,
        "keywords": json.loads(p.keywords) if isinstance(p.keywords, str) else p.keywords,
        "pdf_path": p.pdf_path,
        "pdf_indexed": p.pdf_indexed,
        "fulltext_status": getattr(p, "fulltext_status", None) or "pending",
        "read_status": p.read_status,
        "collection_id": p.collection_id,
        "created_at": str(p.created_at) if p.created_at else None,
        "deleted_at": str(p.deleted_at) if p.deleted_at else None,
    }


def _rect_for_response(rect_value: str | None) -> dict | str:
    if not rect_value:
        return ""
    if isinstance(rect_value, str):
        try:
            parsed = json.loads(rect_value)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            return rect_value
    return rect_value


def _rect_for_storage(rect_value: RectPayload | str | None) -> str | None:
    if rect_value is None:
        return None
    if isinstance(rect_value, str):
        return rect_value
    return json.dumps(rect_value.model_dump(), ensure_ascii=False)


@router.get("/papers", response_model=PaperListResponse)
async def list_papers(
    q: str | None = None,
    author: str | None = None,
    journal: str | None = None,
    year_from: int | None = None,
    year_to: int | None = None,
    keyword: str | None = None,
    collection_id: int | None = None,
    tag_ids: list[int] = Query(default=[]),
    read_status: ReadStatusLiteral | None = Query(default=None),
    sort_by: str = "created_at",
    sort_dir: str = "desc",
    page: int = 1,
    page_size: int = 20,
    trashed: bool = False,
    db: AsyncSession = Depends(get_db),
):
    """多条件列表查询（FTS5 + 结构化过滤）"""
    builder = PaperQueryBuilder(db)
    if trashed:
        builder.filter_trashed()
    else:
        builder.filter_active()
    if q:
        builder.fts_search(q)
    if author:
        builder.filter_author(author)
    if journal:
        builder.filter_journal(journal)
    if year_from is not None:
        builder.filter_year_from(year_from)
    if year_to is not None:
        builder.filter_year_to(year_to)
    if keyword:
        builder.filter_keyword(keyword)
    if collection_id is not None:
        builder.filter_collection(collection_id)
    if tag_ids:
        builder.filter_tags(tag_ids)
    if read_status:
        builder.filter_read_status(read_status)
    builder.sort(sort_by, sort_dir)
    total, items = await builder.paginate(page, page_size)
    return {"total": total, "page": page, "page_size": page_size, "items": items}


@router.get("/papers/search")
async def search_papers(
    q: str = "",
    top_k: int = 10,
    db: AsyncSession = Depends(get_db),
):
    """文献全文检索（基于 paper_fts）"""
    from app.services.vector.fts5 import paper_fts_search

    if not q or not q.strip():
        return {"items": [], "query": q}
    chunks = await paper_fts_search(
        query=q.strip(),
        top_k=min(top_k, 50),
        with_content=True,
        only_fulltext_literature=True,
    )
    if not chunks:
        return {"items": [], "query": q}
    chunk_ids = [c["chunk_id"] for c in chunks]
    chunk_result = await db.execute(
        select(PaperChunk.id, PaperChunk.paper_id, PaperChunk.chunk_text, PaperChunk.chunk_type).where(
            PaperChunk.id.in_(chunk_ids)
        )
    )
    chunk_rows = {r[0]: {"paper_id": r[1], "content": r[2], "chunk_type": r[3]} for r in chunk_result.fetchall()}
    paper_ids = list({cr["paper_id"] for cr in chunk_rows.values()})
    papers_result = await db.execute(select(LiteraturePaper).where(LiteraturePaper.id.in_(paper_ids)))
    papers_map = {p.id: p for p in papers_result.scalars().all()}
    items = []
    for c in chunks:
        meta = chunk_rows.get(c["chunk_id"])
        if not meta:
            continue
        paper = papers_map.get(meta["paper_id"])
        if not paper:
            continue
        items.append({
            "paper_id": meta["paper_id"],
            "title": paper.title,
            "status": "done" if paper.pdf_indexed else "pending",
            "chunk_id": c["chunk_id"],
            "snippet": c.get("snippet", c.get("content", ""))[:200],
            "chunk_type": meta.get("chunk_type"),
        })
    return {"items": items, "query": q}


@router.get(
    "/papers/{paper_id}",
    response_model=PaperDetailResponse,
    responses={404: {"model": ErrorResponse}},
)
async def get_paper(paper_id: int, db: AsyncSession = Depends(get_db)):
    """文献详情（含附件列表、标注数量）"""
    result = await db.execute(select(LiteraturePaper).where(LiteraturePaper.id == paper_id))
    paper = result.scalar_one_or_none()
    if not paper or paper.deleted_at:
        raise HTTPException(status_code=404, detail="文献不存在")
    tag_result = await db.execute(
        select(LiteratureTag)
        .join(LiteraturePaperTag, LiteratureTag.id == LiteraturePaperTag.tag_id)
        .where(LiteraturePaperTag.paper_id == paper_id)
    )
    tags = [
        {"id": t.id, "name": t.name, "color": t.color}
        for t in tag_result.scalars().all()
    ]
    collection = None
    if paper.collection_id:
        coll_result = await db.execute(
            select(LiteratureCollection).where(LiteratureCollection.id == paper.collection_id)
        )
        coll = coll_result.scalar_one_or_none()
        if coll:
            collection = {
                "id": coll.id,
                "name": coll.name,
                "parent_id": coll.parent_id,
                "color": coll.color,
                "icon": coll.icon,
            }
    att_result = await db.execute(
        select(LiteratureAttachment).where(LiteratureAttachment.paper_id == paper_id)
    )
    attachments = [
        {
            "id": a.id,
            "filename": a.filename,
            "file_type": a.file_type,
            "file_size": a.file_size,
            "description": a.description,
            "created_at": str(a.created_at) if a.created_at else None,
        }
        for a in att_result.scalars().all()
    ]
    ann_count = await db.scalar(
        select(func.count()).select_from(LiteratureAnnotation).where(LiteratureAnnotation.paper_id == paper_id)
    )
    resp = _paper_response(paper)
    resp["tags"] = tags
    resp["collection"] = collection
    resp["attachments"] = attachments
    resp["annotation_count"] = ann_count or 0
    return resp


@router.get(
    "/papers/{paper_id}/chunks",
    responses={404: {"model": ErrorResponse}},
)
async def get_paper_chunks(paper_id: int, db: AsyncSession = Depends(get_db)):
    """获取文献全文分块（paper_chunks），按 chunk_index 排序"""
    result = await db.execute(select(LiteraturePaper).where(LiteraturePaper.id == paper_id))
    paper = result.scalar_one_or_none()
    if not paper or paper.deleted_at:
        raise HTTPException(status_code=404, detail="文献不存在")
    chunk_result = await db.execute(
        select(PaperChunk)
        .where(PaperChunk.paper_id == paper_id)
        .order_by(PaperChunk.chunk_index)
    )
    chunks = chunk_result.scalars().all()
    return {
        "paper_id": paper_id,
        "total": len(chunks),
        "items": [
            {
                "id": c.id,
                "chunk_index": c.chunk_index,
                "chunk_type": c.chunk_type or "",
                "chunk_text": c.chunk_text or "",
                "section": c.section or "",
                "page_start": c.page_start,
                "page_end": c.page_end,
            }
            for c in chunks
        ],
    }


@router.get(
    "/papers/{paper_id}/export",
    response_model=CitationExportResponse,
    responses={404: {"model": ErrorResponse}},
)
async def export_citation(
    paper_id: int,
    format: Literal["apa", "bibtex", "nlm", "gbt7714"] = "apa",
    db: AsyncSession = Depends(get_db),
):
    """引用格式导出"""
    result = await db.execute(select(LiteraturePaper).where(LiteraturePaper.id == paper_id))
    paper = result.scalar_one_or_none()
    if not paper:
        raise HTTPException(status_code=404, detail="文献不存在")
    citation = CitationFormatter(paper).format(format)
    return {"format": format, "citation": citation}


@router.post(
    "/papers/export-batch",
    responses={400: {"model": ErrorResponse}},
)
async def export_batch(
    req: ExportBatchRequest,
    db: AsyncSession = Depends(get_db),
):
    """批量导出引用"""
    if not req.ids:
        raise HTTPException(status_code=400, detail="ids 不能为空")
    result = await db.execute(
        select(LiteraturePaper).where(
            LiteraturePaper.id.in_(req.ids),
            LiteraturePaper.deleted_at.is_(None),
        )
    )
    papers = result.scalars().all()
    items = []
    for p in papers:
        citation = CitationFormatter(p).format(req.format)
        items.append({"paper_id": p.id, "title": p.title, "citation": citation})
    combined = "\n\n".join(it["citation"] for it in items)
    return {"format": req.format, "items": items, "combined": combined}


@router.post(
    "/papers/{paper_id}/pdf",
    status_code=200,
    responses={400: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
)
async def upload_paper_pdf(
    paper_id: int,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    """为指定文献上传/替换 PDF"""
    result = await db.execute(select(LiteraturePaper).where(LiteraturePaper.id == paper_id))
    paper = result.scalar_one_or_none()
    if not paper or paper.deleted_at:
        raise HTTPException(status_code=404, detail="文献不存在")
    ext = Path(file.filename or "").suffix or ".pdf"
    if ext.lower() != ".pdf":
        raise HTTPException(status_code=400, detail="仅支持 PDF")

    base_path = Path(settings.app_data_root)
    if paper.pdf_path:
        old_path = base_path / paper.pdf_path.lstrip("/")
        if old_path.exists():
            old_path.unlink(missing_ok=True)
        chunk_result = await db.execute(select(PaperChunk.id).where(PaperChunk.paper_id == paper_id))
        chunk_ids = [r[0] for r in chunk_result.fetchall()]
        if chunk_ids:
            from sqlalchemy import text
            ph = ",".join(str(i) for i in chunk_ids)
            await db.execute(
                text(
                    "INSERT INTO paper_fts(paper_fts, rowid) SELECT 'delete', rowid FROM paper_fts WHERE chunk_id IN (%s)"
                    % ph
                )
            )
        await db.execute(delete(PaperChunk).where(PaperChunk.paper_id == paper_id))

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    path = UPLOAD_DIR / f"{os.urandom(8).hex()}{ext}"
    content = await file.read()
    path.write_bytes(content)
    rel_path = str(path.relative_to(settings.app_data_root))

    paper.pdf_path = rel_path
    paper.pdf_size = len(content)
    paper.pdf_indexed = 0
    paper.fulltext_status = "pending"
    paper.updated_at = datetime.utcnow()
    await db.commit()

    background_tasks.add_task(_index_paper_task, paper_id, rel_path)
    return {"id": paper_id, "status": "indexing"}


@router.delete(
    "/papers/{paper_id}/pdf",
    status_code=204,
    responses={404: {"model": ErrorResponse}},
)
async def delete_paper_pdf(
    paper_id: int,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """删除指定文献的 PDF（保留元数据）"""
    from sqlalchemy import text

    result = await db.execute(select(LiteraturePaper).where(LiteraturePaper.id == paper_id))
    paper = result.scalar_one_or_none()
    if not paper or paper.deleted_at:
        raise HTTPException(status_code=404, detail="文献不存在")

    base_path = Path(settings.app_data_root)
    if paper.pdf_path:
        (base_path / paper.pdf_path.lstrip("/")).unlink(missing_ok=True)

    chunk_result = await db.execute(select(PaperChunk.id).where(PaperChunk.paper_id == paper_id))
    chunk_ids = [r[0] for r in chunk_result.fetchall()]
    if chunk_ids:
        ph = ",".join(str(i) for i in chunk_ids)
        await db.execute(
            text(
                "INSERT INTO paper_fts(paper_fts, rowid) SELECT 'delete', rowid FROM paper_fts WHERE chunk_id IN (%s)"
                % ph
            )
        )
    await db.execute(delete(PaperChunk).where(PaperChunk.paper_id == paper_id))

    paper.pdf_path = None
    paper.pdf_size = 0
    paper.pdf_indexed = 0
    paper.fulltext_status = "pending" if ((paper.pmid or "").strip() or (paper.doi or "").strip()) else "no_fulltext"
    paper.updated_at = datetime.utcnow()
    await db.commit()
    background_tasks.add_task(resolve_fulltext_for_paper, paper_id)


@router.post(
    "/papers/{paper_id}/resolve-fulltext",
    responses={404: {"model": ErrorResponse}},
)
async def trigger_resolve_fulltext(
    paper_id: int,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """手动触发全文获取：优先 PDF 解析，否则尝试 PMC 等开放获取正文并写入检索索引。"""
    result = await db.execute(select(LiteraturePaper).where(LiteraturePaper.id == paper_id))
    paper = result.scalar_one_or_none()
    if not paper or paper.deleted_at:
        raise HTTPException(status_code=404, detail="文献不存在")
    background_tasks.add_task(resolve_fulltext_for_paper, paper_id)
    return {"paper_id": paper_id, "status": "queued"}


@router.get(
    "/papers/{paper_id}/pdf",
    responses={404: {"model": ErrorResponse}},
)
async def serve_pdf(paper_id: int, db: AsyncSession = Depends(get_db)):
    """提供 PDF 文件流（支持 Range 请求，PDF.js 分页加载必须）"""
    result = await db.execute(select(LiteraturePaper).where(LiteraturePaper.id == paper_id))
    paper = result.scalar_one_or_none()
    if not paper or paper.deleted_at or not paper.pdf_path:
        raise HTTPException(status_code=404, detail="PDF 不存在")
    pdf_path = Path(settings.app_data_root) / paper.pdf_path
    if not pdf_path.exists():
        raise HTTPException(status_code=404, detail="PDF 文件不存在")
    return FileResponse(
        path=str(pdf_path),
        media_type="application/pdf",
        headers={"Accept-Ranges": "bytes"},
    )


ALLOWED_ATTACHMENT_EXT = {".pdf", ".doc", ".docx", ".xls", ".xlsx", ".zip", ".txt", ".md", ".csv"}


@router.get(
    "/papers/{paper_id}/attachments",
    response_model=AttachmentListResponse,
    responses={404: {"model": ErrorResponse}},
)
async def list_attachments(paper_id: int, db: AsyncSession = Depends(get_db)):
    """附件列表"""
    result = await db.execute(select(LiteraturePaper.id).where(LiteraturePaper.id == paper_id))
    if not result.first():
        raise HTTPException(status_code=404, detail="文献不存在")
    att_result = await db.execute(
        select(LiteratureAttachment).where(LiteratureAttachment.paper_id == paper_id)
    )
    items = [
        {"id": a.id, "filename": a.filename, "file_type": a.file_type, "file_size": a.file_size, "description": a.description, "created_at": str(a.created_at) if a.created_at else None}
        for a in att_result.scalars().all()
    ]
    return {"items": items}


@router.post(
    "/papers/{paper_id}/attachments",
    response_model=AttachmentResponse,
    status_code=201,
    responses={400: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
)
async def upload_attachment(
    paper_id: int,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    description: str = Form(default=""),
    db: AsyncSession = Depends(get_db),
):
    """上传附件（支持 pdf/docx/xlsx/zip 等）"""
    result = await db.execute(select(LiteraturePaper.id).where(LiteraturePaper.id == paper_id))
    if not result.first():
        raise HTTPException(status_code=404, detail="文献不存在")
    ext = Path(file.filename or "").suffix.lower()
    if ext not in ALLOWED_ATTACHMENT_EXT:
        raise HTTPException(status_code=400, detail=f"不支持的文件类型，允许: {', '.join(ALLOWED_ATTACHMENT_EXT)}")
    base = Path(file.filename or "unnamed").stem
    safe_stem = _safe_filename(base) or "file"
    safe_name = f"{safe_stem}{ext}"
    dest_dir = ATTACHMENTS_DIR / str(paper_id)
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_path = dest_dir / safe_name
    if dest_path.exists():
        safe_name = f"{safe_stem}_{os.urandom(4).hex()}{ext}"
        dest_path = dest_dir / safe_name
    content = await file.read()
    dest_path.write_bytes(content)
    rel_path = str(dest_path.relative_to(settings.app_data_root))
    att = LiteratureAttachment(
        paper_id=paper_id,
        filename=safe_name,
        file_path=rel_path,
        file_type=ext.lstrip("."),
        file_size=len(content),
        description=description,
    )
    db.add(att)
    await db.commit()
    await db.refresh(att)
    if ext == ".pdf":
        background_tasks.add_task(_index_attachment_task, att.id)
    return {
        "id": att.id,
        "filename": att.filename,
        "file_type": att.file_type,
        "file_size": att.file_size,
        "description": att.description,
        "created_at": str(att.created_at) if att.created_at else None,
    }


@router.delete(
    "/papers/{paper_id}/attachments/{att_id}",
    status_code=204,
    responses={404: {"model": ErrorResponse}},
)
async def delete_attachment(paper_id: int, att_id: int, db: AsyncSession = Depends(get_db)):
    """删除附件"""
    result = await db.execute(
        select(LiteratureAttachment).where(
            LiteratureAttachment.id == att_id,
            LiteratureAttachment.paper_id == paper_id,
        )
    )
    att = result.scalar_one_or_none()
    if not att:
        raise HTTPException(status_code=404, detail="附件不存在")
    full_path = Path(settings.app_data_root) / att.file_path
    full_path.unlink(missing_ok=True)
    await db.delete(att)
    await db.commit()


@router.get(
    "/papers/{paper_id}/annotations",
    response_model=AnnotationListResponse,
    responses={404: {"model": ErrorResponse}},
)
async def list_annotations(paper_id: int, db: AsyncSession = Depends(get_db)):
    """标注列表"""
    result = await db.execute(select(LiteraturePaper.id).where(LiteraturePaper.id == paper_id))
    if not result.first():
        raise HTTPException(status_code=404, detail="文献不存在")
    ann_result = await db.execute(
        select(LiteratureAnnotation)
        .where(LiteratureAnnotation.paper_id == paper_id)
        .order_by(LiteratureAnnotation.page_number, LiteratureAnnotation.id)
    )
    items = [
        {
            "id": a.id,
            "annotation_type": a.annotation_type,
            "page_number": a.page_number,
            "rect": _rect_for_response(a.rect),
            "color": a.color,
            "content": a.content,
            "selected_text": a.selected_text,
        }
        for a in ann_result.scalars().all()
    ]
    return {"items": items}


@router.post(
    "/papers/{paper_id}/annotations",
    response_model=AnnotationResponse,
    status_code=201,
    responses={404: {"model": ErrorResponse}},
)
async def create_annotation(
    paper_id: int,
    req: AnnotationCreateRequest,
    db: AsyncSession = Depends(get_db),
):
    """创建标注"""
    result = await db.execute(select(LiteraturePaper.id).where(LiteraturePaper.id == paper_id))
    if not result.first():
        raise HTTPException(status_code=404, detail="文献不存在")
    ann = LiteratureAnnotation(
        paper_id=paper_id,
        annotation_type=req.annotation_type,
        page_number=req.page_number,
        rect=_rect_for_storage(req.rect),
        color=req.color,
        content=req.content,
        selected_text=req.selected_text,
    )
    db.add(ann)
    await db.commit()
    await db.refresh(ann)
    return {
        "id": ann.id,
        "annotation_type": ann.annotation_type,
        "page_number": ann.page_number,
        "rect": _rect_for_response(ann.rect),
        "color": ann.color,
        "content": ann.content,
        "selected_text": ann.selected_text,
    }


@router.put(
    "/papers/{paper_id}/annotations/{ann_id}",
    response_model=AnnotationResponse,
    responses={404: {"model": ErrorResponse}},
)
async def update_annotation(
    paper_id: int,
    ann_id: int,
    req: AnnotationUpdateRequest,
    db: AsyncSession = Depends(get_db),
):
    """更新标注"""
    result = await db.execute(
        select(LiteratureAnnotation).where(
            LiteratureAnnotation.id == ann_id,
            LiteratureAnnotation.paper_id == paper_id,
        )
    )
    ann = result.scalar_one_or_none()
    if not ann:
        raise HTTPException(status_code=404, detail="标注不存在")
    kw = req.model_dump(exclude_none=True)
    if "rect" in kw:
        kw["rect"] = _rect_for_storage(kw["rect"])
    for k, v in kw.items():
        setattr(ann, k, v)
    ann.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(ann)
    return {
        "id": ann.id,
        "annotation_type": ann.annotation_type,
        "page_number": ann.page_number,
        "rect": _rect_for_response(ann.rect),
        "color": ann.color,
        "content": ann.content,
        "selected_text": ann.selected_text,
    }


@router.delete(
    "/papers/{paper_id}/annotations/{ann_id}",
    status_code=204,
    responses={404: {"model": ErrorResponse}},
)
async def delete_annotation(paper_id: int, ann_id: int, db: AsyncSession = Depends(get_db)):
    """删除标注"""
    result = await db.execute(
        select(LiteratureAnnotation).where(
            LiteratureAnnotation.id == ann_id,
            LiteratureAnnotation.paper_id == paper_id,
        )
    )
    ann = result.scalar_one_or_none()
    if not ann:
        raise HTTPException(status_code=404, detail="标注不存在")
    await db.delete(ann)
    await db.commit()


@router.put(
    "/papers/{paper_id}",
    response_model=PaperResponse,
    responses={400: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
)
async def update_paper(paper_id: int, req: PaperUpdateRequest, db: AsyncSession = Depends(get_db)):
    """更新文献元数据"""
    result = await db.execute(select(LiteraturePaper).where(LiteraturePaper.id == paper_id))
    paper = result.scalar_one_or_none()
    if not paper:
        raise HTTPException(status_code=404, detail="文献不存在")
    if paper.deleted_at:
        raise HTTPException(status_code=400, detail="已删除的文献不能更新")

    kw = req.model_dump(exclude_none=True)
    if "collection_id" in kw:
        await _validate_collection_exists(db, kw["collection_id"])
    if "authors" in kw:
        kw["authors"] = __json_authors(kw["authors"])
    if "keywords" in kw:
        kw["keywords"] = __json_list(kw["keywords"])
    if "tag_ids" in kw:
        tag_ids = kw.pop("tag_ids")
        await _validate_tag_ids_exist(db, tag_ids)
        await _sync_tags(db, paper_id, tag_ids)

    for k, v in kw.items():
        setattr(paper, k, v)
    paper.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(paper)
    return _paper_response(paper)


@router.delete("/papers/{paper_id}", status_code=204)
async def soft_delete_paper(paper_id: int, db: AsyncSession = Depends(get_db)):
    """软删除（移入回收站）"""
    result = await db.execute(select(LiteraturePaper).where(LiteraturePaper.id == paper_id))
    paper = result.scalar_one_or_none()
    if not paper:
        raise HTTPException(status_code=404, detail="文献不存在")
    if paper.deleted_at:
        return

    now = datetime.utcnow()
    paper.deleted_at = now
    paper.deleted_at_ts = int(now.timestamp())
    paper.updated_at = now
    await db.commit()


@router.post("/papers/{paper_id}/restore")
async def restore_paper(paper_id: int, db: AsyncSession = Depends(get_db)):
    """从回收站恢复"""
    result = await db.execute(select(LiteraturePaper).where(LiteraturePaper.id == paper_id))
    paper = result.scalar_one_or_none()
    if not paper:
        raise HTTPException(status_code=404, detail="文献不存在")
    paper.deleted_at = None
    paper.deleted_at_ts = None
    paper.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(paper)
    return _paper_response(paper)


@router.delete(
    "/papers/{paper_id}/permanent",
    status_code=204,
    responses={400: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
)
async def permanent_delete_paper(paper_id: int, db: AsyncSession = Depends(get_db)):
    """永久删除（仅对已在回收站的文献有效），清理 PDF、附件、向量 chunk"""
    from sqlalchemy import text

    result = await db.execute(select(LiteraturePaper).where(LiteraturePaper.id == paper_id))
    paper = result.scalar_one_or_none()
    if not paper:
        raise HTTPException(status_code=404, detail="文献不存在")
    if not paper.deleted_at:
        raise HTTPException(status_code=400, detail="只能永久删除回收站中的文献")

    base_path = Path(settings.app_data_root)
    if paper.pdf_path:
        (base_path / paper.pdf_path.lstrip("/")).unlink(missing_ok=True)

    att_result = await db.execute(
        select(LiteratureAttachment).where(LiteratureAttachment.paper_id == paper_id)
    )
    for att in att_result.scalars().all():
        (base_path / att.file_path.lstrip("/")).unlink(missing_ok=True)

    chunk_result = await db.execute(select(PaperChunk.id).where(PaperChunk.paper_id == paper_id))
    chunk_ids = [r[0] for r in chunk_result.fetchall()]
    if chunk_ids:
        ph = ",".join(str(i) for i in chunk_ids)
        await db.execute(
            text(
                "INSERT INTO paper_fts(paper_fts, rowid) SELECT 'delete', rowid FROM paper_fts WHERE chunk_id IN (%s)"
                % ph
            )
        )
    await db.execute(delete(PaperChunk).where(PaperChunk.paper_id == paper_id))
    await db.delete(paper)
    await db.commit()


@router.post("/papers/upload")
async def upload_paper(background_tasks: BackgroundTasks, file: UploadFile, db: AsyncSession = Depends(get_db)):
    """上传文献 PDF，后台解析并索引到 paper_chunks + paper_fts"""
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    ext = Path(file.filename or "").suffix or ".pdf"
    if ext.lower() != ".pdf":
        raise HTTPException(status_code=400, detail="仅支持 PDF")
    path = UPLOAD_DIR / f"{os.urandom(8).hex()}{ext}"
    with open(path, "wb") as f:
        shutil.copyfileobj(file.file, f)
    rel_path = str(path.relative_to(settings.app_data_root))
    lock = get_domain_lock("literature")
    async with lock:
        paper = LiteraturePaper(
            user_id=1,
            title=file.filename or "未命名",
            pdf_path=rel_path,
            pdf_indexed=0,
            import_source="pdf",
            fulltext_status="pending",
        )
        db.add(paper)
        await db.commit()
        await db.refresh(paper)
    background_tasks.add_task(_index_paper_task, paper.id, rel_path)
    return {"id": paper.id, "title": paper.title, "status": "indexing"}


# --- 文件导入 ---

@router.post("/papers/import")
async def import_papers(
    file: UploadFile,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """文件导入（RIS/BibTeX/PDF）"""
    from app.services.literature.importers import RISImporter, BibTeXImporter, PDFMetadataImporter

    content = await file.read()
    filename = (file.filename or "").lower()
    papers_data: list[dict] = []

    if filename.endswith(".pdf"):
        UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        path = UPLOAD_DIR / f"{os.urandom(8).hex()}.pdf"
        path.write_bytes(content)
        rel_path = str(path.relative_to(settings.app_data_root))
        meta = PDFMetadataImporter().extract(path)
        paper = LiteraturePaper(
            user_id=1,
            title=meta.get("title") or file.filename or "未命名",
            authors=__json_authors(meta.get("authors", [])),
            pdf_path=rel_path,
            pdf_indexed=0,
            import_source="pdf",
            fulltext_status="pending",
        )
        db.add(paper)
        await db.commit()
        await db.refresh(paper)
        background_tasks.add_task(_index_paper_task, paper.id, rel_path)
        return {"success": 1, "skipped": 0, "failed": 0, "paper_ids": [paper.id], "errors": []}
    elif filename.endswith(".ris"):
        papers_data = RISImporter().parse(content.decode("utf-8", errors="replace"))
    elif filename.endswith((".bib", ".bibtex")):
        papers_data = BibTeXImporter().parse(content.decode("utf-8", errors="replace"))
    else:
        raise HTTPException(status_code=415, detail="支持 PDF / RIS / BibTeX")

    if not papers_data:
        return {"success": 0, "skipped": 0, "failed": 0, "paper_ids": [], "errors": []}

    source = "ris" if filename.endswith(".ris") else "bibtex"
    if len(papers_data) > IMPORT_ASYNC_THRESHOLD:
        task_id = str(uuid.uuid4())
        _import_tasks[task_id] = {
            "task_id": task_id,
            "status": "queued",
            "total": len(papers_data),
            "source": source,
            "created_at": datetime.utcnow().isoformat(),
        }
        background_tasks.add_task(_run_import_task, task_id, papers_data, source)
        return {"task_id": task_id, "total": len(papers_data), "status": "queued"}

    result = await _bulk_import_records(papers_data, source=source)
    pids = result.get("paper_ids") or []
    if pids:
        background_tasks.add_task(resolve_fulltext_batch, pids)
    return result


@router.get("/import-tasks/{task_id}")
@router.get("/papers/import-tasks/{task_id}")
async def get_import_task(task_id: str):
    """查询导入任务状态（大批量异步导入）"""
    task = _import_tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="导入任务不存在")
    return task


@router.post("/papers/cleanup-trash")
async def cleanup_trash(db: AsyncSession = Depends(get_db)):
    """清理超过 30 天的回收站文献（可由 cron 定时调用）"""
    from app.services.literature.trash_cleanup import cleanup_expired_trash

    affected = await cleanup_expired_trash(db)
    return {"success": True, "deleted": affected}


# --- 集合 ---

async def _get_collection_depth(db: AsyncSession, parent_id: int) -> int:
    depth = 0
    current = parent_id
    while current:
        r = await db.execute(select(LiteratureCollection.parent_id).where(LiteratureCollection.id == current))
        row = r.fetchone()
        if not row:
            break
        current = row[0]
        depth += 1
        if depth >= 3:
            break
    return depth


@router.get("/collections/tree", response_model=list[CollectionTreeItem])
async def get_collection_tree(db: AsyncSession = Depends(get_db)):
    """树形集合列表"""
    from sqlalchemy import text
    result = await db.execute(select(LiteratureCollection).order_by(LiteratureCollection.sort_order, LiteratureCollection.id))
    colls = result.scalars().all()
    cnt_result = await db.execute(text(
        "SELECT collection_id, COUNT(*) FROM literature_papers "
        "WHERE deleted_at IS NULL AND collection_id IS NOT NULL GROUP BY collection_id"
    ))
    counts = dict(cnt_result.fetchall())

    def build_tree(parent_id: int | None) -> list[dict]:
        out = []
        for c in colls:
            if (c.parent_id is None and parent_id is None) or (c.parent_id == parent_id):
                out.append({
                    "id": c.id,
                    "name": c.name,
                    "parent_id": c.parent_id,
                    "color": c.color,
                    "icon": c.icon,
                    "sort_order": c.sort_order,
                    "count": counts.get(c.id, 0),
                    "children": build_tree(c.id),
                })
        return out

    return build_tree(None)


@router.post("/collections", response_model=CollectionResponse, status_code=201)
async def create_collection(req: CollectionCreateRequest, db: AsyncSession = Depends(get_db)):
    """创建集合"""
    if req.parent_id:
        depth = await _get_collection_depth(db, req.parent_id)
        if depth >= 3:
            raise HTTPException(status_code=400, detail="集合最多支持3层嵌套")
    coll = LiteratureCollection(**req.model_dump())
    db.add(coll)
    await db.commit()
    await db.refresh(coll)
    return {"id": coll.id, "name": coll.name, "parent_id": coll.parent_id, "color": coll.color, "icon": coll.icon}


@router.put("/collections/{coll_id}", response_model=CollectionResponse, responses={404: {"model": ErrorResponse}})
async def update_collection(coll_id: int, req: CollectionUpdateRequest, db: AsyncSession = Depends(get_db)):
    """更新集合"""
    result = await db.execute(select(LiteratureCollection).where(LiteratureCollection.id == coll_id))
    coll = result.scalar_one_or_none()
    if not coll:
        raise HTTPException(status_code=404, detail="集合不存在")
    if req.parent_id is not None:
        if req.parent_id == coll_id:
            raise HTTPException(status_code=400, detail="父集合不能为自身")
        depth = await _get_collection_depth(db, req.parent_id)
        if depth >= 3:
            raise HTTPException(status_code=400, detail="集合最多支持3层嵌套")
        coll.parent_id = req.parent_id
    if req.name is not None:
        coll.name = req.name
    if req.color is not None:
        coll.color = req.color
    if req.icon is not None:
        coll.icon = req.icon
    if req.sort_order is not None:
        coll.sort_order = req.sort_order
    await db.commit()
    await db.refresh(coll)
    return {"id": coll.id, "name": coll.name, "parent_id": coll.parent_id, "color": coll.color, "icon": coll.icon}


@router.delete("/collections/{coll_id}", status_code=204, responses={404: {"model": ErrorResponse}})
async def delete_collection(coll_id: int, db: AsyncSession = Depends(get_db)):
    """删除集合（文献移至未分类，子集合提升为同级）"""
    result = await db.execute(select(LiteratureCollection).where(LiteratureCollection.id == coll_id))
    coll = result.scalar_one_or_none()
    if not coll:
        raise HTTPException(status_code=404, detail="集合不存在")
    await db.execute(update(LiteraturePaper).where(LiteraturePaper.collection_id == coll_id).values(collection_id=None))
    await db.execute(update(LiteratureCollection).where(LiteratureCollection.parent_id == coll_id).values(parent_id=coll.parent_id))
    await db.delete(coll)
    await db.commit()


# --- 标签 ---

@router.get("/tags", response_model=list[TagListItemResponse])
async def list_tags(db: AsyncSession = Depends(get_db)):
    """标签列表（含文献数）"""
    from sqlalchemy import text
    result = await db.execute(text("""
        SELECT t.id, t.name, t.color, COUNT(pt.paper_id) as paper_count
        FROM literature_tags t
        LEFT JOIN literature_paper_tags pt ON t.id = pt.tag_id
        LEFT JOIN literature_papers p ON pt.paper_id = p.id AND p.deleted_at IS NULL
        GROUP BY t.id ORDER BY paper_count DESC
    """))
    rows = result.fetchall()
    return [{"id": r[0], "name": r[1], "color": r[2], "paper_count": r[3] or 0} for r in rows]


@router.post("/tags", response_model=TagResponse, status_code=201)
async def create_tag(req: TagCreateRequest, db: AsyncSession = Depends(get_db)):
    """创建标签"""
    tag = LiteratureTag(name=req.name.strip(), color=req.color or "#1D9E75")
    db.add(tag)
    await db.commit()
    await db.refresh(tag)
    return {"id": tag.id, "name": tag.name, "color": tag.color}


@router.put("/tags/{tag_id}", response_model=TagResponse, responses={404: {"model": ErrorResponse}})
async def update_tag(tag_id: int, req: TagUpdateRequest, db: AsyncSession = Depends(get_db)):
    """更新标签（名称/颜色）"""
    result = await db.execute(select(LiteratureTag).where(LiteratureTag.id == tag_id))
    tag = result.scalar_one_or_none()
    if not tag:
        raise HTTPException(status_code=404, detail="标签不存在")
    if req.name is not None:
        tag.name = req.name.strip()
    if req.color is not None:
        tag.color = req.color
    await db.commit()
    await db.refresh(tag)
    return {"id": tag.id, "name": tag.name, "color": tag.color}


@router.delete("/tags/{tag_id}", status_code=204, responses={404: {"model": ErrorResponse}})
async def delete_tag(tag_id: int, db: AsyncSession = Depends(get_db)):
    """删除标签（关联自动解除）"""
    result = await db.execute(select(LiteratureTag).where(LiteratureTag.id == tag_id))
    tag = result.scalar_one_or_none()
    if not tag:
        raise HTTPException(status_code=404, detail="标签不存在")
    await db.delete(tag)
    await db.commit()


@router.patch("/papers/{paper_id}/read-status", response_model=ReadStatusResponse)
async def update_read_status(
    paper_id: int,
    req: ReadStatusRequest,
    db: AsyncSession = Depends(get_db),
):
    """更新阅读状态"""
    status = req.status
    result = await db.execute(select(LiteraturePaper).where(LiteraturePaper.id == paper_id))
    paper = result.scalar_one_or_none()
    if not paper:
        raise HTTPException(status_code=404, detail="文献不存在")
    paper.read_status = status
    paper.updated_at = datetime.utcnow()
    await db.commit()
    return {"read_status": status}


@router.patch("/papers/{paper_id}/tags")
async def update_paper_tags(
    paper_id: int, req: UpdateTagsRequest, db: AsyncSession = Depends(get_db),
):
    """更新文献标签（覆盖式）"""
    result = await db.execute(select(LiteraturePaper).where(LiteraturePaper.id == paper_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="文献不存在")
    await _validate_tag_ids_exist(db, req.tag_ids)
    await db.execute(delete(LiteraturePaperTag).where(LiteraturePaperTag.paper_id == paper_id))
    for tag_id in req.tag_ids:
        db.add(LiteraturePaperTag(paper_id=paper_id, tag_id=tag_id))
    await db.commit()
    return {"tag_ids": req.tag_ids}


@router.get("/articles/{article_id}/bindings")
async def list_article_bindings(
    article_id: int,
    section_id: int | None = None,
    scope: Literal["article", "section"] | None = None,
    db: AsyncSession = Depends(get_db),
):
    """查看文章/章节绑定文献。scope=article 仅文章级；scope=section 且 section_id 指定时按章节过滤"""
    art = await db.execute(select(Article.id).where(Article.id == article_id))
    if not art.first():
        raise HTTPException(status_code=404, detail="文章不存在")
    stmt = select(ArticleLiteratureBinding, LiteraturePaper).join(
        LiteraturePaper, ArticleLiteratureBinding.paper_id == LiteraturePaper.id
    ).where(ArticleLiteratureBinding.article_id == article_id)
    if scope == "article":
        stmt = stmt.where(ArticleLiteratureBinding.section_id.is_(None))
    elif section_id is not None:
        stmt = stmt.where(ArticleLiteratureBinding.section_id == section_id)
    stmt = stmt.order_by(ArticleLiteratureBinding.priority.asc(), ArticleLiteratureBinding.id.asc())
    result = await db.execute(stmt)
    rows = result.fetchall()
    return {
        "items": [
            {
                "binding_id": b.id,
                "article_id": b.article_id,
                "section_id": b.section_id,
                "paper_id": p.id,
                "priority": b.priority,
                "title": p.title,
                "doi": p.doi,
                "year": p.year,
            }
            for b, p in rows
        ]
    }


@router.post("/articles/{article_id}/bindings", status_code=201)
async def bind_papers_to_article(
    article_id: int,
    req: BindPapersRequest,
    db: AsyncSession = Depends(get_db),
):
    """绑定文献到文章（可选绑定到章节）"""
    art = await db.execute(select(Article.id).where(Article.id == article_id))
    if not art.first():
        raise HTTPException(status_code=404, detail="文章不存在")
    if req.section_id is not None:
        sec = await db.execute(
            select(ArticleSection.id).where(
                ArticleSection.id == req.section_id,
                ArticleSection.article_id == article_id,
            )
        )
        if not sec.first():
            raise HTTPException(status_code=404, detail="章节不存在")
    if not req.paper_ids:
        raise HTTPException(status_code=400, detail="paper_ids 不能为空")

    created = 0
    for paper_id in req.paper_ids:
        existing = await db.execute(
            select(ArticleLiteratureBinding.id).where(
                ArticleLiteratureBinding.article_id == article_id,
                ArticleLiteratureBinding.section_id == req.section_id,
                ArticleLiteratureBinding.paper_id == paper_id,
            )
        )
        if existing.first():
            continue
        db.add(ArticleLiteratureBinding(
            article_id=article_id,
            section_id=req.section_id,
            paper_id=paper_id,
            priority=req.priority,
        ))
        created += 1
    await db.commit()
    return {"created": created}


@router.get("/articles/{article_id}/external-refs")
async def list_external_refs(
    article_id: int,
    section_id: int | None = None,
    scope: Literal["article", "section"] | None = None,
    db: AsyncSession = Depends(get_db),
):
    """查看文章/章节外部引用。scope=article 仅文章级；scope=section 且 section_id 指定时按章节过滤"""
    art = await db.execute(select(Article.id).where(Article.id == article_id))
    if not art.first():
        raise HTTPException(status_code=404, detail="文章不存在")
    stmt = select(ArticleExternalReference).where(ArticleExternalReference.article_id == article_id)
    if scope == "article":
        stmt = stmt.where(ArticleExternalReference.section_id.is_(None))
    elif section_id is not None:
        stmt = stmt.where(ArticleExternalReference.section_id == section_id)
    stmt = stmt.order_by(ArticleExternalReference.id.asc())
    rows = (await db.execute(stmt)).scalars().all()
    items = []
    for r in rows:
        try:
            authors = json.loads(r.authors) if isinstance(r.authors, str) else (r.authors or [])
        except Exception:
            authors = []
        items.append({
            "ref_id": r.id,
            "article_id": r.article_id,
            "section_id": r.section_id,
            "source": r.source,
            "source_id": r.source_id,
            "doi": r.doi,
            "pmid": r.pmid,
            "title": r.title,
            "authors": authors,
            "journal": r.journal,
            "year": r.year,
            "url": r.url,
            "abstract": r.abstract,
        })
    return {"items": items}


@router.post("/articles/{article_id}/external-refs", status_code=201)
async def bind_external_refs(
    article_id: int,
    req: BindExternalRefsRequest,
    db: AsyncSession = Depends(get_db),
):
    """绑定外部引用到文章（无需先入库）"""
    art = await db.execute(select(Article.id).where(Article.id == article_id))
    if not art.first():
        raise HTTPException(status_code=404, detail="文章不存在")
    if req.section_id is not None:
        sec = await db.execute(
            select(ArticleSection.id).where(
                ArticleSection.id == req.section_id,
                ArticleSection.article_id == article_id,
            )
        )
        if not sec.first():
            raise HTTPException(status_code=404, detail="章节不存在")
    if not req.items:
        raise HTTPException(status_code=400, detail="items 不能为空")

    created = 0
    for item in req.items:
        # 同一 article/section/source/source_id 或 doi/pmid 去重
        stmt = select(ArticleExternalReference.id).where(
            ArticleExternalReference.article_id == article_id,
            ArticleExternalReference.section_id == req.section_id,
        )
        if item.source_id:
            stmt = stmt.where(ArticleExternalReference.source == item.source, ArticleExternalReference.source_id == item.source_id)
        elif item.doi:
            stmt = stmt.where(ArticleExternalReference.doi == item.doi.lower().strip())
        elif item.pmid:
            stmt = stmt.where(ArticleExternalReference.pmid == item.pmid.strip())
        else:
            stmt = stmt.where(ArticleExternalReference.title == item.title)
        existing = await db.execute(stmt)
        if existing.first():
            continue
        db.add(ArticleExternalReference(
            article_id=article_id,
            section_id=req.section_id,
            source=item.source,
            source_id=item.source_id or "",
            doi=(item.doi.lower().strip() if item.doi else None),
            pmid=(item.pmid.strip() if item.pmid else None),
            title=item.title,
            authors=json.dumps([a.model_dump() for a in item.authors], ensure_ascii=False),
            journal=item.journal or "",
            year=item.year,
            url=item.url or "",
            abstract=item.abstract or "",
        ))
        created += 1
    await db.commit()
    return {"created": created}


@router.delete("/articles/{article_id}/external-refs/{ref_id}", status_code=204)
async def delete_external_ref(
    article_id: int,
    ref_id: int,
    db: AsyncSession = Depends(get_db),
):
    """删除外部引用绑定"""
    result = await db.execute(
        select(ArticleExternalReference).where(
            ArticleExternalReference.id == ref_id,
            ArticleExternalReference.article_id == article_id,
        )
    )
    ref = result.scalar_one_or_none()
    if not ref:
        raise HTTPException(status_code=404, detail="引用不存在")
    await db.delete(ref)
    await db.commit()


@router.delete("/articles/{article_id}/bindings/{binding_id}", status_code=204)
async def delete_article_binding(
    article_id: int,
    binding_id: int,
    db: AsyncSession = Depends(get_db),
):
    """删除绑定"""
    result = await db.execute(
        select(ArticleLiteratureBinding).where(
            ArticleLiteratureBinding.id == binding_id,
            ArticleLiteratureBinding.article_id == article_id,
        )
    )
    binding = result.scalar_one_or_none()
    if not binding:
        raise HTTPException(status_code=404, detail="绑定不存在")
    await db.delete(binding)
    await db.commit()


@router.get("/papers/{paper_id}/bindings")
async def list_paper_bindings(
    paper_id: int,
    db: AsyncSession = Depends(get_db),
):
    """查看某篇文献被哪些文章/章节绑定引用。"""
    p = await db.execute(select(LiteraturePaper.id).where(LiteraturePaper.id == paper_id))
    if not p.first():
        raise HTTPException(status_code=404, detail="文献不存在")

    stmt = (
        select(ArticleLiteratureBinding, Article, ArticleSection)
        .join(Article, ArticleLiteratureBinding.article_id == Article.id)
        .outerjoin(ArticleSection, ArticleLiteratureBinding.section_id == ArticleSection.id)
        .where(ArticleLiteratureBinding.paper_id == paper_id)
        .order_by(ArticleLiteratureBinding.created_at.desc(), ArticleLiteratureBinding.id.desc())
    )
    result = await db.execute(stmt)
    rows = result.fetchall()
    return {
        "items": [
            {
                "binding_id": b.id,
                "article_id": a.id,
                "article_title": a.title or a.topic or f"文章#{a.id}",
                "section_id": s.id if s else None,
                "section_title": s.title if s else None,
                "created_at": b.created_at,
            }
            for b, a, s in rows
        ]
    }
