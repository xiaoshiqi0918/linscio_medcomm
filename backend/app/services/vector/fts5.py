"""
FTS5 全文检索 - Ollama 不可用时的降级方案
knowledge_fts + paper_fts
"""
from typing import Optional
from sqlalchemy import text
from app.core.database import AsyncSessionLocal


async def ensure_fts_tables(session=None):
    """确保 knowledge_fts + paper_fts 虚拟表存在，并修复 papers_fts 列名不匹配"""
    stmts = [
        """CREATE VIRTUAL TABLE IF NOT EXISTS knowledge_fts USING fts5(
            chunk_id UNINDEXED, content, tokenize='unicode61'
        )""",
        """CREATE VIRTUAL TABLE IF NOT EXISTS paper_fts USING fts5(
            chunk_id UNINDEXED, content, tokenize='unicode61'
        )""",
    ]
    if session is not None:
        for s in stmts:
            await session.execute(text(s))
        await _fix_papers_fts_column_mismatch(session)
        await _fix_papers_fts_update_trigger(session)
        return
    async with AsyncSessionLocal() as sess:
        for s in stmts:
            await sess.execute(text(s))
        await _fix_papers_fts_column_mismatch(sess)
        await _fix_papers_fts_update_trigger(sess)
        await sess.commit()


_PAPERS_FTS_INSERT = """
    CREATE TRIGGER papers_fts_insert AFTER INSERT ON literature_papers BEGIN
        INSERT INTO papers_fts(rowid, title, authors, abstract, keywords, user_notes, journal)
        VALUES (new.id, new.title, new.authors, new.abstract, new.keywords, new.user_notes, new.journal);
    END
"""

_PAPERS_FTS_UPDATE = """
    CREATE TRIGGER papers_fts_update AFTER UPDATE ON literature_papers BEGIN
        INSERT INTO papers_fts(papers_fts, rowid, title, authors, abstract, keywords, user_notes, journal)
        VALUES ('delete', old.id, old.title, old.authors, old.abstract, old.keywords, old.user_notes, old.journal);
        INSERT INTO papers_fts(rowid, title, authors, abstract, keywords, user_notes, journal)
        VALUES (new.id, new.title, new.authors, new.abstract, new.keywords, new.user_notes, new.journal);
    END
"""

_PAPERS_FTS_DELETE = """
    CREATE TRIGGER papers_fts_delete AFTER DELETE ON literature_papers BEGIN
        INSERT INTO papers_fts(papers_fts, rowid, title, authors, abstract, keywords, user_notes, journal)
        VALUES ('delete', old.id, old.title, old.authors, old.abstract, old.keywords, old.user_notes, old.journal);
    END
"""


async def _fix_papers_fts_column_mismatch(session):
    """
    papers_fts 曾用 authors_text / keywords_text 作列名，但 content table
    (literature_papers) 实际列是 authors / keywords。FTS5 content-table 读回时
    按列名映射，导致 'no such column: T.authors_text'。检测到旧 schema 时重建。
    """
    row = (await session.execute(text(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='papers_fts'"
    ))).fetchone()
    if not row or not row[0]:
        return
    schema_sql = row[0]
    if "authors_text" not in schema_sql:
        return
    await _rebuild_papers_fts_triggers(session)
    print("[FTS5] Rebuilt papers_fts: fixed column name mismatch (authors_text → authors)", flush=True)


async def _fix_papers_fts_update_trigger(session):
    """
    FTS5 content-sync UPDATE trigger 使用 UPDATE ... SET 时，在 aiosqlite 下会报
    'database disk image is malformed'。改为 delete+insert 模式。
    """
    row = (await session.execute(text(
        "SELECT sql FROM sqlite_master WHERE type='trigger' AND name='papers_fts_update'"
    ))).fetchone()
    if not row or not row[0]:
        return
    if "UPDATE papers_fts SET" in row[0]:
        await session.execute(text("DROP TRIGGER IF EXISTS papers_fts_insert"))
        await session.execute(text("DROP TRIGGER IF EXISTS papers_fts_update"))
        await session.execute(text("DROP TRIGGER IF EXISTS papers_fts_delete"))
        await session.execute(text(_PAPERS_FTS_INSERT))
        await session.execute(text(_PAPERS_FTS_UPDATE))
        await session.execute(text(_PAPERS_FTS_DELETE))
        print("[FTS5] Fixed papers_fts_update trigger: UPDATE SET → delete+insert", flush=True)


async def _rebuild_papers_fts_triggers(session):
    """Drop/recreate papers_fts and all triggers"""
    await session.execute(text("DROP TRIGGER IF EXISTS papers_fts_insert"))
    await session.execute(text("DROP TRIGGER IF EXISTS papers_fts_update"))
    await session.execute(text("DROP TRIGGER IF EXISTS papers_fts_delete"))
    await session.execute(text("DROP TABLE IF EXISTS papers_fts"))
    await session.execute(text("""
        CREATE VIRTUAL TABLE papers_fts USING fts5(
            title, authors, abstract, keywords, user_notes, journal,
            content='literature_papers', content_rowid='id', tokenize='unicode61'
        )
    """))
    await session.execute(text("INSERT INTO papers_fts(papers_fts) VALUES('rebuild')"))
    await session.execute(text(_PAPERS_FTS_INSERT))
    await session.execute(text(_PAPERS_FTS_UPDATE))
    await session.execute(text(_PAPERS_FTS_DELETE))


async def ensure_paper_fts_tables(session=None):
    """仅确保 paper_fts 存在（文献索引器用）"""
    stmt = """CREATE VIRTUAL TABLE IF NOT EXISTS paper_fts USING fts5(
        chunk_id UNINDEXED, content, tokenize='unicode61'
    )"""
    if session is not None:
        await session.execute(text(stmt))
        return
    async with AsyncSessionLocal() as sess:
        await sess.execute(text(stmt))
        await sess.commit()


async def fts_search(query: str, top_k: int = 5, with_content: bool = True) -> list[dict]:
    """FTS5 全文检索，返回 chunk_id、snippet，可选完整 content（从 knowledge_chunks 取）"""
    try:
        q_escaped = query.replace('"', '""').strip()
        if not q_escaped:
            return []
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                text("""
                    SELECT chunk_id, snippet(knowledge_fts, 2, '', '', '...', 32) as snippet
                    FROM knowledge_fts
                    WHERE knowledge_fts MATCH :q
                    LIMIT :top_k
                """),
                {"q": q_escaped, "top_k": top_k}
            )
            rows = result.fetchall()
        out = [{"chunk_id": r[0], "snippet": r[1] or ""} for r in rows]
        if with_content and out:
            from app.models.knowledge import KnowledgeChunk
            from sqlalchemy import select
            chunk_ids = [r["chunk_id"] for r in out]
            async with AsyncSessionLocal() as session:
                res = await session.execute(
                    select(KnowledgeChunk.id, KnowledgeChunk.content, KnowledgeChunk.specialty).where(
                        KnowledgeChunk.id.in_(chunk_ids)
                    )
                )
                id_to_row = {r[0]: (r[1] or "", r[2]) for r in res.fetchall()}
            for o in out:
                content, sp = id_to_row.get(o["chunk_id"], (o["snippet"], None))
                o["content"] = content
                o["specialty"] = sp
        else:
            for o in out:
                o["content"] = o["snippet"]
                o["specialty"] = None
        return out
    except Exception:
        return []


async def paper_fts_search(
    query: str,
    top_k: int = 5,
    with_content: bool = True,
    chunk_types: list[str] | None = None,
    paper_ids: list[int] | None = None,
    only_fulltext_literature: bool = False,
) -> list[dict]:
    """FTS5 全文检索 paper_chunks，可选按 chunk_type / 文献全文状态过滤"""
    try:
        q_escaped = query.replace('"', '""').strip()
        if not q_escaped:
            return []
        from app.models.paper import PaperChunk
        from sqlalchemy import select

        limit = top_k * 5 if chunk_types else top_k
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                text("""
                    SELECT chunk_id, snippet(paper_fts, 2, '', '', '...', 32) as snippet
                    FROM paper_fts
                    WHERE paper_fts MATCH :q
                    LIMIT :lim
                """),
                {"q": q_escaped, "lim": limit},
            )
            rows = result.fetchall()
        out = [{"chunk_id": r[0], "snippet": r[1] or ""} for r in rows]
        if not out:
            return []
        chunk_ids = [o["chunk_id"] for o in out]
        async with AsyncSessionLocal() as session:
            stmt = select(PaperChunk.id, PaperChunk.paper_id, PaperChunk.chunk_text, PaperChunk.chunk_type).where(
                PaperChunk.id.in_(chunk_ids)
            )
            if only_fulltext_literature:
                from app.models.literature import LiteraturePaper

                stmt = (
                    select(PaperChunk.id, PaperChunk.paper_id, PaperChunk.chunk_text, PaperChunk.chunk_type)
                    .join(LiteraturePaper, LiteraturePaper.id == PaperChunk.paper_id)
                    .where(
                        PaperChunk.id.in_(chunk_ids),
                        LiteraturePaper.fulltext_status == "full",
                    )
                )
            if paper_ids:
                stmt = stmt.where(PaperChunk.paper_id.in_(paper_ids))
            res = await session.execute(stmt)
            rows = res.fetchall()
        id_to_row = {r[0]: (r[1], r[2] or "", r[3] or "") for r in rows}  # paper_id, chunk_text, chunk_type
        if chunk_types:
            out = [o for o in out if id_to_row.get(o["chunk_id"], (0, "", ""))[2] in chunk_types]
        if paper_ids:
            out = [o for o in out if id_to_row.get(o["chunk_id"], (0, "", ""))[0] in set(paper_ids)]
        for o in out[:top_k]:
            pid, content, ct = id_to_row.get(o["chunk_id"], (0, o["snippet"], ""))
            o["content"] = content
            o["chunk_type"] = ct
            o["paper_id"] = int(pid) if pid else None
        return out[:top_k]
    except Exception:
        return []
