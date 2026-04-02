"""literature support v2.0

文献支撑库 v2.0：literature_papers 等新表，迁移 papers -> literature_papers
paper_chunks 改为关联 literature_papers，新增 papers_fts / 索引 / 视图

Revision ID: f1a2b3c4d5e6
Revises: e5f6a7b8c9d0
Create Date: 2026-03-23

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'f1a2b3c4d5e6'
down_revision: Union[str, Sequence[str], None] = 'e5f6a7b8c9d0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. 集合
    op.create_table(
        'literature_collections',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('parent_id', sa.Integer(), nullable=True),
        sa.Column('color', sa.String(length=20), nullable=True, server_default='#185FA5'),
        sa.Column('icon', sa.String(length=30), nullable=True, server_default='folder'),
        sa.Column('sort_order', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['parent_id'], ['literature_collections.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )

    # 2. 标签
    op.create_table(
        'literature_tags',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('color', sa.String(length=20), nullable=True, server_default='#1D9E75'),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name'),
    )

    # 3. 文献主表
    op.create_table(
        'literature_papers',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=True, server_default='1'),
        sa.Column('title', sa.Text(), nullable=False),
        sa.Column('authors', sa.Text(), nullable=False, server_default='[]'),
        sa.Column('journal', sa.Text(), nullable=True, server_default=''),
        sa.Column('year', sa.Integer(), nullable=True),
        sa.Column('volume', sa.String(length=50), nullable=True, server_default=''),
        sa.Column('issue', sa.String(length=50), nullable=True, server_default=''),
        sa.Column('pages', sa.String(length=50), nullable=True, server_default=''),
        sa.Column('publisher', sa.Text(), nullable=True, server_default=''),
        sa.Column('doi', sa.String(length=200), nullable=True),
        sa.Column('pmid', sa.String(length=50), nullable=True),
        sa.Column('arxiv_id', sa.String(length=50), nullable=True),
        sa.Column('url', sa.Text(), nullable=True, server_default=''),
        sa.Column('abstract', sa.Text(), nullable=True, server_default=''),
        sa.Column('keywords', sa.Text(), nullable=True, server_default='[]'),
        sa.Column('language', sa.String(length=10), nullable=True, server_default='zh'),
        sa.Column('user_notes', sa.Text(), nullable=True, server_default=''),
        sa.Column('user_abstract', sa.Text(), nullable=True, server_default=''),
        sa.Column('read_status', sa.String(length=20), nullable=True, server_default='unread'),
        sa.Column('rating', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('cite_count', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('collection_id', sa.Integer(), nullable=True),
        sa.Column('pdf_path', sa.Text(), nullable=True),
        sa.Column('pdf_size', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('pdf_indexed', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('import_source', sa.String(length=30), nullable=True, server_default='manual'),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.Column('deleted_at_ts', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['collection_id'], ['literature_collections.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('doi'),
        sa.UniqueConstraint('pmid'),
    )

    # 4. 文献-标签
    op.create_table(
        'literature_paper_tags',
        sa.Column('paper_id', sa.Integer(), nullable=False),
        sa.Column('tag_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['paper_id'], ['literature_papers.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['tag_id'], ['literature_tags.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('paper_id', 'tag_id'),
    )

    # 5. 附件
    op.create_table(
        'literature_attachments',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('paper_id', sa.Integer(), nullable=False),
        sa.Column('filename', sa.String(length=255), nullable=False),
        sa.Column('file_path', sa.Text(), nullable=False),
        sa.Column('file_type', sa.String(length=20), nullable=True, server_default='pdf'),
        sa.Column('file_size', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('description', sa.Text(), nullable=True, server_default=''),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['paper_id'], ['literature_papers.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )

    # 6. 标注
    op.create_table(
        'literature_annotations',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('paper_id', sa.Integer(), nullable=False),
        sa.Column('annotation_type', sa.String(length=30), nullable=False),
        sa.Column('page_number', sa.Integer(), nullable=False),
        sa.Column('rect', sa.Text(), nullable=False),
        sa.Column('color', sa.String(length=20), nullable=True, server_default='#FFD700'),
        sa.Column('content', sa.Text(), nullable=True, server_default=''),
        sa.Column('selected_text', sa.Text(), nullable=True, server_default=''),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['paper_id'], ['literature_papers.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )

    # 7. 迁移 papers -> literature_papers
    conn = op.get_bind()
    conn.execute(sa.text("""
        INSERT INTO literature_papers (
            id, user_id, title, journal, pdf_path, created_at,
            import_source, pdf_indexed
        )
        SELECT id, user_id, COALESCE(title, ''), '',
               file_path, created_at,
               'pdf', CASE WHEN status = 'done' THEN 1 ELSE 0 END
        FROM papers
    """))

    # 8. 重建 paper_chunks：新 schema 关联 literature_papers
    op.create_table(
        'paper_chunks_new',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('paper_id', sa.Integer(), nullable=False),
        sa.Column('chunk_index', sa.Integer(), nullable=False),
        sa.Column('chunk_type', sa.String(length=30), nullable=True),
        sa.Column('chunk_text', sa.Text(), nullable=False),
        sa.Column('page_start', sa.Integer(), nullable=True),
        sa.Column('page_end', sa.Integer(), nullable=True),
        sa.Column('section', sa.String(length=100), nullable=True, server_default=''),
        sa.Column('embedding', sa.LargeBinary(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['paper_id'], ['literature_papers.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    conn.execute(sa.text("""
        INSERT INTO paper_chunks_new (id, paper_id, chunk_index, chunk_type, chunk_text, page_start, page_end, section, created_at)
        SELECT id, paper_id, chunk_index, chunk_type, COALESCE(content, ''), NULL, NULL, '', created_at
        FROM paper_chunks
    """))
    op.drop_table('paper_chunks')
    op.rename_table('paper_chunks_new', 'paper_chunks')

    # 9. papers_fts（FTS5 列表检索）—— 列名必须与 content table 一致
    conn.execute(sa.text("""
        CREATE VIRTUAL TABLE IF NOT EXISTS papers_fts USING fts5(
            title, authors, abstract, keywords, user_notes, journal,
            content='literature_papers', content_rowid='id', tokenize='unicode61'
        )
    """))
    conn.execute(sa.text("""
        INSERT INTO papers_fts(papers_fts) VALUES('rebuild')
    """))

    # 10. 触发器
    conn.execute(sa.text("""
        CREATE TRIGGER papers_fts_insert AFTER INSERT ON literature_papers BEGIN
            INSERT INTO papers_fts(rowid, title, authors, abstract, keywords, user_notes, journal)
            VALUES (new.id, new.title, new.authors, new.abstract, new.keywords, new.user_notes, new.journal);
        END
    """))
    conn.execute(sa.text("""
        CREATE TRIGGER papers_fts_update AFTER UPDATE ON literature_papers BEGIN
            INSERT INTO papers_fts(papers_fts, rowid, title, authors, abstract, keywords, user_notes, journal)
            VALUES ('delete', old.id, old.title, old.authors, old.abstract, old.keywords, old.user_notes, old.journal);
            INSERT INTO papers_fts(rowid, title, authors, abstract, keywords, user_notes, journal)
            VALUES (new.id, new.title, new.authors, new.abstract, new.keywords, new.user_notes, new.journal);
        END
    """))
    conn.execute(sa.text("""
        CREATE TRIGGER papers_fts_delete AFTER DELETE ON literature_papers BEGIN
            INSERT INTO papers_fts(papers_fts, rowid, title, authors, abstract, keywords, user_notes, journal)
            VALUES ('delete', old.id, old.title, old.authors, old.abstract, old.keywords, old.user_notes, old.journal);
        END
    """))

    # 11. 索引（部分索引用原始 SQL）
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS idx_papers_doi ON literature_papers(doi) WHERE doi IS NOT NULL"))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS idx_papers_pmid ON literature_papers(pmid) WHERE pmid IS NOT NULL"))
    op.create_index('idx_papers_year', 'literature_papers', ['year'])
    op.create_index('idx_papers_deleted', 'literature_papers', ['deleted_at'])
    op.create_index('idx_papers_collection', 'literature_papers', ['collection_id'])
    op.create_index('idx_papers_read', 'literature_papers', ['read_status'])
    op.create_index('idx_paper_chunks', 'paper_chunks', ['paper_id', 'chunk_index'])
    op.create_index('idx_annotations', 'literature_annotations', ['paper_id', 'page_number'])

    # 12. 视图
    conn.execute(sa.text("""
        CREATE VIEW IF NOT EXISTS v_doi_index AS
        SELECT doi, id, title, year FROM literature_papers
        WHERE doi IS NOT NULL AND deleted_at IS NULL
    """))
    conn.execute(sa.text("""
        CREATE VIEW IF NOT EXISTS v_expired_trash AS
        SELECT id, title, deleted_at_ts FROM literature_papers
        WHERE deleted_at IS NOT NULL
          AND deleted_at_ts < strftime('%s', 'now') - (30 * 86400)
    """))

    # 13. 更新 paper_fts 使用 chunk_text（FTS5 表结构不变，插入逻辑在代码中）
    # paper_fts 保持 chunk_id + content，代码中插入时用 chunk_text 作为 content
    # 已有 paper_fts 数据仍有效（chunk_id 未变）

    # 14. 删除旧 papers 表
    op.drop_table('papers')


def downgrade() -> None:
    conn = op.get_bind()

    # 删除视图
    conn.execute(sa.text("DROP VIEW IF EXISTS v_doi_index"))
    conn.execute(sa.text("DROP VIEW IF EXISTS v_expired_trash"))

    # 删除触发器
    conn.execute(sa.text("DROP TRIGGER IF EXISTS papers_fts_insert"))
    conn.execute(sa.text("DROP TRIGGER IF EXISTS papers_fts_update"))
    conn.execute(sa.text("DROP TRIGGER IF EXISTS papers_fts_delete"))

    # 删除 papers_fts
    conn.execute(sa.text("DROP TABLE IF EXISTS papers_fts"))

    # 删除索引
    for idx in ['idx_paper_chunks', 'idx_annotations', 'idx_papers_read', 'idx_papers_collection',
                'idx_papers_deleted', 'idx_papers_year', 'idx_papers_pmid', 'idx_papers_doi']:
        conn.execute(sa.text(f"DROP INDEX IF EXISTS {idx}"))

    # 重建 papers 表
    op.create_table(
        'papers',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('title', sa.String(length=500), nullable=True),
        sa.Column('file_path', sa.String(length=500), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )

    # 重建旧 paper_chunks
    op.create_table(
        'paper_chunks_old',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('paper_id', sa.Integer(), nullable=True),
        sa.Column('chunk_index', sa.Integer(), nullable=True),
        sa.Column('chunk_type', sa.String(length=30), nullable=True),
        sa.Column('content', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['paper_id'], ['papers.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    conn.execute(sa.text("""
        INSERT INTO papers (id, user_id, title, file_path, status, created_at)
        SELECT id, user_id, title, pdf_path, CASE WHEN pdf_indexed=1 THEN 'done' ELSE 'pending' END, created_at
        FROM literature_papers
    """))
    conn.execute(sa.text("""
        INSERT INTO paper_chunks_old (id, paper_id, chunk_index, chunk_type, content, created_at)
        SELECT id, paper_id, chunk_index, chunk_type, chunk_text, created_at FROM paper_chunks
    """))
    op.drop_table('paper_chunks')
    op.rename_table('paper_chunks_old', 'paper_chunks')

    # 删除新表
    op.drop_table('literature_annotations')
    op.drop_table('literature_attachments')
    op.drop_table('literature_paper_tags')
    op.drop_table('literature_papers')
    op.drop_table('literature_tags')
    op.drop_table('literature_collections')
