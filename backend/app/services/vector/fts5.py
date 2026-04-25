"""
全文检索抽象层 — 双模式支持
  desktop (SQLite):  FTS5 虚拟表 knowledge_fts / paper_fts
  saas (PostgreSQL): tsvector + GIN 索引 + ts_rank 排序
"""
from typing import Optional
from sqlalchemy import text
from app.core.database import AsyncSessionLocal
from app.core.config import is_desktop


# ── 初始化 ─────────────────────────────────────────────────

async def ensure_fts_tables(session=None):
    """确保全文检索基础设施就绪"""
    if is_desktop():
        await _ensure_fts_tables_sqlite(session)
    else:
        await _ensure_fts_tables_pg(session)


async def ensure_paper_fts_tables(session=None):
    """确保文献全文检索基础设施就绪"""
    if is_desktop():
        await _ensure_paper_fts_tables_sqlite(session)
    else:
        await _ensure_paper_fts_tables_pg(session)


# ── 知识库 FTS 搜索 ──────────────────────────────────────────

async def fts_search(query: str, top_k: int = 5, with_content: bool = True) -> list[dict]:
    """全文检索 knowledge_chunks"""
    if is_desktop():
        return await _fts_search_sqlite(query, top_k, with_content)
    return await _fts_search_pg(query, top_k, with_content)


# ── 文献 FTS 搜索 ───────────────────────────────────────────

async def paper_fts_search(
    query: str,
    top_k: int = 5,
    with_content: bool = True,
    chunk_types: list[str] | None = None,
    paper_ids: list[int] | None = None,
    only_fulltext_literature: bool = False,
) -> list[dict]:
    """全文检索 paper_chunks"""
    if is_desktop():
        return await _paper_fts_search_sqlite(
            query, top_k, with_content, chunk_types, paper_ids, only_fulltext_literature
        )
    return await _paper_fts_search_pg(
        query, top_k, with_content, chunk_types, paper_ids, only_fulltext_literature
    )


# ── 索引写入 ────────────────────────────────────────────────

async def index_knowledge_chunk(chunk_id: int, content: str, session) -> None:
    """向全文索引写入一条知识库 chunk"""
    if is_desktop():
        await session.execute(
            text("INSERT INTO knowledge_fts(chunk_id, content) VALUES (:cid, :content)"),
            {"cid": chunk_id, "content": (content or "")[:10000]},
        )
    # PostgreSQL 无需单独维护，tsvector 列通过触发器自动更新


async def delete_knowledge_chunks_from_fts(chunk_ids: list[int], session) -> None:
    """从全文索引删除知识库 chunk"""
    if not chunk_ids:
        return
    if is_desktop():
        placeholders = ",".join(str(i) for i in chunk_ids)
        try:
            await session.execute(text(
                f"INSERT INTO knowledge_fts(knowledge_fts, rowid) "
                f"SELECT 'delete', rowid FROM knowledge_fts WHERE chunk_id IN ({placeholders})"
            ))
        except Exception:
            pass
    # PostgreSQL 无需单独维护，删除行时 tsvector 列自动失效


async def index_paper_chunk(chunk_id: int, content: str, session) -> None:
    """向全文索引写入一条文献 chunk"""
    if is_desktop():
        await session.execute(
            text("INSERT INTO paper_fts(chunk_id, content) VALUES (:cid, :content)"),
            {"cid": chunk_id, "content": (content or "")[:10000]},
        )
    # PostgreSQL 无需单独维护


async def delete_paper_chunks_from_fts(chunk_ids: list[int], session) -> None:
    """从全文索引删除文献 chunk"""
    if not chunk_ids:
        return
    if is_desktop():
        ph = ",".join(str(i) for i in chunk_ids)
        try:
            await session.execute(text("DELETE FROM paper_fts WHERE chunk_id IN (%s)" % ph))
        except Exception:
            pass
    # PostgreSQL 无需单独维护


# ══════════════════════════════════════════════════════════
#  SQLite / FTS5 实现
# ══════════════════════════════════════════════════════════

async def _ensure_fts_tables_sqlite(session=None):
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


async def _ensure_paper_fts_tables_sqlite(session=None):
    stmt = """CREATE VIRTUAL TABLE IF NOT EXISTS paper_fts USING fts5(
        chunk_id UNINDEXED, content, tokenize='unicode61'
    )"""
    if session is not None:
        await session.execute(text(stmt))
        return
    async with AsyncSessionLocal() as sess:
        await sess.execute(text(stmt))
        await sess.commit()


async def _fts_search_sqlite(query: str, top_k: int = 5, with_content: bool = True) -> list[dict]:
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
            out = await _enrich_knowledge_chunks(out)
        else:
            for o in out:
                o["content"] = o["snippet"]
                o["specialty"] = None
        return out
    except Exception:
        return []


async def _paper_fts_search_sqlite(
    query: str, top_k: int, with_content: bool,
    chunk_types, paper_ids, only_fulltext_literature,
) -> list[dict]:
    try:
        q_escaped = query.replace('"', '""').strip()
        if not q_escaped:
            return []
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
        return await _filter_paper_chunks(out, top_k, chunk_types, paper_ids, only_fulltext_literature)
    except Exception:
        return []


# ══════════════════════════════════════════════════════════
#  PostgreSQL / tsvector 实现
# ══════════════════════════════════════════════════════════

async def _ensure_fts_tables_pg(session=None):
    """PostgreSQL: 给 knowledge_chunks 和 paper_chunks 添加 tsvector 列 + GIN 索引"""
    stmts = [
        # knowledge_chunks
        "ALTER TABLE knowledge_chunks ADD COLUMN IF NOT EXISTS search_vector tsvector",
        """CREATE INDEX IF NOT EXISTS idx_knowledge_chunks_fts
           ON knowledge_chunks USING gin(search_vector)""",
        """CREATE OR REPLACE FUNCTION knowledge_chunks_search_trigger() RETURNS trigger AS $$
           BEGIN
             NEW.search_vector := to_tsvector('simple', coalesce(NEW.content, ''));
             RETURN NEW;
           END
           $$ LANGUAGE plpgsql""",
        """DO $$ BEGIN
             IF NOT EXISTS (
               SELECT 1 FROM pg_trigger WHERE tgname = 'trg_knowledge_chunks_search'
             ) THEN
               CREATE TRIGGER trg_knowledge_chunks_search
               BEFORE INSERT OR UPDATE OF content ON knowledge_chunks
               FOR EACH ROW EXECUTE FUNCTION knowledge_chunks_search_trigger();
             END IF;
           END $$""",
        # 回填已有行
        """UPDATE knowledge_chunks SET search_vector = to_tsvector('simple', coalesce(content, ''))
           WHERE search_vector IS NULL""",
        # paper_chunks
        "ALTER TABLE paper_chunks ADD COLUMN IF NOT EXISTS search_vector tsvector",
        """CREATE INDEX IF NOT EXISTS idx_paper_chunks_fts
           ON paper_chunks USING gin(search_vector)""",
        """CREATE OR REPLACE FUNCTION paper_chunks_search_trigger() RETURNS trigger AS $$
           BEGIN
             NEW.search_vector := to_tsvector('simple', coalesce(NEW.chunk_text, ''));
             RETURN NEW;
           END
           $$ LANGUAGE plpgsql""",
        """DO $$ BEGIN
             IF NOT EXISTS (
               SELECT 1 FROM pg_trigger WHERE tgname = 'trg_paper_chunks_search'
             ) THEN
               CREATE TRIGGER trg_paper_chunks_search
               BEFORE INSERT OR UPDATE OF chunk_text ON paper_chunks
               FOR EACH ROW EXECUTE FUNCTION paper_chunks_search_trigger();
             END IF;
           END $$""",
        """UPDATE paper_chunks SET search_vector = to_tsvector('simple', coalesce(chunk_text, ''))
           WHERE search_vector IS NULL""",
    ]
    if session is not None:
        for s in stmts:
            await session.execute(text(s))
        return
    async with AsyncSessionLocal() as sess:
        for s in stmts:
            await sess.execute(text(s))
        await sess.commit()


async def _ensure_paper_fts_tables_pg(session=None):
    """PostgreSQL: 确保 paper_chunks 有 tsvector 列"""
    stmts = [
        "ALTER TABLE paper_chunks ADD COLUMN IF NOT EXISTS search_vector tsvector",
        """CREATE INDEX IF NOT EXISTS idx_paper_chunks_fts
           ON paper_chunks USING gin(search_vector)""",
        """CREATE OR REPLACE FUNCTION paper_chunks_search_trigger() RETURNS trigger AS $$
           BEGIN
             NEW.search_vector := to_tsvector('simple', coalesce(NEW.chunk_text, ''));
             RETURN NEW;
           END
           $$ LANGUAGE plpgsql""",
        """DO $$ BEGIN
             IF NOT EXISTS (
               SELECT 1 FROM pg_trigger WHERE tgname = 'trg_paper_chunks_search'
             ) THEN
               CREATE TRIGGER trg_paper_chunks_search
               BEFORE INSERT OR UPDATE OF chunk_text ON paper_chunks
               FOR EACH ROW EXECUTE FUNCTION paper_chunks_search_trigger();
             END IF;
           END $$""",
        """UPDATE paper_chunks SET search_vector = to_tsvector('simple', coalesce(chunk_text, ''))
           WHERE search_vector IS NULL""",
    ]
    if session is not None:
        for s in stmts:
            await session.execute(text(s))
        return
    async with AsyncSessionLocal() as sess:
        for s in stmts:
            await sess.execute(text(s))
        await sess.commit()


async def _fts_search_pg(query: str, top_k: int = 5, with_content: bool = True) -> list[dict]:
    try:
        q = query.strip()
        if not q:
            return []
        ts_query = " & ".join(w for w in q.split() if w)
        if not ts_query:
            ts_query = q
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                text("""
                    SELECT id, left(content, 200) AS snippet,
                           ts_rank(search_vector, to_tsquery('simple', :q)) AS rank
                    FROM knowledge_chunks
                    WHERE search_vector @@ to_tsquery('simple', :q)
                    ORDER BY rank DESC
                    LIMIT :top_k
                """),
                {"q": ts_query, "top_k": top_k}
            )
            rows = result.fetchall()
        out = [{"chunk_id": r[0], "snippet": r[1] or ""} for r in rows]
        if with_content and out:
            out = await _enrich_knowledge_chunks(out)
        else:
            for o in out:
                o["content"] = o["snippet"]
                o["specialty"] = None
        return out
    except Exception:
        return []


async def _paper_fts_search_pg(
    query: str, top_k: int, with_content: bool,
    chunk_types, paper_ids, only_fulltext_literature,
) -> list[dict]:
    try:
        q = query.strip()
        if not q:
            return []
        ts_query = " & ".join(w for w in q.split() if w)
        if not ts_query:
            ts_query = q
        limit = top_k * 5 if chunk_types else top_k
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                text("""
                    SELECT id, left(chunk_text, 200) AS snippet,
                           ts_rank(search_vector, to_tsquery('simple', :q)) AS rank
                    FROM paper_chunks
                    WHERE search_vector @@ to_tsquery('simple', :q)
                    ORDER BY rank DESC
                    LIMIT :lim
                """),
                {"q": ts_query, "lim": limit},
            )
            rows = result.fetchall()
        out = [{"chunk_id": r[0], "snippet": r[1] or ""} for r in rows]
        if not out:
            return []
        return await _filter_paper_chunks(out, top_k, chunk_types, paper_ids, only_fulltext_literature)
    except Exception:
        return []


# ══════════════════════════════════════════════════════════
#  共享工具函数
# ══════════════════════════════════════════════════════════

async def _enrich_knowledge_chunks(out: list[dict]) -> list[dict]:
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
    return out


async def _filter_paper_chunks(
    out: list[dict], top_k: int,
    chunk_types, paper_ids, only_fulltext_literature,
) -> list[dict]:
    from app.models.paper import PaperChunk
    from sqlalchemy import select
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
    id_to_row = {r[0]: (r[1], r[2] or "", r[3] or "") for r in rows}
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


# ══════════════════════════════════════════════════════════
#  SQLite FTS5 维护（仅桌面端）
# ══════════════════════════════════════════════════════════

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
    row = (await session.execute(text(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='papers_fts'"
    ))).fetchone()
    if not row or not row[0]:
        return
    if "authors_text" not in row[0]:
        return
    await _rebuild_papers_fts_triggers(session)


async def _fix_papers_fts_update_trigger(session):
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


async def _rebuild_papers_fts_triggers(session):
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
