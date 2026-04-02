"""文献列表多条件查询构建器（FTS5 + 结构化过滤）"""
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class PaperQueryBuilder:
    """FTS5 全文检索 + 结构化条件组合"""

    def __init__(self, db: AsyncSession):
        self.db = db
        self._conditions: list[str] = []
        self._params: dict = {}
        self._fts_query: str | None = None
        self._sort_col = "created_at"
        self._sort_dir = "DESC"

    def filter_active(self) -> "PaperQueryBuilder":
        self._conditions.append("p.deleted_at IS NULL")
        return self

    def filter_trashed(self) -> "PaperQueryBuilder":
        self._conditions.append("p.deleted_at IS NOT NULL")
        return self

    def fts_search(self, q: str) -> "PaperQueryBuilder":
        if q and q.strip():
            self._fts_query = q.strip().replace('"', '""')
        return self

    def filter_author(self, author: str) -> "PaperQueryBuilder":
        self._conditions.append("p.authors LIKE :author")
        self._params["author"] = f"%{author}%"
        return self

    def filter_journal(self, journal: str) -> "PaperQueryBuilder":
        self._conditions.append("p.journal LIKE :journal")
        self._params["journal"] = f"%{journal}%"
        return self

    def filter_year_from(self, year: int) -> "PaperQueryBuilder":
        self._conditions.append("p.year >= :year_from")
        self._params["year_from"] = year
        return self

    def filter_year_to(self, year: int) -> "PaperQueryBuilder":
        self._conditions.append("p.year <= :year_to")
        self._params["year_to"] = year
        return self

    def filter_keyword(self, keyword: str) -> "PaperQueryBuilder":
        self._conditions.append("p.keywords LIKE :keyword")
        self._params["keyword"] = f"%{keyword}%"
        return self

    def filter_collection(self, collection_id: int) -> "PaperQueryBuilder":
        self._conditions.append("p.collection_id = :collection_id")
        self._params["collection_id"] = collection_id
        return self

    def filter_tags(self, tag_ids: list[int]) -> "PaperQueryBuilder":
        if not tag_ids:
            return self
        ph = ",".join(f":tag_{i}" for i in range(len(tag_ids)))
        self._conditions.append(
            f"p.id IN (SELECT paper_id FROM literature_paper_tags WHERE tag_id IN ({ph}))"
        )
        for i, tid in enumerate(tag_ids):
            self._params[f"tag_{i}"] = tid
        return self

    def filter_read_status(self, status: str) -> "PaperQueryBuilder":
        self._conditions.append("p.read_status = :read_status")
        self._params["read_status"] = status
        return self

    def sort(self, col: str, direction: str) -> "PaperQueryBuilder":
        valid = {"created_at", "year", "cite_count", "title", "updated_at"}
        self._sort_col = col if col in valid else "created_at"
        self._sort_dir = "ASC" if (direction or "").lower() == "asc" else "DESC"
        return self

    async def paginate(self, page: int, size: int) -> tuple[int, list[dict]]:
        offset = max(0, (page - 1) * size)
        size = max(1, min(size, 100))

        if self._fts_query:
            fts_cte = (
                "WITH fts_hits AS ("
                "  SELECT rowid, rank FROM papers_fts"
                "  WHERE papers_fts MATCH :fts_q"
                ")"
            )
            self._params["fts_q"] = self._fts_query
            base_sql = (
                f"{fts_cte} SELECT p.* FROM literature_papers p "
                "INNER JOIN fts_hits ON p.id = fts_hits.rowid"
            )
        else:
            base_sql = "SELECT p.* FROM literature_papers p"

        where_clause = (" WHERE " + " AND ".join(self._conditions)) if self._conditions else ""
        count_sql = text(f"SELECT COUNT(*) FROM ({base_sql}{where_clause}) t")
        result = await self.db.execute(count_sql, self._params)
        total = result.scalar() or 0

        sort_col = self._sort_col if self._sort_col != "updated_at" else "COALESCE(p.updated_at, p.created_at)"
        sort_expr = f"{sort_col} {self._sort_dir}"
        if self._fts_query:
            sort_expr = f"fts_hits.rank, {sort_expr}"

        query_sql = text(
            f"{base_sql}{where_clause} ORDER BY {sort_expr} LIMIT :limit OFFSET :offset"
        )
        rows = (
            await self.db.execute(
                query_sql, {**self._params, "limit": size, "offset": offset}
            )
        ).fetchall()

        items = []
        for r in rows:
            row = dict(r._mapping)
            for k, v in list(row.items()):
                if hasattr(v, "isoformat"):
                    row[k] = v.isoformat() if v else None
            items.append(row)
        return total, items
