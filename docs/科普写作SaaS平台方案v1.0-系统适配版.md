# 科普写作智能体 SaaS 平台 —— 系统适配方案

> 版本：v1.0（系统适配版） | 基于 v0.9 方案 + MedComm 现有系统分析  
> 技术栈：复用 MedComm 后端（FastAPI + SQLAlchemy）+ 新 SaaS 前端（Vue 3）  
> 托管：腾讯云香港

---

## 一、适配总述

本文档基于 v0.9 方案，逐项与 MedComm 现有代码库对照，给出六个关键决策的论证结论，并将方案条目映射到具体可复用模块。目标是最大化复用现有资产、最小化重复开发。

### 六项关键决策结论速查

| 决策项 | 结论 | 核心理由 |
|--------|------|----------|
| 产品定位 | **渐进开放**：MVP 只露 article，底层保留 format_router | 17 种形式架构已成熟，限制仅在前端，零成本扩展 |
| 异步架构 | **SSE + Celery 混合**：生成/优化走 SSE，分析/导出走 Celery | 保留实时流式体验，批量任务解耦到队列 |
| 数据库 | **复用现有模型 + 扩展积分/计费表** | Article/Section/Content 比方案设计更强大 |
| 门户角色 | **独立 SaaS 应用**，共享基础设施 | 业务逻辑差异大，强合并增加耦合风险 |
| 模型选择 | **SaaS 版固定模型路由**，用户不可选 | 积分定价基于固定成本核算，自选会亏损 |
| 桌面共存 | **双产品线并行**：桌面版面向机构，SaaS 面向个人 | 桌面版授权码体系继续运营，SaaS 独立获客 |

---

## 二、决策 1：产品定位 —— 渐进开放

### 现状分析

MedComm 的 `format_router.py` 已实现完整的 17 种内容形式体系：

```
FORMAT_CONFIG = {
    "article":         图文文章（科普主力）
    "story":           科普故事
    "debunk":          辟谣文
    "qa_article":      问答科普
    "research_read":   研究速读
    "oral_script":     口播脚本（抖音/B站）
    "drama_script":    情景剧本
    "storyboard":      动画分镜
    "audio_script":    播客脚本
    "comic_strip":     条漫
    "card_series":     知识卡片系列
    "poster":          科普海报
    "picture_book":    科普绘本
    "long_image":      竖版长图
    "patient_handbook": 患者教育手册
    "quiz_article":    自测科普
    "h5_outline":      H5 互动大纲
}
```

每种形式都有独立的 Agent 群、章节结构、导出器、平台推荐矩阵。这套架构已经过充分验证。

### 决策结论

**MVP 阶段**只在 SaaS 前端开放以下 4 种文字类形式（不依赖 ComfyUI 图像能力）：

| 形式 | 说明 | 适合平台 | MVP 理由 |
|------|------|---------|---------|
| article | 图文文章 | 微信/期刊/通用 | 科普主力，覆盖方案核心场景 |
| story | 科普故事 | 微信/通用 | 叙事类科普需求大 |
| debunk | 辟谣文 | 微信/通用 | 自媒体热门题材 |
| qa_article | 问答科普 | 微信/小红书/通用 | 患者教育刚需 |

**实现方式**：后端 `format_router.py` 零改动，前端新建文章时只展示上述 4 种。后续每开放一种新形式，只需前端加一行配置，**不涉及后端开发**。

**后续扩展路径**：
- Phase 2：开放 `oral_script`（口播脚本）、`research_read`（研究速读）—— 视频博主需求
- Phase 3：开放 `patient_handbook`（患者手册）、`card_series`（知识卡片）—— 需配图能力到位后
- 远期：开放 `comic_strip`、`poster` 等图像密集形式 —— 需 ComfyUI 云端化

**积分定价影响**：不同形式的章节数和字数差异大，定价应按「目标字数分档」而非按形式，v0.9 的字数阶梯方案仍然适用。

---

## 三、决策 2：异步架构 —— SSE + Celery 混合

### 现状分析

MedComm 现有的 `generate_section_stream()` 是一个成熟的 SSE 流式生成管线：

```
SSE 事件流程：
  → context（RAG 检索结果）
  → delta（逐 token 流式输出）
  → rewriting（去AI化改写中...）
  → rewritten_content（改写后全文）
  → verify_report（AIGC 检测报告）
  → done（最终内容 + 字数 + 配图建议）
```

用户可以实时看到内容逐字出现，这种体验远优于 Celery 轮询的「等待中... → 完成」。

### 决策结论

**混合架构**，按操作类型分流：

| 操作类型 | 通道 | 理由 |
|----------|------|------|
| 章节生成 | **SSE 流式** | 核心体验，用户实时看到输出 |
| 段落优化（第三轮） | **SSE 流式** | 选段改写结果立即展示 |
| 文献分析 | **Celery 队列** | 耗时长（MapReduce 多篇），用户可离开 |
| 文件导出 | **Celery 队列** | PDF 渲染耗时，后台处理 |
| AIGC 检测 | **同步 API** | 本地算法，毫秒级，无需异步 |

**积分扣费时机**：
- SSE 通道：流式完成（收到 `done` 事件）后，后端在同一请求内完成扣费 + 存储
- Celery 通道：Worker 任务成功后原子扣费，前端轮询到 `success` 后刷新余额
- 两种通道都遵循「先存内容，后扣积分」原则

**对 v0.9 方案的修订**：
- 方案中 §4.1 架构图的 Celery 仍保留，但职责缩窄为文献分析和导出
- 方案中 §9.3 的「前端每 2 秒轮询」仅用于 Celery 任务，生成/优化走 SSE
- Redis 仍需要：Celery Broker + 分布式锁（并发扣费保护）+ JWT 黑名单

---

## 四、决策 3：数据库 —— 复用现有模型 + 扩展

### 现状分析

MedComm 现有的数据模型层次比 v0.9 方案更丰富：

**现有 Article 体系**（v0.9 只有一张 articles 表）：
- `Article` —— 文章主体，含 content_format / platform / target_audience / reading_level / target_word_count 等
- `ArticleSection` —— 章节级管理，支持排序、跳过、独立状态
- `ArticleContent` —— 内容版本管理，支持 TipTap JSON / HTML / 纯文本，含 verify_report
- `ArticleLiteratureBinding` —— 文章与文献的关联
- `ArticleExternalReference` —— 站外引用（PubMed/CrossRef/Semantic Scholar）

**现有 User 模型**（极简，需大幅扩展）：
```python
class User(Base):
    id, email, display_name, created_at, updated_at
```

### 决策结论

**保留全部现有表结构 + 扩展 User + 新增计费相关表**。

#### User 模型扩展（SQLite → PostgreSQL 同时改造）

```python
class User(Base):
    __tablename__ = "users"

    # 现有字段保留
    id              # SERIAL PK
    display_name    # 昵称
    email           # 邮箱（可选）

    # SaaS 新增：账号体系
    phone                   # VARCHAR(20) UNIQUE - 手机号（主登录凭据）
    password_hash           # VARCHAR(255) - bcrypt 密码
    is_banned               # BOOLEAN DEFAULT FALSE

    # SaaS 新增：积分体系
    credits                 # DECIMAL(10,4) DEFAULT 0 - 充值积分
    gift_credits            # DECIMAL(10,4) DEFAULT 3 - 赠送积分
    gift_credits_expire_at  # TIMESTAMP - 注册后 30 天
    promo_credits           # DECIMAL(10,4) DEFAULT 0 - 推广积分
    promo_credits_expire_at # TIMESTAMP - 获得后 6 个月
    free_generation_used    # BOOLEAN DEFAULT FALSE

    # SaaS 新增：推广体系
    referral_code           # VARCHAR(8) UNIQUE - 推广码
    referred_by             # INT FK(users.id) - 推广者

    # SaaS 新增：统计
    total_recharged         # DECIMAL(10,4) DEFAULT 0
    total_consumed          # DECIMAL(10,4) DEFAULT 0
```

#### 新增表（直接采用 v0.9 设计）

- `usage_logs` —— 用量日志（方案 §6.1 设计不变）
- `recharge_logs` —— 充值记录
- `tasks` —— Celery 任务追踪
- `referral_logs` —— 推广记录
- `withdrawal_logs` —— 兑换记录

#### 保留现有表（不改动）

- `articles` / `article_sections` / `article_contents` —— 核心内容体系
- `article_literature_bindings` / `article_external_references` —— 文献关联
- `polish_sessions` / `polish_changes` —— 润色会话
- `knowledge_docs` / `knowledge_chunks` —— 知识库（SaaS 可选功能）
- `writing_examples` —— Few-shot 示例
- `medical_terms` —— 医学术语库

#### v0.9 方案的 literatures 表改造

v0.9 设计了简单的 `literatures` 表。但现有系统已有完整的文献库：
- `literature_papers` —— 论文主表
- `literature_tags` / `literature_collections` —— 分类
- `paper_chunks` —— 分块存储（RAG 检索）

**结论**：保留现有文献表体系，不采用 v0.9 的简化版。

#### 内容存储策略

v0.9 提出用 COS 存储文章内容。**不采纳**。

| 存储对象 | 存储位置 | 理由 |
|----------|---------|------|
| 文章内容（TipTap JSON/HTML/纯文本） | **PostgreSQL** | 章节级频繁读写，版本管理需结构化查询 |
| 用户上传的 PDF 原始文件 | **腾讯云 COS** | 大文件，低频访问 |
| 导出产物（DOCX/PDF） | **腾讯云 COS** | 生成后按需下载，带签名链接 |
| 文献分析结果 | **PostgreSQL（JSON 字段）** | 随文章一起查询 |

---

## 五、决策 4：门户角色 —— 独立 SaaS 应用

### 现状分析

现有门户系统（`portal-system/`）定位明确：
- PostgreSQL + FastAPI + 管理后台 + Docker Compose
- 服务桌面版的授权码管理、设备绑定、版本分发
- 已有 `MedcommUser` / `MedcommLicenseCode` / `MedcommUserLicense` 等模型
- 已部署在 `api.linscio.com.cn`

### 决策结论

**新建独立 SaaS 应用**，与门户分离但共享基础设施。

```
腾讯云香港 CVM
├── Nginx（统一入口）
│   ├── api.linscio.com.cn      → 门户 API（现有，不动）
│   ├── admin.linscio.com.cn    → 管理后台（现有，不动）
│   ├── writer.linscio.com.cn   → SaaS 写作前端（新建）
│   └── writer-api.linscio.com.cn → SaaS 写作后端（新建）
│
├── Docker Compose（门户组件，现有不动）
│   ├── linscio-db (PostgreSQL)
│   ├── linscio-api
│   └── linscio-admin
│
└── SaaS 写作服务（新建）
    ├── saas-api (FastAPI + Uvicorn)      ← 从 backend/ fork
    ├── saas-celery-worker                 ← 文献分析 + 导出任务
    └── Redis                              ← Celery Broker + 分布式锁
```

**共享的基础设施**：
- PostgreSQL 实例（同一个 PG，不同 schema 或独立数据库）
- Nginx 反向代理
- 腾讯云 COS
- SSL 证书

**隔离的资源**：
- SaaS 有独立的 FastAPI 进程和端口
- SaaS 有独立的 Redis 实例（或 DB 编号隔离）
- SaaS 用户表与门户的 `medcomm_users` 完全独立

**管理后台扩展**：
- 现有 `portal-system/admin` 可扩展 SaaS 管理功能（用户管理、积分监控、成本报表等）
- 或在 SaaS 后端内置 `/admin/` 路由集，独立鉴权（方案 §14.2 的设计）

---

## 六、决策 5：模型选择 —— SaaS 固定路由

### 现状分析

MedComm 的 LLM 管理器已实现完善的多层级路由：

```python
# manager.py - 模型解析优先级
resolve_model():
    1. 用户 DB 设置（Settings 页面选择）     ← 桌面版特有
    2. 环境变量 MEDCOMM_DEFAULT_MODEL
    3. 文章级 default_model（创建时快照）
    4. model_hint 系统推荐
    5. 扫描第一个有 Key 的模型

# TaskTier 分级
QUALITY  → 高质量写作（gpt-4o / claude-sonnet-4-6 / gemini-2.5-pro）
BALANCED → 日常任务（gpt-4o-mini / deepseek-chat / gemini-2.5-flash）
FAST     → 快速响应（gpt-4o-mini / qwen-turbo / glm-4.7-flash）
REASONING → 推理型（deepseek-reasoner / claude-opus-4-6 / gemini-2.5-pro）
```

### 决策结论

SaaS 版新增 **`SaaSTaskRouter`** 模式，按任务类型强制指定模型，不走用户选择链路。

```python
# SaaS 任务路由表（替代 v0.9 的模型指定）
SAAS_TASK_ROUTES = {
    "literature_analysis_abstract": {
        "primary": "kimi-k2.5",           # Kimi 长上下文，摘要短用便宜模型
        "fallback": "deepseek-chat",
        "degraded": "qwen-plus",
        "task_tier": TaskTier.BALANCED,
    },
    "literature_analysis_fulltext": {
        "primary": "gemini-2.5-pro",       # 全文 token 量大，需长上下文
        "fallback": "kimi-k2.5",
        "degraded": "qwen-plus",
        "task_tier": TaskTier.QUALITY,
    },
    "generation_round1": {
        "primary": "gpt-4o",               # 写作质量最高
        "fallback": "deepseek-chat",
        "degraded": "qwen-plus",
        "task_tier": TaskTier.QUALITY,
    },
    "deai_rewrite_round2": {
        "primary": "claude-sonnet-4-6",    # 改写最自然（注：v0.9 用 3.5，现已升级）
        "fallback": "gpt-4o",
        "degraded": "deepseek-chat",
        "task_tier": TaskTier.QUALITY,
    },
    "optimization_round3": {
        "primary": "claude-sonnet-4-6",    # 同上，保持风格一致
        "fallback": "gpt-4o",
        "degraded": "deepseek-chat",
        "task_tier": TaskTier.QUALITY,
    },
}
```

**对现有 manager.py 的改动**：
- 不修改 `resolve_model()` 和 `resolve_model_for_task()` 原有逻辑（桌面版继续使用）
- 新增 `resolve_model_for_saas_task(task_type: str)` 函数，从 `SAAS_TASK_ROUTES` 查表
- SaaS 的 API 层调用新函数，桌面版不受影响

**v0.9 方案模型表的更新**：

| 任务类型 | v0.9 首选 | **v1.0 首选（更新后）** | 变更原因 |
|----------|-----------|------------------------|----------|
| 文献分析（摘要） | Kimi 128k | **kimi-k2.5** | manager.py 里 moonshot 已用 kimi-k2.5 |
| 文献分析（全文） | Gemini 1.5 Pro | **gemini-2.5-pro** | 新版，能力更强 |
| 生成第一轮 | GPT-4o | **gpt-4o**（不变） | — |
| 去AI化第二轮 | Claude Sonnet 3.5 | **claude-sonnet-4-6** | manager.py 已升级到 4-6 |
| 第三轮优化 | Claude Sonnet 3.5 | **claude-sonnet-4-6** | 同上 |

**成本影响**：Claude Sonnet 4-6 的定价可能与 3.5 不同，需要重新核算 v0.9 §3 的积分定价表。建议上线前做一轮实际 API 成本采样。

---

## 七、决策 6：桌面版与 SaaS 版共存

### 决策结论

**双产品线并行，差异化定位**：

| 维度 | 桌面版 MedComm | SaaS 写作平台 |
|------|---------------|--------------|
| 目标用户 | 医院/机构（B 端） | 个人科研工作者/自媒体（C 端） |
| 计费模式 | 年费授权码 | 按需积分 |
| 数据存储 | 本地 SQLite | 云端 PostgreSQL |
| 功能范围 | 全部 17 种形式 + ComfyUI + 知识库 | MVP 4 种形式，逐步开放 |
| 模型选择 | 用户自选（自带 API Key） | 平台固定路由 |
| 技术栈 | Electron + 本地 FastAPI | 纯 Web |

**代码复用策略**：
- `backend/` 仓库 fork 为 `saas-backend/`，初期手动同步核心模块
- 复用的核心模块通过 Git submodule 或包引用管理（远期）
- 共享模块清单：`services/llm/`、`services/medcomm/`、`services/enhancement/`、`services/verification/`、`services/export/`、`services/literature/`、`agents/`、`workflow/`

**门户授权体系**：继续维护，桌面版不受 SaaS 影响。

---

## 八、可复用资产详细映射

### 8.1 LLM 多厂商管理器 → 直接复用

| v0.9 要求 | 现有实现 | 复用程度 |
|-----------|---------|---------|
| 6 家 LLM 接入 | `manager.py` 已覆盖 10+ 家 | 100% |
| 统一 Provider 接口 | `openai_client.py` 统一调用 | 100% |
| 自动降级 | `PROVIDER_PRIORITY` + `TaskTier` | 需新增 SaaS 专用路由 |
| API Key 安全管理 | 环境变量加载 | 改为腾讯云 SSM（部署层改） |

### 8.2 去 AI 化改写引擎 → 核心复用

现有 `deai_rewriter.py` 的三层改写架构：
```
表层（句法）：句式重构 + 添加主语
中层（词汇）：破解模板 + 困惑度提升
深层（语义）：概念具象 + 论证补全 + 风格断裂
```

- v0.9 第二轮「分段去AI化」 → 复用 `rewrite_multi_pass()`，已在 `generator.py` 里自动触发
- v0.9 第三轮「选段 LLM 优化」 → 复用 `ai-assist` API 的 `rewrite` action，按选中字数计费

**需要适配**：
- `rewrite_multi_pass` 当前处理单章节，SaaS 的「分段改写」需要按 500-800 字切分后逐段调用
- 新增计费钩子（改写前检查余额，改写后原子扣费）

### 8.3 AIGC 检测 → 直接复用

现有 `detect_ai_patterns()` 和 `detect_ai_patterns_by_paragraph()`：
- 40+ 条规则匹配（分享催促、列表口水、机械过渡、过度修饰、AI 结尾等 8 大类）
- 段落级检测增强版（句长 Burstiness、词汇 TTR、连接词密度、段首句式重复度、标点均匀度等 7 个维度）
- risk_level: high / medium / low
- 完全本地运算，零 LLM 成本

**v0.9 要求的「免费无限次」** → 完全满足。

**需要新增的展示逻辑**：
- 免费用户：显示总体 AI 率 + 第 1 段完整结果，其余锁定（v0.9 §3.7 的策略）
- 付费用户：全段落完整展示，可触发 LLM 优化

### 8.4 文献分析 → 大部分复用

现有 `analyzer.py` 的 MapReduce 架构：
```
1-2 篇：单次流式分析
≥3 篇：逐篇 _analyze_one_paper → 综合 chat_completion 流式
```

**需要扩展**：
- PDF 上传解析（现有 `pymupdf` 在依赖中，但文献模块主要走在线检索）
- DOI → 全文获取（可通过 CrossRef / Semantic Scholar API 获取元数据和全文链接）
- 字数统计 → 阶梯定价（v0.9 §3.2 的 S/M/L/XL/XXL 档）

### 8.5 导出服务 → 复用 + 扩展

现有导出链路：
```
_merged_export()
  → 章节合并
  → CitationFormatter（参考文献格式化）
  → prepend_export_title_*（标题前置）
  → HtmlDocxExporter / WeasyPrintExporter(PDF)
```

**需要新增**：
- 水印层：带水印版（免费导出）和无水印版（3 积分）
- 零宽字符隐写：`embed_watermark(content, user_id)`（v0.9 §9.5 的方案可直接实现）

### 8.6 润色/优化 → 复用

| v0.9 功能 | 现有实现 | 复用方式 |
|-----------|---------|---------|
| 第三轮选段改写 | `ai-assist` API (`rewrite` action) | 加计费钩子 |
| 系统提示 | `_DEAI_SYSTEM_PROMPT` | 直接复用 |
| 流式输出 | `chat_completion(stream=True)` | 直接复用 |

### 8.7 现有能力补充纳入

以下现有能力 v0.9 未提及，建议纳入 SaaS 以提升竞争力：

| 能力 | 来源模块 | SaaS 定位 | 计费 |
|------|---------|-----------|------|
| 医学术语规范化 | `normalize_terms` 节点 | 生成流程内置 | 免费（包含在生成费用中） |
| 医学声明验证 | `verify_medical_claims` 节点 | 生成流程内置 | 免费 |
| 阅读难度检查 | `check_reading_level` 节点 | 生成流程内置 | 免费 |
| RAG 上下文检索 | `RAGRetriever` + FTS5 | 提升生成质量 | 免费 |
| 章节版本管理 | `ArticleContent.version` | 用户可回退 | 免费 |
| 配图建议 | `suggest_images` 节点 | 文字描述配图方案 | 免费 |

---

## 九、写作流程细化（修订 v0.9 §2）

v0.9 的三轮流程过于简化，结合现有系统的成熟管线，修订为：

```
用户创建文章
  ├── 选择内容形式（MVP：article/story/debunk/qa_article）
  ├── 选择目标平台（微信/小红书/通用等）
  ├── 设置受众和阅读难度
  └── 设置目标字数

文献上传/导入
  ├── PDF 上传（提取全文，统计字数 → 阶梯定价）
  ├── DOI 输入（自动获取论文元数据）
  └── PubMed/Semantic Scholar 检索（现有能力）

文献分析（积分扣费点 1）
  ├── 摘要模式：0.5 积分/篇
  └── 全文模式：按字数阶梯 1-8 积分

章节生成（积分扣费点 2，SSE 流式）
  ├── 按形式的章节结构逐段生成（SECTION_TYPES_BY_FORMAT）
  ├── 每段自动触发：
  │   ├── RAG 上下文注入（文献 + 知识库）
  │   ├── 医学声明验证
  │   └── 去AI化多轮改写（deai_rewriter）
  ├── 生成完成后自动 AIGC 检测
  └── 用户可逐章审阅和调整

用户精修（第三轮）
  ├── 自己手改（免费）
  ├── 选段 LLM 优化（积分扣费点 3，按字数计费）
  └── 随时触发 AIGC 检测（免费）

导出（积分扣费点 4）
  ├── 带水印导出（免费）
  └── 无水印导出 Word/PDF（3 积分）
```

### 与 v0.9 的关键差异

1. **章节逐段生成**替代整篇一次生成 —— 用户体验更好，可中途调整
2. **SSE 流式输出**替代 Celery 轮询 —— 实时看到内容出现
3. **RAG + 医学验证**自动集成在生成流程中 —— v0.9 未提及但对科普质量至关重要
4. **去AI化是生成流程的一部分**，不是独立的「第二轮」—— 用户只感知一次「生成」
5. **积分计费点集中**：生成费用 = 第一轮 + 第二轮合并计费（v0.9 设计不变）

---

## 十、积分体系适配（修订 v0.9 §3）

v0.9 的积分体系设计整体合理，仅需以下微调：

### 10.1 模型成本更新

v0.9 基于 Claude Sonnet 3.5 / Gemini 1.5 Pro 等老模型定价。现有系统已升级到：
- Claude Sonnet 4-6（输出成本可能变化）
- Gemini 2.5 Pro / Flash
- Kimi K2.5

**建议**：上线前做一轮成本采样（各任务类型各跑 100 次，统计平均 token 消耗），重新核算毛利。

### 10.2 积分扣费 SQL 适配 PostgreSQL

v0.9 的原子扣费 SQL 在 PostgreSQL 下完全适用，但建议加 `RETURNING`：

```sql
UPDATE users
SET credits = credits - :cost,
    total_consumed = total_consumed + :cost,
    updated_at = NOW()
WHERE id = :user_id
  AND credits >= :cost
RETURNING credits;
```

返回更新后余额，减少一次查询。

### 10.3 积分消耗优先级实现

v0.9 的三级优先级（赠送 → 推广 → 充值）需要事务内多步操作：

```python
async def deduct_credits(user_id: int, cost: Decimal, db: AsyncSession) -> dict:
    """
    三级优先级扣费，事务内原子操作。
    返回 {"success": bool, "breakdown": {...}, "remaining": Decimal}
    """
    user = await db.get(User, user_id, with_for_update=True)  # 行锁

    remaining_cost = cost
    breakdown = {}

    # 1. 赠送积分（检查有效期）
    if user.gift_credits > 0 and user.gift_credits_expire_at > now():
        use = min(user.gift_credits, remaining_cost)
        user.gift_credits -= use
        remaining_cost -= use
        breakdown["gift"] = float(use)

    # 2. 推广积分（检查有效期）
    if remaining_cost > 0 and user.promo_credits > 0 and user.promo_credits_expire_at > now():
        use = min(user.promo_credits, remaining_cost)
        user.promo_credits -= use
        remaining_cost -= use
        breakdown["promo"] = float(use)

    # 3. 充值积分
    if remaining_cost > 0:
        if user.credits < remaining_cost:
            return {"success": False}
        user.credits -= remaining_cost
        breakdown["credits"] = float(remaining_cost)

    user.total_consumed += cost
    await db.flush()
    return {"success": True, "breakdown": breakdown, "remaining": user.total_credits}
```

---

## 十一、安全机制补充（修订 v0.9 §10）

### 11.1 前端防复制 —— 降低预期

v0.9 的 `Ctrl+C` 拦截方案技术上**极易绕过**（开发者工具控制台一行代码即可解除所有事件监听）。

**建议**：
- 前端拦截仅作为「礼貌性提醒」，不要视为安全屏障
- 真正的防护靠**后端零宽字符隐写**（v0.9 §9.5 的方案有效）
- 追加措施：生成内容不在前端暴露纯文本，而是通过 TipTap 编辑器渲染 JSON 结构

### 11.2 并发安全 —— Redis 分布式锁

v0.9 的 `UPDATE WHERE credits >= cost` 在 PostgreSQL 下是行级锁安全的。但对于 SSE 长连接场景，建议额外加 Redis 分布式锁：

```python
async def acquire_operation_lock(user_id: int, operation: str, ttl: int = 60):
    """防止同一用户同一操作的并发重复提交"""
    key = f"op_lock:{user_id}:{operation}"
    return await redis.set(key, "1", ex=ttl, nx=True)
```

---

## 十二、技术迁移路径（修订 v0.9 §13）

### Phase 0：基础设施（1 周）

- [ ] 腾讯云 CVM 2核4GB + 托管 PostgreSQL + Redis 部署
- [ ] `backend/` fork 为 `saas-backend/`
- [ ] `database.py` 改为 PostgreSQL 连接（`asyncpg` 替代 `aiosqlite`）
- [ ] 去除 SQLite 特有代码（PRAGMA、WAL、分域锁等）
- [ ] Alembic 初始化 + 数据模型迁移脚本
- [ ] 去除 Electron / ComfyUI / Ollama 相关依赖

### Phase 1：核心流程 SaaS 化（3-4 周）

- [ ] User 模型扩展 + 手机号注册/登录 + JWT（替换现有 HMAC token）
- [ ] 积分系统（credit_service.py：预检/扣费/余额/三级优先级）
- [ ] 文献分析 SaaS 化（PDF 上传 + 字数统计 + 阶梯定价）
- [ ] 章节生成 SaaS 化（`generator.py` 加积分钩子 + SaaS 模型路由）
- [ ] AIGC 检测展示（分段标红 + 免费用户锁定）
- [ ] Vue 3 SaaS 前端（去 Electron，新写作流程页面）
- [ ] Celery 配置（文献分析 + 导出任务）

### Phase 2：商业化闭环（2-3 周）

- [ ] 积分充值 + 易支付对接（回调、签名验证、幂等处理）
- [ ] 第三轮 LLM 优化（基于 ai-assist，字符级计费）
- [ ] 导出水印/无水印逻辑
- [ ] 零宽字符隐写
- [ ] 新用户体验流程（3 积分赠送 + 1 次免费生成）
- [ ] Nginx SSL 配置 + 域名解析

### Phase 3：运营增长（持续）

- [ ] 管理后台（成本监控 + 用户管理 + 模型路由调整）
- [ ] 推广系统（推广码 + 返利 + 兑现审核）
- [ ] 更多内容形式开放（story / debunk / oral_script...）
- [ ] 监控告警（LLM 成本 / 错误率 / 用户行为）
- [ ] 知识库功能开放（按上传量计费）

---

## 十三、附录：v0.9 逐章对照表

| v0.9 章节 | 适配结论 |
|-----------|---------|
| §1 项目概述 | 产品定位更新：渐进开放多形式 |
| §2 写作流程 | 改为章节逐段生成，SSE 流式，自动集成验证+去AI化 |
| §3 收费体系 | 整体保留，模型成本需重新核算（升级到 Claude 4-6 / Gemini 2.5） |
| §4 系统架构 | 改为 SSE + Celery 混合架构，去掉纯 Celery 轮询 |
| §5 LLM 接入 | 复用现有 manager.py，新增 SaaS 固定路由表 |
| §6 积分扣费逻辑 | 保留，PostgreSQL RETURNING 优化 |
| §7 数据库设计 | 以现有模型为基础扩展，不从零重建 |
| §8 支付方案 | 保留（易支付方案不变） |
| §9 服务器配置 | 保留，与现有门户共享 CVM |
| §10 前端技术 | 保留 Vue 3 + Element Plus，去掉 Electron 依赖 |
| §11 项目目录 | 从 backend/ fork，保留核心服务目录结构 |
| §12 监控运营 | 保留 |
| §13 开发阶段 | 更新为四阶段（含 Phase 0 基础设施） |
| §14 数据安全 | 保留 + 补充前端防复制的局限性说明 |
| §15 推广方案 | 保留（设计合理） |
| §16 风险应对 | 保留 + 补充 Claude 4-6 成本变动风险 |
