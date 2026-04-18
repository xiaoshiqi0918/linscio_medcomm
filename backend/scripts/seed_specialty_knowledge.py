"""
学科基础知识库种子脚本
========================
将 data/specialty_knowledge/*.json 中的结构化知识导入数据库。

每个 JSON 文件结构:
{
  "name": "心内科基础知识库",
  "specialty": "cardiology",
  "source": "system",
  "description": "...",
  "version": "2026.04",
  "chunks": [
    {
      "topic": "主题名",
      "chunk_type": "epidemiology|diagnosis|treatment|...",
      "content": "实际内容..."
    },
    ...
  ]
}

用法（在 backend 目录下）:
  python -m scripts.seed_specialty_knowledge
  python -m scripts.seed_specialty_knowledge --dry-run
  python -m scripts.seed_specialty_knowledge --file cardiology.json
  python -m scripts.seed_specialty_knowledge --rebuild  # 清空已有系统知识库后重新导入
"""
import argparse
import asyncio
import json
import logging
from pathlib import Path

from sqlalchemy import delete, select, text

from app.core.database import AsyncSessionLocal
from app.models.knowledge import KnowledgeDoc, KnowledgeChunk

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("specialty_knowledge")

DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "specialty_knowledge"


async def sync_fts_index(session, chunk_ids: list[int]):
    """将 chunk 同步到 knowledge_fts FTS5 虚拟表"""
    if not chunk_ids:
        return
    await session.execute(text(
        "CREATE VIRTUAL TABLE IF NOT EXISTS knowledge_fts USING fts5("
        "chunk_id UNINDEXED, content, tokenize='unicode61')"
    ))
    for cid in chunk_ids:
        chunk = await session.get(KnowledgeChunk, cid)
        if chunk:
            await session.execute(text(
                "INSERT INTO knowledge_fts(chunk_id, content) VALUES (:cid, :content)"
            ), {"cid": cid, "content": chunk.content or ""})


async def clear_system_knowledge(session):
    """清除所有 source='system' 的知识库数据"""
    docs = (await session.execute(
        select(KnowledgeDoc).where(KnowledgeDoc.source == "system")
    )).scalars().all()

    doc_ids = [d.id for d in docs]
    if not doc_ids:
        return 0

    chunk_ids = (await session.execute(
        select(KnowledgeChunk.id).where(KnowledgeChunk.doc_id.in_(doc_ids))
    )).scalars().all()

    if chunk_ids:
        for cid in chunk_ids:
            await session.execute(text(
                "DELETE FROM knowledge_fts WHERE chunk_id = :cid"
            ), {"cid": cid})
        await session.execute(
            delete(KnowledgeChunk).where(KnowledgeChunk.doc_id.in_(doc_ids))
        )

    await session.execute(
        delete(KnowledgeDoc).where(KnowledgeDoc.id.in_(doc_ids))
    )

    return len(doc_ids)


async def import_knowledge_file(
    session,
    file_path: Path,
    dry_run: bool = False,
) -> tuple[int, int]:
    """导入单个知识库 JSON 文件，返回 (doc_count, chunk_count)"""
    data = json.loads(file_path.read_text(encoding="utf-8"))

    name = data.get("name", file_path.stem)
    specialty = data.get("specialty")
    source = data.get("source", "system")
    chunks_data = data.get("chunks", [])

    if not chunks_data:
        logger.warning(f"No chunks in {file_path.name}, skipping")
        return 0, 0

    existing = (await session.execute(
        select(KnowledgeDoc).where(
            KnowledgeDoc.name == name,
            KnowledgeDoc.source == source,
        )
    )).scalars().first()

    if existing:
        logger.info(f"Knowledge doc '{name}' already exists (id={existing.id}), skipping")
        return 0, 0

    if dry_run:
        logger.info(f"[dry-run] Would import: {name} ({len(chunks_data)} chunks)")
        return 1, len(chunks_data)

    doc = KnowledgeDoc(
        name=name,
        file_path=str(file_path),
        status="done",
        is_system=True,
        specialty=specialty,
        source=source,
    )
    session.add(doc)
    await session.flush()
    doc_id = doc.id

    chunk_ids = []
    for idx, chunk_data in enumerate(chunks_data):
        topic = chunk_data.get("topic", "")
        chunk_type = chunk_data.get("chunk_type", "general")
        content = chunk_data.get("content", "")

        if not content.strip():
            continue

        header = f"【{topic}】\n" if topic else ""
        full_content = header + content

        chunk = KnowledgeChunk(
            doc_id=doc_id,
            chunk_index=idx,
            content=full_content,
            specialty=specialty,
        )
        session.add(chunk)
        await session.flush()
        chunk_ids.append(chunk.id)

    await sync_fts_index(session, chunk_ids)

    logger.info(f"Imported: {name} (doc_id={doc_id}, {len(chunk_ids)} chunks)")
    return 1, len(chunk_ids)


async def main(
    file_name: str | None = None,
    dry_run: bool = False,
    rebuild: bool = False,
):
    """主入口"""
    if not DATA_DIR.exists():
        logger.error(f"Data directory not found: {DATA_DIR}")
        return

    if file_name:
        files = [DATA_DIR / file_name]
        if not files[0].exists():
            logger.error(f"File not found: {files[0]}")
            return
    else:
        files = sorted(DATA_DIR.glob("*.json"))

    if not files:
        logger.info("No JSON files found in data/specialty_knowledge/")
        return

    async with AsyncSessionLocal() as session:
        if rebuild and not dry_run:
            cleared = await clear_system_knowledge(session)
            logger.info(f"Cleared {cleared} existing system knowledge docs")

        total_docs = 0
        total_chunks = 0

        for f in files:
            try:
                docs, chunks = await import_knowledge_file(session, f, dry_run)
                total_docs += docs
                total_chunks += chunks
            except Exception as e:
                logger.error(f"Failed to import {f.name}: {e}")

        if not dry_run:
            await session.commit()

        logger.info(f"Done: {total_docs} docs, {total_chunks} chunks imported")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Import specialty knowledge bases")
    parser.add_argument(
        "--file",
        help="Import only the specified JSON file (e.g. cardiology.json)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview without writing to database",
    )
    parser.add_argument(
        "--rebuild",
        action="store_true",
        help="Clear existing system knowledge before importing",
    )
    args = parser.parse_args()

    asyncio.run(main(
        file_name=args.file,
        dry_run=args.dry_run,
        rebuild=args.rebuild,
    ))
