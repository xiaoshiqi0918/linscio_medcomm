"""
文献解析与 FTS5 索引
PDF 解析 → 分块 → paper_chunks + paper_fts
支持结构化（PMC XML 分段）和纯文本两种入口。
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING

from sqlalchemy import text, delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.paper import PaperChunk
from app.core.config import settings

if TYPE_CHECKING:
    from app.services.literature.fulltext_resolver import ParsedPaper


CHUNK_SIZE = 500
CHUNK_OVERLAP = 50


def _infer_chunk_type(chunk_index: int, total_chunks: int) -> str:
    if total_chunks <= 0:
        return "background"
    ratio = chunk_index / max(total_chunks, 1)
    if ratio < 0.2:
        return "background"
    if ratio < 0.4:
        return "methods"
    if ratio < 0.7:
        return "results"
    return "conclusion"


async def _clear_old_chunks(paper_id: int, db: AsyncSession) -> None:
    """删除旧 chunks + FTS 索引"""
    from app.services.vector.fts5 import ensure_paper_fts_tables
    await ensure_paper_fts_tables(db)

    old_result = await db.execute(select(PaperChunk.id).where(PaperChunk.paper_id == paper_id))
    old_ids = [r[0] for r in old_result.fetchall()]
    if old_ids:
        ph = ",".join(str(i) for i in old_ids)
        await db.execute(
            text(
                f"INSERT INTO paper_fts(paper_fts, rowid) SELECT 'delete', rowid FROM paper_fts WHERE chunk_id IN ({ph})"
            )
        )
        await db.execute(delete(PaperChunk).where(PaperChunk.paper_id == paper_id))
        await db.flush()


async def _insert_fts(paper_id: int, db: AsyncSession) -> None:
    result = await db.execute(
        select(PaperChunk.id, PaperChunk.chunk_text)
        .where(PaperChunk.paper_id == paper_id)
        .order_by(PaperChunk.chunk_index)
    )
    for row in result.fetchall():
        cid, content = row[0], (row[1] or "")[:10000]
        await db.execute(
            text("INSERT INTO paper_fts(chunk_id, content) VALUES (:cid, :content)"),
            {"cid": cid, "content": content},
        )


async def _replace_paper_chunks_from_text(paper_id: int, text_content: str, db: AsyncSession) -> int:
    """用纯文本重建某篇文献的 chunk + FTS。不 commit。返回 chunk 数。"""
    stripped = (text_content or "").strip()
    if not stripped:
        return 0

    await _clear_old_chunks(paper_id, db)

    chunks = _split_chunks(stripped)
    total = len(chunks)
    for i, chunk_text in enumerate(chunks):
        ct = _infer_chunk_type(i, total)
        chunk = PaperChunk(paper_id=paper_id, chunk_index=i, chunk_type=ct, chunk_text=chunk_text)
        db.add(chunk)
        await db.flush()

    await _insert_fts(paper_id, db)
    return len(chunks)


async def _replace_paper_chunks_structured(paper_id: int, parsed: ParsedPaper, db: AsyncSession) -> int:
    """用结构化 ParsedPaper 重建 chunks，保留 section/chunk_type。不 commit。"""
    await _clear_old_chunks(paper_id, db)

    chunk_index = 0

    if parsed.abstract:
        db.add(PaperChunk(
            paper_id=paper_id, chunk_index=chunk_index,
            chunk_type="abstract", section="Abstract",
            chunk_text=parsed.abstract,
        ))
        await db.flush()
        chunk_index += 1

    for sec in parsed.sections:
        sec_text = sec.get("text", "")
        sec_title = sec.get("section", "")
        sec_type = sec.get("chunk_type", "body")

        sub_chunks = _split_chunks(sec_text)
        for sub_text in sub_chunks:
            db.add(PaperChunk(
                paper_id=paper_id, chunk_index=chunk_index,
                chunk_type=sec_type, section=sec_title,
                chunk_text=sub_text,
            ))
            await db.flush()
            chunk_index += 1

    if parsed.references:
        ref_text = "\n".join(parsed.references)
        db.add(PaperChunk(
            paper_id=paper_id, chunk_index=chunk_index,
            chunk_type="references", section="References",
            chunk_text=ref_text,
        ))
        await db.flush()
        chunk_index += 1

    if chunk_index == 0 and parsed.raw_text:
        return await _replace_paper_chunks_from_text(paper_id, parsed.raw_text, db)

    await _insert_fts(paper_id, db)
    return chunk_index


async def parse_and_index_paper(paper_id: int, file_path: str, db: AsyncSession) -> tuple[int, str]:
    """
    解析文献 PDF 并写入 paper_chunks + paper_fts
    返回 (chunk_count, status)
    """
    full_path = Path(settings.app_data_root) / file_path.lstrip("/")
    if not full_path.exists():
        return 0, "failed"

    try:
        text_content = _extract_pdf_text(full_path)
    except Exception:
        return 0, "failed"

    if not text_content.strip():
        return 0, "done"

    n = await _replace_paper_chunks_from_text(paper_id, text_content, db)
    await db.commit()
    return n, "done"


async def index_plain_fulltext_for_paper(paper_id: int, plain_text: str, db: AsyncSession) -> tuple[int, str]:
    """将已获取的全文纯文本写入 chunk + FTS（如 PMC OA）。返回 (chunk_count, status)。"""
    n = await _replace_paper_chunks_from_text(paper_id, plain_text, db)
    if n <= 0:
        return 0, "empty"
    await db.commit()
    return n, "done"


async def index_structured_fulltext_for_paper(
    paper_id: int, parsed: ParsedPaper, db: AsyncSession,
) -> tuple[int, str]:
    """将结构化解析结果写入 chunk + FTS。返回 (chunk_count, status)。"""
    n = await _replace_paper_chunks_structured(paper_id, parsed, db)
    if n <= 0:
        return 0, "empty"
    await db.commit()
    return n, "done"


def _extract_pdf_text(path: Path) -> str:
    try:
        from pypdf import PdfReader

        reader = PdfReader(str(path))
        return "\n".join(p.extract_text() or "" for p in reader.pages)
    except Exception:
        return ""


def _split_chunks(text_str: str) -> list[str]:
    paragraphs = re.split(r"\n\s*\n", text_str)
    chunks: list[str] = []
    current: list[str] = []
    length = 0
    for p in paragraphs:
        p = p.strip()
        if not p:
            continue
        if length + len(p) > CHUNK_SIZE and current:
            chunks.append("\n\n".join(current))
            overlap: list[str] = []
            overlap_len = 0
            for s in reversed(current):
                if overlap_len + len(s) <= CHUNK_OVERLAP:
                    overlap.insert(0, s)
                    overlap_len += len(s)
                else:
                    break
            current = overlap
            length = overlap_len
        current.append(p)
        length += len(p)
    if current:
        chunks.append("\n\n".join(current))
    return chunks if chunks else [text_str[:CHUNK_SIZE]]
