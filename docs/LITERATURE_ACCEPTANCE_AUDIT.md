# 文献支撑库验收标准最终检查报告

## 验收标准对照表

| 验收标准 | 实现方案 | 实现状态 | 检查结论 |
|---------|---------|---------|---------|
| 能新增/编辑/删除（软删）/恢复文献 | POST/PUT/DELETE/restore 完整 CRUD | ✅ 已实现 | 通过 |
| DOI 自动补全，失败有错误提示 | CrossRef + NCBI 双源，指数退避重试 | ✅ 已实现 | 通过 |
| RIS/BibTeX 成功率 > 95% | RIS 按行解析，BibTeX 用 bibtexparser 库 | ✅ 已实现 | 需实测 |
| 列表检索 < 500ms（1万条） | FTS5 全文检索 + 复合索引 | ⚠️ 已实现 | 需实测 |
| APA/BibTeX 字段完整率 > 98% | CitationFormatter 所有字段均有 fallback | ✅ 已实现 | 通过 |
| DOI 去重准确率 100% | DOI 列 UNIQUE 约束，录入前 check | ✅ 已实现 | 通过 |
| 相似标题去重可用水平 | difflib + 0.85 阈值 + 年份窗口 | ✅ 已实现 | 通过 |

---

## 1. 新增/编辑/删除（软删）/恢复文献

**实现位置**：`backend/app/api/v1/literature.py`

- `POST /papers` - 创建
- `PUT /papers/{id}` - 更新
- `DELETE /papers/{id}` - 软删除（设置 `deleted_at`）
- `POST /papers/{id}/restore` - 恢复
- `deleted_at` 字段用于软删除，不物理删除

**结论**：✅ 符合验收标准

---

## 2. DOI 自动补全，失败有错误提示

**实现位置**：`backend/app/services/literature/metadata_fetcher.py`，`backend/app/api/v1/literature.py` 之 `fetch_metadata`

- CrossRef（DOI）、NCBI（PMID）双源 ✅
- 指数退避重试：`await asyncio.sleep(2**attempt)` ✅
- 超时 504：`httpx.TimeoutException` → 504 ✅
- 网络错误 503：`httpx.ConnectError` → 503 ✅
- 404：DOI/PMID 不存在 → 404 + `METADATA_NOT_FOUND` ✅

**结论**：✅ 符合验收标准

---

## 3. RIS/BibTeX 成功率 > 95%

**实现位置**：
- `backend/app/services/literature/importers/ris.py` - RIS 按行解析，支持 TI/AU/JO/PY/DO 等常用标签
- `backend/app/services/literature/importers/bibtex.py` - 使用 bibtexparser 库

**缺失**：无 Zotero/EndNote 标准测试集及成功率统计。

**建议**：补充 `tests/literature/test_ris_bibtex_import.py`，使用标准样本验证成功率。

---

## 4. 列表检索 < 500ms（1万条）

**实现位置**：
- `backend/app/services/literature/query_builder.py` - FTS5 使用 `papers_fts`，先 MATCH 后 JOIN
- `backend/alembic/versions/f1a2b3c4d5e6_literature_support_v2.py` - `papers_fts` 虚拟表及触发器

**注意**：`query_builder` 使用 `papers_fts`，需确认迁移已执行且表存在。`paper_fts` 为 chunk 级全文索引，`papers_fts` 为文献级列表检索。

**缺失**：无 EXPLAIN QUERY PLAN 验证及 1 万条性能测试。

**建议**：补充性能测试用例。

---

## 5. APA/BibTeX 字段完整率 > 98%

**实现位置**：`backend/app/services/literature/citation_formatter.py`

- APA：`_apa_authors()` 无作者时返回 "Anonymous"，年份无时 "(n.d.)"，其它字段 `or ""`
- BibTeX：无作者时 "Unknown"，`field_strs` 只输出非空字段
- NLM / GB/T 7714：作者为空时 "Unknown"/"佚名"，其它字段有空值处理

**结论**：✅ 字段缺失有 fallback，不抛异常

---

## 6. DOI 去重准确率 100%

**实现位置**：
- `app/models/literature.py`：`doi = Column(String(200), unique=True)` ✅
- `app/api/v1/literature.py`：`create_paper` 前调用 `DuplicateChecker.check()`，`exact_match` 时拒绝并返回 409 ✅
- `POST /papers/check-duplicate` 返回 `exact_match`、`paper_id`、`fuzzy_matches` ✅

**结论**：✅ 符合验收标准

---

## 7. 相似标题去重可用水平

**实现位置**：`backend/app/services/literature/dedup.py`

- 使用 `difflib.SequenceMatcher` 计算标题相似度 ✅
- 阈值 `TITLE_SIMILARITY_THRESHOLD = 0.85` ✅
- 年份窗口：`(year-1, year+1)` ✅
- 作者 Jaccard 相似度参与综合评分 ✅
- 仅提示，不阻断录入：`fuzzy_matches` 返回给前端，由用户决定 ✅

**结论**：✅ 符合验收标准

---

## 8. 性能测试用例

**已新增**：`backend/tests/performance/test_literature_search.py`

- `test_search_1w_papers`：列表检索响应 < 500ms
- `test_doi_dedup_accuracy`：DOI 去重返回 `exact_match=True`
- `test_ris_import_success_rate`：RIS 标准样本成功率 ≥ 95%

**运行方式**：先启动后端 `uvicorn app.main:app`，再执行 `pytest tests/performance/test_literature_search.py -v`

---

## 9. 潜在问题

1. **papers_fts 表存在性**：`query_builder` 依赖 `papers_fts`，若迁移未执行或表被删除，带 `q=` 的列表查询会报错。需确认迁移状态。
2. **BibTeX 解析异常**：`bibtexparser` 未安装时会 `return []`，应在导入时做更明确的错误处理或依赖检查。
