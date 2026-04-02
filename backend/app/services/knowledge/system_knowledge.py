"""
系统内置知识自动索引
启动时扫描 prompt-example/system-knowledge/ 目录下的 .txt 文件，
对尚未入库的文件自动创建 KnowledgeDoc(is_system=True) 并索引。
这些文档不在前端知识库列表中显示，但 RAG 检索可以命中。
"""
import logging
from pathlib import Path

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.models.knowledge import KnowledgeDoc

logger = logging.getLogger("linscio.system_knowledge")

_PROJECT_ROOT = Path(__file__).resolve().parents[4]
SYSTEM_KNOWLEDGE_DIR = _PROJECT_ROOT / "prompt-example" / "system-knowledge"


async def index_system_knowledge():
    """扫描并索引系统内置知识文档（幂等，已存在的跳过）"""
    if not SYSTEM_KNOWLEDGE_DIR.exists():
        return

    txt_files = sorted(SYSTEM_KNOWLEDGE_DIR.glob("*.txt"))
    if not txt_files:
        return

    async with AsyncSessionLocal() as db:
        for ddl in [
            "ALTER TABLE knowledge_docs ADD COLUMN is_system BOOLEAN DEFAULT 0",
            "ALTER TABLE knowledge_docs ADD COLUMN specialty VARCHAR(50)",
            "ALTER TABLE knowledge_docs ADD COLUMN source VARCHAR(20) DEFAULT 'user'",
            "ALTER TABLE knowledge_chunks ADD COLUMN specialty VARCHAR(50)",
        ]:
            try:
                await db.execute(text(ddl))
                await db.commit()
            except Exception:
                await db.rollback()

        for txt_file in txt_files:
            name = txt_file.stem
            result = await db.execute(
                select(KnowledgeDoc).where(
                    KnowledgeDoc.name == name,
                    KnowledgeDoc.is_system == True,
                )
            )
            existing = result.scalar_one_or_none()
            if existing and existing.status == "done":
                continue

            if existing:
                doc_id = existing.id
                existing.status = "indexing"
                await db.commit()
            else:
                doc = KnowledgeDoc(
                    user_id=1,
                    name=name,
                    file_path=str(txt_file),
                    status="indexing",
                    is_system=True,
                    source="system",
                )
                db.add(doc)
                await db.commit()
                await db.refresh(doc)
                doc_id = doc.id

            try:
                from app.services.knowledge.indexer import parse_and_index
                _count, status = await parse_and_index(doc_id, str(txt_file), db)
                result2 = await db.execute(
                    select(KnowledgeDoc).where(KnowledgeDoc.id == doc_id)
                )
                d = result2.scalar_one_or_none()
                if d:
                    d.status = status
                    await db.commit()
                logger.info(f"[system-knowledge] indexed '{name}': {_count} chunks, status={status}")
            except Exception as e:
                logger.warning(f"[system-knowledge] failed to index '{name}': {e}")
                result3 = await db.execute(
                    select(KnowledgeDoc).where(KnowledgeDoc.id == doc_id)
                )
                d = result3.scalar_one_or_none()
                if d:
                    d.status = "failed"
                    await db.commit()
