"""
学科包安装入口

学科包文件结构（设计规范）：
    {specialty_id}/
    ├── config.json          # 学科配置（specialty_context, key_diseases, avoid_topics, ...）
    ├── knowledge/            # 指南文件、参考文献（PDF/TXT/MD）
    │   ├── 糖尿病诊治指南2024.pdf
    │   ├── 内分泌科常见问答.txt
    │   └── ...
    ├── terms.json           # 术语列表 [{term, abbreviation, layman_explain, analogy, audience_level}, ...]
    └── examples.json        # 科普范例 [{content_format, section_type, content_text, analysis_text, ...}, ...]

安装流程：
    1. 解析 config.json → 更新 _BUILTIN_SPECIALTY_CONFIGS（运行时）+ specialty_packages 表状态
    2. 遍历 knowledge/ → 为每个文件创建 KnowledgeDoc(specialty=xxx, source='package') + parse_and_index
    3. 导入 terms.json → 写入 medical_terms(specialty=xxx, source='package')
    4. 导入 examples.json → 写入 writing_examples(specialty=xxx, source='package')

所有导入均为幂等操作：重复安装只更新不重复创建。
"""
import json
import logging
from pathlib import Path

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.knowledge import KnowledgeDoc
from app.models.term import MedicalTerm
from app.models.example import WritingExample

logger = logging.getLogger("linscio.pack_installer")


async def install_specialty_pack(
    pack_dir: str | Path,
    specialty_id: str,
    db: AsyncSession,
) -> dict:
    """
    安装一个学科包到系统中。

    Args:
        pack_dir: 学科包根目录路径
        specialty_id: 学科 ID（如 endocrine, cardiology）
        db: 异步数据库 session

    Returns:
        {"config": bool, "knowledge_docs": int, "terms": int, "examples": int, "errors": [str]}
    """
    pack_path = Path(pack_dir)
    result = {"config": False, "knowledge_docs": 0, "terms": 0, "examples": 0, "errors": []}

    if not pack_path.exists():
        result["errors"].append(f"Pack directory not found: {pack_path}")
        return result

    # 1. config.json → 运行时学科配置
    config_file = pack_path / "config.json"
    if config_file.exists():
        try:
            config = json.loads(config_file.read_text(encoding="utf-8"))
            from app.services.enhancement.prompt_builder import _BUILTIN_SPECIALTY_CONFIGS
            _BUILTIN_SPECIALTY_CONFIGS[specialty_id] = config
            result["config"] = True
            logger.info(f"[pack] loaded config for '{specialty_id}'")
        except Exception as e:
            result["errors"].append(f"config.json parse error: {e}")

    # 2. knowledge/ → 知识文档索引
    knowledge_dir = pack_path / "knowledge"
    if knowledge_dir.exists():
        for doc_file in sorted(knowledge_dir.iterdir()):
            if doc_file.suffix.lower() not in (".txt", ".md", ".pdf"):
                continue
            try:
                count = await _index_pack_knowledge(db, doc_file, specialty_id)
                result["knowledge_docs"] += 1
                logger.info(f"[pack] indexed '{doc_file.name}': {count} chunks")
            except Exception as e:
                result["errors"].append(f"knowledge/{doc_file.name}: {e}")

    # 3. terms.json → 术语
    terms_file = pack_path / "terms.json"
    if terms_file.exists():
        try:
            terms = json.loads(terms_file.read_text(encoding="utf-8"))
            count = await _import_pack_terms(db, terms, specialty_id)
            result["terms"] = count
            logger.info(f"[pack] imported {count} terms for '{specialty_id}'")
        except Exception as e:
            result["errors"].append(f"terms.json: {e}")

    # 4. examples.json → 范例
    examples_file = pack_path / "examples.json"
    if examples_file.exists():
        try:
            examples = json.loads(examples_file.read_text(encoding="utf-8"))
            count = await _import_pack_examples(db, examples, specialty_id)
            result["examples"] = count
            logger.info(f"[pack] imported {count} examples for '{specialty_id}'")
        except Exception as e:
            result["errors"].append(f"examples.json: {e}")

    return result


async def uninstall_specialty_pack(specialty_id: str, db: AsyncSession) -> dict:
    """卸载学科包：删除该学科的包来源数据（不影响用户自行上传的内容）。"""
    from sqlalchemy import text as sa_text
    from app.models.knowledge import KnowledgeChunk

    counts = {"knowledge_docs": 0, "terms": 0, "examples": 0}

    docs = await db.execute(
        select(KnowledgeDoc).where(
            KnowledgeDoc.specialty == specialty_id,
            KnowledgeDoc.source == "package",
        )
    )
    for doc in docs.scalars().all():
        old_chunks = await db.execute(
            select(KnowledgeChunk.id).where(KnowledgeChunk.doc_id == doc.id)
        )
        old_ids = [r[0] for r in old_chunks.fetchall()]
        if old_ids:
            placeholders = ",".join(str(i) for i in old_ids)
            try:
                await db.execute(sa_text(
                    f"INSERT INTO knowledge_fts(knowledge_fts, rowid) "
                    f"SELECT 'delete', rowid FROM knowledge_fts WHERE chunk_id IN ({placeholders})"
                ))
            except Exception:
                pass
            await db.execute(
                delete(KnowledgeChunk).where(KnowledgeChunk.doc_id == doc.id)
            )
        await db.execute(
            delete(KnowledgeDoc).where(KnowledgeDoc.id == doc.id)
        )
        counts["knowledge_docs"] += 1

    await db.execute(
        delete(MedicalTerm).where(
            MedicalTerm.specialty == specialty_id,
            MedicalTerm.source == "package",
        )
    )

    await db.execute(
        delete(WritingExample).where(
            WritingExample.specialty == specialty_id,
            WritingExample.source == "package",
        )
    )

    from app.services.enhancement.prompt_builder import _BUILTIN_SPECIALTY_CONFIGS
    _BUILTIN_SPECIALTY_CONFIGS.pop(specialty_id, None)

    await db.commit()
    return counts


async def _index_pack_knowledge(db: AsyncSession, file_path: Path, specialty_id: str) -> int:
    """索引学科包中的单个知识文档"""
    name = file_path.stem

    existing = await db.execute(
        select(KnowledgeDoc).where(
            KnowledgeDoc.name == name,
            KnowledgeDoc.specialty == specialty_id,
            KnowledgeDoc.source == "package",
        )
    )
    doc = existing.scalar_one_or_none()

    if doc:
        doc.status = "indexing"
        doc.file_path = str(file_path)
        await db.commit()
        doc_id = doc.id
    else:
        doc = KnowledgeDoc(
            user_id=1,
            name=name,
            file_path=str(file_path),
            status="indexing",
            is_system=False,
            specialty=specialty_id,
            source="package",
        )
        db.add(doc)
        await db.commit()
        await db.refresh(doc)
        doc_id = doc.id

    from app.services.knowledge.indexer import parse_and_index
    count, status = await parse_and_index(doc_id, str(file_path), db, specialty=specialty_id)

    result = await db.execute(select(KnowledgeDoc).where(KnowledgeDoc.id == doc_id))
    d = result.scalar_one_or_none()
    if d:
        d.status = status
        await db.commit()
    return count


async def _import_pack_terms(db: AsyncSession, terms: list[dict], specialty_id: str) -> int:
    """导入学科包术语（幂等：先清除该学科的 package 来源术语再写入）"""
    await db.execute(
        delete(MedicalTerm).where(
            MedicalTerm.specialty == specialty_id,
            MedicalTerm.source == "package",
        )
    )
    await db.flush()

    count = 0
    for t in terms:
        term = MedicalTerm(
            term=t.get("term", ""),
            abbreviation=t.get("abbreviation", ""),
            layman_explain=t.get("layman_explain", ""),
            analogy=t.get("analogy", ""),
            specialty=specialty_id,
            audience_level=t.get("audience_level", "public"),
            source="package",
        )
        db.add(term)
        count += 1
    await db.commit()
    return count


async def _import_pack_examples(db: AsyncSession, examples: list[dict], specialty_id: str) -> int:
    """导入学科包范例（幂等：先清除该学科的 package 来源范例再写入）"""
    await db.execute(
        delete(WritingExample).where(
            WritingExample.specialty == specialty_id,
            WritingExample.source == "package",
        )
    )
    await db.flush()

    count = 0
    for e in examples:
        example = WritingExample(
            content_format=e.get("content_format", "article"),
            section_type=e.get("section_type", "body"),
            target_audience=e.get("target_audience", "public"),
            platform=e.get("platform", "universal"),
            specialty=specialty_id,
            content_text=e.get("content_text", ""),
            content_json=json.dumps(e["content_json"]) if e.get("content_json") else None,
            analysis_text=e.get("analysis_text", ""),
            source="package",
            is_active=True,
        )
        db.add(example)
        count += 1
    await db.commit()
    return count
