# RAG 多源加权检索与混合检索 - 开发完整性检查

基于规范 15.1 / 15.2 / 15.3 的检查结果。

> **更新**：已按检查结论完成完善，见各节「当前状态」。

---

## 15.1 RAG 多源加权检索

### 规范要求

```python
RETRIEVAL_WEIGHTS = {
    'paper_chunks':     0.6,   # 文献支撑库（外部权威，优先级高）
    'knowledge_chunks': 0.4,   # 知识库（科室内部知识）
}

# 叙事类形式均参与 RAG 检索
# 脚本类/图示类形式：RAG 检索仍执行，但结果更多用于防编造验证而非提示词注入
```

### 当前状态

| 子项 | 状态 | 说明 |
|------|------|------|
| RETRIEVAL_WEIGHTS 常量 | ✅ | `rag_retriever.py` 已定义 0.6 / 0.4 |
| paper_chunks 检索 | ✅ | `paper_fts_search` 已接入，文献上传后解析并索引 paper_fts |
| knowledge_chunks 检索 | ✅ | FTS5 全文检索已接入 |
| 加权融合 | ✅ | `retrieve()` 分别检索 paper + knowledge，按权重排序合并 |
| paper_fts 表 | ✅ | `ensure_fts_tables` 创建 paper_fts，文献上传触发 `parse_and_index_paper` |

### 缺口（已补齐）

1. ~~paper_chunks 无 FTS5 索引~~ → 已建 `paper_fts`，`literature/paper_indexer.py` 解析 PDF 并索引
2. ~~RAGRetriever.retrieve() 未实现多源加权~~ → 已实现 paper + knowledge 双源加权
3. 叙事类 vs 脚本类/图示类：RAG 仍执行，结果用于提示词注入；脚本/图示类后续可细化为「仅防编造」

---

## 15.2 章节类型到 chunk_type 的映射

### 规范要求

```python
SECTION_TO_CHUNK_TYPE = {
    'intro': ['background', 'objective'], 'body': ['methods', 'results'],
    'case':  ['results', 'conclusion'],   'qa':   ['conclusion', 'limitation'],
    'summary': ['conclusion', 'abstract'],
    'opening': ['background'],            'development': ['methods', 'results'],
    'climax': ['results'],                'resolution':  ['conclusion'],
    'lesson': ['conclusion'],
    'myth_intro': ['background'],         'finding':     ['results'],
    'implication': ['conclusion'],        'caution':     ['limitation'],
    'hook': ['background'],               'body_1':      ['methods'],
    'disease_intro': ['background'],      'symptoms':    ['results'],
    'treatment': ['conclusion'],          'daily_care':  ['conclusion'],
    'panel_1': ['background'],            'card_1':      ['background'],
    # 规范还包含 myth_1/2/3, qa_intro, qa_1~3, qa_summary, action_guide 等
}
```

### 当前状态

| 子项 | 状态 | 说明 |
|------|------|------|
| SECTION_TO_CHUNK_TYPE 常量 | ✅ | `rag_retriever.py` 已定义，覆盖 80+ section_type |
| 映射覆盖范围 | ✅ | 已补全 myth_1/2/3, qa_*, action_guide, body_2/3, scene_*, frame_*, panel_*, card_*, visit_tips 等 |
| RAG 检索使用该映射 | ✅ | `paper_fts_search` 按 section_type → chunk_types 过滤 paper_chunks |
| paper_chunks.chunk_type | ✅ | 模型有 chunk_type，解析时按位置推断 |
| knowledge_chunks.chunk_type | ❌ | 模型无 chunk_type，仅全文检索 |

### 缺口（已部分补齐）

1. ~~SECTION_TO_CHUNK_TYPE 不全~~ → 已补全
2. ~~retrieve() 未用 section_type~~ → 已传入 section_type，paper 检索按 chunk_type 过滤
3. knowledge_chunks 无 chunk_type：知识库仍全文检索，待扩展

---

## 15.3 Ollama 不可用时的降级

### 规范要求

- 跳过向量检索，仅用 FTS5 全文检索
- SSE 推送 `ollama_warning` 事件
- 右侧面板显示提示

### 当前状态

| 子项 | 状态 | 说明 |
|------|------|------|
| 向量检索（Ollama/embedding） | ❌ | 未接入 sqlite-vec，当前仅 FTS5 |
| FTS5 降级 | ✅ | 当前即仅用 FTS5，`_ollama_available()` 检测 11434 |
| SSE ollama_warning 事件 | ✅ | `generate_section_stream` 在 `ollama_unavailable` 时 yield |
| 前端 useStreamGenerate | ✅ | 解析 `ollama_warning`，经 store 传给 RightPanel |
| VerificationPanel / 右侧面板 | ✅ | RightPanel 显示 ollama_warning 提示块 |

### 缺口（已补齐）

1. ~~Ollama 检测与降级逻辑~~ → `_ollama_available()` 检测 127.0.0.1:11434，不可用时标记 ollama_unavailable
2. ~~SSE 事件~~ → `generate_section_stream` yield `{"type": "ollama_warning", "message": "..."}`
3. ~~前端~~ → `useStreamGenerate` 解析并写入 store，RightPanel 展示
4. ~~VerificationPanel~~ → RightPanel 增加 ollama_warning 区块

---

## 汇总：已完成项

| 模块 | 实现 |
|------|------|
| RAG | paper_chunks FTS5 索引 + 多源加权检索 |
| RAG | retrieve() 使用 section_type → chunk_type 过滤（paper） |
| SECTION_TO_CHUNK_TYPE | 补全 80+ 映射 |
| Ollama 降级 | 检测 + SSE ollama_warning + 前端面板 |
| 待扩展 | knowledge_chunks 的 chunk_type（可选） |

---

## 相关文件路径

| 模块 | 路径 |
|------|------|
| RAG 检索器 | `backend/app/services/enhancement/rag_retriever.py` |
| FTS5 | `backend/app/services/vector/fts5.py` |
| 知识库索引 | `backend/app/services/knowledge/indexer.py` |
| 提示词增强 | `backend/app/services/enhancement/prompt_builder.py` |
| 生成流 | `backend/app/services/medcomm/generator.py` |
| 前端 SSE | `frontend/src/composables/useStreamGenerate.ts` |
| 右侧面板 | `frontend/src/components/verification/VerificationPanel.vue` |
| 形式/章节 | `backend/app/services/format_router.py` |
