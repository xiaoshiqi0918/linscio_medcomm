"""知识库 API"""
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import os
import shutil
from pathlib import Path

from app.core.database import AsyncSessionLocal, get_domain_lock
from app.models.knowledge import KnowledgeDoc
from app.core.config import settings

router = APIRouter()

UPLOAD_DIR = Path(settings.app_data_root) / "uploads" / "knowledge"


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session


async def _index_doc_task(doc_id: int, file_path: str):
    from app.services.knowledge.indexer import parse_and_index
    status = "failed"
    try:
        async with AsyncSessionLocal() as db:
            count, status = await parse_and_index(doc_id, file_path, db)
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(KnowledgeDoc).where(KnowledgeDoc.id == doc_id))
            doc = result.scalar_one_or_none()
            if doc:
                doc.status = status
                await db.commit()
    except Exception:
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(KnowledgeDoc).where(KnowledgeDoc.id == doc_id))
            doc = result.scalar_one_or_none()
            if doc:
                doc.status = "failed"
                await db.commit()


@router.get("/docs")
async def list_docs(db: AsyncSession = Depends(get_db)):
    """知识库文档列表（不含系统内置文档）"""
    result = await db.execute(
        select(KnowledgeDoc)
        .where((KnowledgeDoc.is_system == False) | (KnowledgeDoc.is_system.is_(None)))
        .order_by(KnowledgeDoc.created_at.desc())
    )
    items = result.scalars().all()
    return {"items": [{"id": d.id, "name": d.name, "status": d.status, "created_at": str(d.created_at)} for d in items]}


@router.post("/docs/upload")
async def upload_doc(background_tasks: BackgroundTasks, file: UploadFile, db: AsyncSession = Depends(get_db)):
    """上传知识库文档（PDF/TXT/MD），后台解析并索引到 FTS5"""
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    ext = Path(file.filename or "").suffix.lower()
    if ext not in (".pdf", ".txt", ".md", ".markdown"):
        raise HTTPException(status_code=400, detail="支持 PDF/TXT/MD")
    path = UPLOAD_DIR / f"{os.urandom(8).hex()}{ext}"
    with open(path, "wb") as f:
        shutil.copyfileobj(file.file, f)
    rel_path = str(path.relative_to(settings.app_data_root))
    lock = get_domain_lock("knowledge")
    async with lock:
        doc = KnowledgeDoc(user_id=1, name=file.filename or "未命名", file_path=rel_path, status="indexing")
        db.add(doc)
        await db.commit()
        await db.refresh(doc)
    background_tasks.add_task(_index_doc_task, doc.id, rel_path)
    return {"id": doc.id, "name": doc.name, "status": doc.status}


@router.get("/docs/{doc_id}/status")
async def get_doc_status(doc_id: int, db: AsyncSession = Depends(get_db)):
    """查询文档索引状态"""
    result = await db.execute(select(KnowledgeDoc).where(KnowledgeDoc.id == doc_id))
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="文档不存在")
    return {"id": doc.id, "name": doc.name, "status": doc.status}


@router.post("/docs/{doc_id}/retry")
async def retry_doc_index(background_tasks: BackgroundTasks, doc_id: int, db: AsyncSession = Depends(get_db)):
    """索引失败后重试解析与索引"""
    result = await db.execute(select(KnowledgeDoc).where(KnowledgeDoc.id == doc_id))
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="文档不存在")
    doc.status = "indexing"
    await db.commit()
    background_tasks.add_task(_index_doc_task, doc_id, doc.file_path)
    return {"id": doc.id, "status": doc.status}


@router.delete("/docs/{doc_id}")
async def delete_doc(doc_id: int, db: AsyncSession = Depends(get_db)):
    """删除文档及关联 chunks、FTS5 索引"""
    from app.models.knowledge import KnowledgeChunk
    from sqlalchemy import text, delete
    lock = get_domain_lock("knowledge")
    async with lock:
        result = await db.execute(select(KnowledgeDoc).where(KnowledgeDoc.id == doc_id))
        doc = result.scalar_one_or_none()
        if not doc:
            raise HTTPException(status_code=404)
        chunk_ids = [
            r[0] for r in (await db.execute(select(KnowledgeChunk.id).where(KnowledgeChunk.doc_id == doc_id))).fetchall()
        ]
        if chunk_ids:
            ph = ",".join(str(i) for i in chunk_ids)
            await db.execute(text(
                f"INSERT INTO knowledge_fts(knowledge_fts, rowid) SELECT 'delete', rowid FROM knowledge_fts WHERE chunk_id IN ({ph})"
            ))
        await db.execute(delete(KnowledgeChunk).where(KnowledgeChunk.doc_id == doc_id))
        await db.delete(doc)
        await db.commit()
    return {"ok": True}
