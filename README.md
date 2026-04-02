# LinScio MedComm

医学科普写作智能体桌面客户端 · Electron + Vue 3 + FastAPI + SQLite + LangGraph

## 版权与使用范围

- **权利保留**：本仓库内的源代码、文档与配套资源，其著作权及相关知识产权由 **LinScio**（或权利人）保留。`package.json` 中 `license` 为 `UNLICENSED`，**不表示**以 MIT 等开源许可证向公众授权；未获书面许可，不得擅自将本仓库用于商业再分发、对外提供同源托管服务或规避产品授权机制。
- **终端用户**：通过官方安装包或受控渠道使用 MedComm 时，须遵守 LinScio 公布的 **《服务条款》** 与 **《隐私政策》**。请以线上**当前有效版本**为准，常见入口为官网 / 门户页脚或法务栏目：
  - [MedComm 官网](https://medcomm.linscio.com.cn)
  - [LinScio 门户](https://www.linscio.com.cn)
- **依赖组件**：第三方库（如 `node_modules` 所涉项目）仍各自适用其原有许可证，不因本仓库整体为专有软件而改变。

## 快速开始

### 环境要求

- Node.js 18+
- Python 3.11+
- 推荐使用 pnpm 或 npm

### 安装

```bash
npm install
pip install -r backend/requirements.txt
```

### 开发模式

**终端 1 - 后端：**
```bash
cd backend && OPENAI_API_KEY=sk-xxx python run.py
```
> AI 生成功能需配置 `OPENAI_API_KEY` 环境变量

**终端 2 - 前端：**
```bash
npm run dev
```

**终端 3 - Electron（可选）：**
```bash
NODE_ENV=development npm run electron:dev
```

或直接访问 http://localhost:5173 使用 Web 模式。

### 构建

```bash
npm run build
npm run electron:build
```

## 项目结构

```
linscio-medcomm/
├── electron/          # Electron 主进程
├── frontend/          # Vue 3 前端
├── backend/           # FastAPI 后端
│   ├── app/
│   │   ├── api/       # API 路由
│   │   ├── models/    # ORM 模型
│   │   ├── services/  # 业务逻辑（含 format_router）
│   │   └── core/      # 配置、数据库、锁
│   └── run.py
└── package.json
```

## 核心特性

- **17 种科普形式** × **7 种发布平台**（形式路由器 format_router）
- **形式感知编辑器**：按 content_format 加载对应 Tiptap 扩展
- **分域写锁**：articles / images / literature / knowledge / examples / system
- **SQLite WAL 模式**：单文件数据库，零配置

## 已完成开发阶段

- ✅ **阶段一**：Alembic 迁移、完整 ORM 模型
- ✅ **阶段二**：useFormatEditor、6 个 Tiptap 扩展、EditorToolbar
- ✅ **阶段三**：RAG + Few-shot + 术语注入骨架
- ✅ **阶段四**：防编造验证链路
- ✅ **阶段五**：BaseAgent + MedCommSectionState + 写作图骨架

## 后续开发（已完成）

- ✅ LLM 接入（OpenAI + 模型优先级）
- ✅ 章节生成 SSE 流式 API + AI 生成按钮
- ✅ FTS5 全文检索骨架 + RAG 降级
- ✅ 图像生成引擎骨架
- ✅ API Key 测试接口 `POST /api/v1/system/apikey/test`

## 开发方案

详见 `LinScio_MedComm_开发方案_v6.md`
