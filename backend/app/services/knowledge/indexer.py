"""
知识库解析与 FTS5 索引
PDF/TXT/MD 解析 → 分块 → knowledge_chunks + knowledge_fts
"""
import re
from pathlib import Path
from sqlalchemy import text, delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.knowledge import KnowledgeChunk
from app.core.config import settings


CHUNK_SIZE = 500
CHUNK_OVERLAP = 50


async def parse_and_index(
    doc_id: int,
    file_path: str,
    db: AsyncSession,
    specialty: str | None = None,
) -> tuple[int, str]:
    """
    解析文档并写入 knowledge_chunks + knowledge_fts
    specialty: 学科标记，会冗余写入每个 chunk 以加速检索过滤
    返回 (chunk_count, status)
    """
    from app.services.vector.fts5 import ensure_fts_tables

    fp = Path(file_path)
    full_path = fp if fp.is_absolute() and fp.exists() else Path(settings.app_data_root) / file_path
    if not full_path.exists():
        return 0, "failed"

    try:
        text_content = _extract_text(full_path)
    except Exception:
        return 0, "failed"

    if not text_content.strip():
        return 0, "done"

    await ensure_fts_tables(db)

    # 删除该 doc 的旧 chunk 及 FTS5 记录
    old_result = await db.execute(select(KnowledgeChunk.id).where(KnowledgeChunk.doc_id == doc_id))
    old_ids = [r[0] for r in old_result.fetchall()]
    if old_ids:
        placeholders = ",".join(str(i) for i in old_ids)
        await db.execute(text(
            f"INSERT INTO knowledge_fts(knowledge_fts, rowid) SELECT 'delete', rowid FROM knowledge_fts WHERE chunk_id IN ({placeholders})"
        ))
        await db.execute(delete(KnowledgeChunk).where(KnowledgeChunk.doc_id == doc_id))
        await db.flush()

    chunks = _split_chunks(text_content)
    for i, chunk_text in enumerate(chunks):
        chunk = KnowledgeChunk(doc_id=doc_id, chunk_index=i, content=chunk_text, specialty=specialty)
        db.add(chunk)
        await db.flush()

    # 写入 FTS5
    result = await db.execute(
        select(KnowledgeChunk.id, KnowledgeChunk.content).where(
            KnowledgeChunk.doc_id == doc_id
        ).order_by(KnowledgeChunk.chunk_index)
    )
    for row in result.fetchall():
        cid, content = row[0], (row[1] or "")[:10000]
        await db.execute(
            text("INSERT INTO knowledge_fts(chunk_id, content) VALUES (:cid, :content)"),
            {"cid": cid, "content": content},
        )
    await db.commit()
    return len(chunks), "done"


def _extract_text(path: Path) -> str:
    ext = path.suffix.lower()
    if ext == ".txt":
        return path.read_text(encoding="utf-8", errors="ignore")
    if ext in (".md", ".markdown"):
        return path.read_text(encoding="utf-8", errors="ignore")
    if ext == ".pdf":
        try:
            from pypdf import PdfReader
            reader = PdfReader(str(path))
            return "\n".join(p.extract_text() or "" for p in reader.pages)
        except Exception:
            return ""
    return ""


def _split_chunks(text: str) -> list[str]:
    paragraphs = re.split(r"\n\s*\n", text)
    chunks = []
    current = []
    length = 0
    for p in paragraphs:
        p = p.strip()
        if not p:
            continue
        if length + len(p) > CHUNK_SIZE and current:
            chunks.append("\n\n".join(current))
            overlap = []
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
    return chunks if chunks else [text[:CHUNK_SIZE]]
