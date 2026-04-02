"""回收站过期清理：超过 30 天的文献永久删除"""
import time
from pathlib import Path
from sqlalchemy import select, delete, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.literature import LiteraturePaper, LiteratureAttachment
from app.models.paper import PaperChunk

TRASH_RETENTION_DAYS = 30


async def cleanup_expired_trash(db: AsyncSession) -> int:
    """
    永久删除超过保留期的回收站文献。
    返回删除的文献数量。
    """
    cutoff_ts = int(time.time()) - TRASH_RETENTION_DAYS * 86400
    result = await db.execute(
        select(LiteraturePaper)
        .where(LiteraturePaper.deleted_at.is_not(None))
        .where(LiteraturePaper.deleted_at_ts < cutoff_ts)
    )
    papers = result.scalars().all()
    base_path = Path(settings.app_data_root)

    for paper in papers:
        if paper.pdf_path:
            (base_path / paper.pdf_path.lstrip("/")).unlink(missing_ok=True)

        att_result = await db.execute(
            select(LiteratureAttachment).where(LiteratureAttachment.paper_id == paper.id)
        )
        for att in att_result.scalars().all():
            (base_path / att.file_path.lstrip("/")).unlink(missing_ok=True)

        chunk_result = await db.execute(select(PaperChunk.id).where(PaperChunk.paper_id == paper.id))
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
    return len(papers)
