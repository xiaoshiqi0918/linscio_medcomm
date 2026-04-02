# Layer 3C：图示/视觉类 Agent 完整性检查

## 检查结论概览

| 形式 | 规范要求 | 当前实现 | 完整性 | 待办事项 |
|------|----------|----------|--------|----------|
| **条漫** | ComicPanelPlanner + ComicPanelWriter | 仅 ComicPanelWriter | ⚠️ 部分 | ① 增加 planner ② Writer 接入规范 prompt |
| **知识卡片** | CardWriterAgent (JSON) | FormatAgent + 简版 fallback | ❌ 未实现 | 需完整实现 |
| **科普绘本** | PictureBookPlanner + PictureBookPage | FormatAgent + 简版 fallback | ❌ 未实现 | 需完整实现 |
| **科普海报** | PosterAgent (整体 JSON) | FormatAgent + 5 分节 | ⚠️ 结构差异 | 结构需对齐或保留分节 |

---

## 7.1 条漫 Agent 群

### 规范要求

1. **ComicPanelPlannerAgent**：分格规划
   - 输出 JSON：`total_panels`, `story_type`, `story_arc`, `panels[]`
   - 每格：`panel_index`, `panel_role`, `panel_theme`, `key_visual`, `emotion`
   - 规划原则：4-8 格、叙事结构、视觉连贯性

2. **ComicPanelWriterAgent**：单格内容
   - 使用 `format_meta`：`panel_index`, `total_panels`, `panel_role`, `panel_theme`, `story_arc`
   - `position_guidance`：第 1 格钩子、最后一格落点、中间格功能
   - 输出 JSON：`panel_index`, `scene_desc`, `dialogue`, `narration`, `caption`, `visual_notes`
   - `scene_desc` 规范：英文 30-50 词，DALL·E 可用
   - 对白规范：≤15 字/句，口语化

### 当前实现

- **ComicPanelWriter**（`backend/app/agents/comic/comic_agent.py`）
  - ✅ 使用 `format_meta`：`panel_index`, `total_panels`
  - ❌ 未使用：`panel_role`, `panel_theme`, `story_arc`
  - ❌ 无 `position_guidance`
  - ❌ 使用 FORMAT_SECTION_PROMPTS 简版，无 `visual_notes`、无详细 scene_desc/对白规范

- **无 ComicPanelPlannerAgent**
  - `SECTION_TYPES_BY_FORMAT["comic_strip"]` 仅有 `panel_1`~`panel_6`，无 `planner`
  - `_build_format_meta` 未填充 `panel_role`, `panel_theme`, `story_arc`

### 建议改动

1. **format_router**：在 comic_strip 的 section 前增加 `planner`
2. **task_prompts**：实现 `get_comic_planner`、`get_comic_panel`（接入 get_task_prompt 或直接增强 ComicPanelWriter）
3. **workflow**：planner 输出 JSON 存入 article/section 的 format_meta，供后续 panel 使用
4. **ComicPanelWriter**：接入规范 prompt，使用 `panel_role`/`panel_theme`/`story_arc`/`position_guidance`

---

## 7.2 知识卡片 Agent

### 规范要求

- **CardWriterAgent**
  - `format_meta`：`card_index`, `total_cards`, `card_title`, `color_scheme`
  - `color_guidance`：blue/green/orange/purple/red
  - 输出 JSON：`card_index`, `card_title`, `headline`, `body_text`, `key_takeaway`, `illustration_desc`, `icon_suggestions`, `data_placeholder`
  - `headline` ≤15 字；`body_text` 80-120 字；`illustration_desc` 英文 DALL·E

### 当前实现

- **card_series** 使用 **FormatAgent**（无专用 Agent）
- **TASK_PROMPT_FUNCS** 中无 card_series 条目，走 FORMAT_SECTION_PROMPTS 简版
- format_section 仅：「请撰写知识卡片1。格式：标题+核心要点（2-3条）……」

### 建议改动

1. **task_prompts**：实现 `get_card_content(state, section_type)`，支持 format_meta
2. **TASK_PROMPT_FUNCS**：添加 card_series 映射
3. **方案 A**：继续用 FormatAgent + get_task_prompt
4. **方案 B**：新建 CardWriterAgent，在 registry 注册
5. **_build_format_meta**：为 card_series 填充 `card_index`, `total_cards`, `color_scheme`（card_title 可留空或由 planner 提供）

---

## 7.3 科普绘本 Agent 群

### 规范要求

1. **PictureBookPlannerAgent**：整体规划
   - 输出 JSON：`total_pages`, `story_title`, `main_character`, `core_message`, `pages[]`
   - 每页：`page_index`, `page_function`, `page_theme`, `emotion`
   - 页数 6-10；主角拟人化；不引起恐惧

2. **PictureBookPageAgent**：单页内容
   - `format_meta`：`page_index`, `total_pages`, `page_theme`, `main_character`
   - 输出 JSON：`page_index`, `page_text`, `illustration_desc`, `sound_words`, `parent_note`
   - `page_text` 6-20 字，儿童视角

### 当前实现

- **picture_book** 使用 **FormatAgent**
- **SECTION_TYPES_BY_FORMAT**：`page_1`~`page_5`（无 planner）
- format_section 仅：「请撰写绘本第1页的文字（配合插图），语言温馨，每页50字以内」

### 建议改动

1. **format_router**：增加 `planner` 作为首节
2. **task_prompts**：实现 `get_picture_book_planner`、`get_picture_book_page`
3. **_build_format_meta**：为 picture_book 填充 `page_index`, `total_pages`, `page_theme`, `main_character`
4. 若规范要求 6-10 页，需评估是否将 page_5 扩展为 page_1~page_8 等

---

## 7.4 科普海报 Agent

### 规范要求

- **PosterAgent**：整体一次生成
  - 输出 JSON：`main_title`, `sub_title`, `key_points[]`, `data_highlight`, `call_to_action`, `footer`, `main_visual_desc`, `color_theme`

### 当前实现

- **poster** 使用 **FormatAgent**
- **SECTION_TYPES_BY_FORMAT**：`headline`, `core_message`, `data_points`, `cta`, `visual_desc`（5 个分节）
- 规范为**整体 JSON**，当前为**分节生成**，结构不一致

### 设计选择

| 方案 | 说明 |
|------|------|
| **A. 整体生成** | 新增 `poster_full` section_type，一次生成完整 JSON，需调整存储与导出 |
| **B. 保留分节** | 保持 5 节，为每节补充规范级 task_prompt，导出时组装为 key_points 等结构 |

建议：若产品按「分节编辑」交互，选 B；若接受「整张海报一次生成」，选 A。

---

## 汇总：建议实施顺序

1. **P0**：条漫 ComicPanelWriter 接入规范 prompt（panel_role/theme/arc + position_guidance + JSON 规范）
2. **P0**：知识卡片实现 get_card_content + format_meta
3. **P1**：条漫增加 planner 及 format_meta 传递
4. **P1**：绘本实现 planner + page 及 format_meta
5. **P2**：海报结构对齐（整体 vs 分节）
