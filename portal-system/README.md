# LinScio AI · 聆思恪 门户 · 管理后台 · 镜像仓库

基于 [LinScio_AI_完整开发方案_v4](../docs/README.md) 的工程目录，包含门户网站、管理后台、FastAPI 后端及 Docker Compose 编排。

## 目录结构

```
portal-system/
├── docker-compose.yml    # 统一编排：DB、API、门户、管理后台、Registry、Registry UI
├── docker-compose.prod.yml # 可选：生产环境内存限制（4 GB 机器）
├── .env.example          # 环境变量示例（复制为 .env 后填写）
├── .env.production.example # 生产环境示例（腾讯云 + 域名 linscio.com.cn）
├── api/                  # FastAPI 后端（含 Dockerfile）
├── portal/               # 门户前端（Vue 3 + Vite，含 Dockerfile）
├── admin/                # 管理后台（Vue 3 + Element Plus + ECharts + Vite，含 Dockerfile）
├── registry/auth/        # htpasswd 目录（部署时生成 htpasswd 文件）
├── registry/config.yml   # Registry 显式配置（挂载进容器，减少 panic）
├── registry-ui/          # Registry UI 自定义镜像（Nginx 请求时解析 upstream，避免启动 panic）
├── deploy/               # 部署配置（如宝塔 Nginx 反向代理）
├── docs/                 # 部署文档（如腾讯云轻量 + 宝塔）
└── data/                 # 持久化数据（可选，生产可改为 bind mount）
```

## Docker 容器化部署（推荐）

**所有部署均通过 Docker 命令完成**，无需在宿主机安装 Node、npm 或单独构建前端；管理后台所需依赖（含 ECharts）在构建镜像时由 `npm install` 自动安装。

### 1. 环境变量

```bash
cp .env.example .env
# 编辑 .env：POSTGRES_PASSWORD、JWT_SECRET_KEY、AES_SECRET_KEY、AES_IV 等
```

### 2. Registry 认证文件（必做，否则 Registry 会 panic）

Registry 使用 `REGISTRY_AUTH=htpasswd`，**必须先存在 `registry/auth/htpasswd` 再启动**，否则会报错退出。

**方式一（推荐，仅用 Docker）：**

```bash
chmod +x scripts/create-registry-htpasswd.sh
./scripts/create-registry-htpasswd.sh
# 默认用户 registry / 密码 registry（开发用）。生产可传参: ./scripts/create-registry-htpasswd.sh 你的用户 强密码
```

**方式二（一行命令）：**

```bash
mkdir -p registry/auth
docker run --rm -v "$(pwd)/registry/auth:/out" --entrypoint sh httpd:2.4 -c "htpasswd -Bbn registry registry > /out/htpasswd"
```

### 3. 一键构建并启动

```bash
cd portal-system
docker compose build
docker compose up -d
```

- **linscio-db**：PostgreSQL 16  
- **linscio-api**：FastAPI 后端（从 `api/Dockerfile` 构建）  
- **linscio-portal**：门户前端（从**仓库根** context 使用 `portal/Dockerfile.with-docs` 构建，**已含帮助文档** `/docs/`，无需单独执行 `make docs-build-portal`）  
- **linscio-admin**：管理后台（从 `admin/Dockerfile` 构建，**含 ECharts**，Node 构建 + Nginx 运行）  
- **linscio-registry**：镜像仓库（registry:2，仅容器内 5000，不直接对外）
- **linscio-registry-proxy**：拉取代理（同 API 镜像，对外 5000，按套餐 Tag 白名单校验后转发至 Registry）
- **linscio-registry-ui**：Registry UI（从 `registry-ui/Dockerfile` 构建，基于 joxit，直连 linscio-registry）  

### 4. 访问地址

| 服务       | 地址                      |
|------------|---------------------------|
| 门户       | http://localhost:3000     |
| 管理后台   | http://localhost:3001     |
| API        | http://localhost:8001     |
| Registry（拉取经代理） | http://localhost:5003     |
| Registry UI| http://localhost:5002     |

**网址与端口完整对应**（见下方「网址与端口对应表」）。

**网址与端口对应表**

| 项目 / 服务 | 宿主机端口 | 本机访问地址 | 生产域名示例（宝塔 Nginx 反代） |
|-------------|------------|--------------|----------------------------------|
| 门户前端 | 3000 | http://localhost:3000 | https://www.linscio.com.cn |
| 管理后台 | 3001 | http://localhost:3001 | https://admin.linscio.com.cn |
| API 后端 | 8001 | http://127.0.0.1:8001 | https://api.linscio.com.cn |
| 镜像仓库拉取代理（docker login/pull） | 5003 | http://127.0.0.1:5003 | https://registry.linscio.com.cn |
| Registry Web UI | 5002 | http://127.0.0.1:5002 | https://hub.linscio.com.cn |

- 根域 linscio.com.cn 一般 301 跳转到 www（门户）。linscio-registry（5000）、linscio-db（5432）仅容器间访问，不映射宿主机。
- 健康检查：API → `http://127.0.0.1:8001/health`，Registry 代理 → `http://127.0.0.1:5003/health`。

**门户「帮助文档」**（`/docs/`）：`docker compose build linscio-portal` 已使用含文档的 Dockerfile（仓库根 context + `portal/Dockerfile.with-docs`），**一次构建即包含** `/docs/`，无需先执行 `make docs-build-portal` 或 `make build-portal-with-docs`。直接 `docker compose up -d linscio-portal` 即可。

门户与管理后台容器内 Nginx 已将 `/api` 代理到 `linscio-api:8001`，无需在宿主机再配反向代理即可调用接口。

**门户用户中心**：登录后进入「用户中心」为「我的授权」+「下载」；激活后在「下载」页获取安装包为主，Docker 方式为可选。套餐与周期配置参考见仓库根目录 **docs/套餐与周期-设置参考.md**。

**若管理后台页面显示「加载失败」**：  
1）确认已创建管理员：`./scripts/create-admin.sh`（默认 admin / admin123）；  
2）确认 `linscio-api` 容器已启动：`docker compose ps`，且无报错；  
3）打开浏览器开发者工具（F12）→ Network 查看 `/api/v1/admin/stats` 是否返回 401/500，Console 是否有报错；  
4）查看 API 日志：`docker compose logs linscio-api`，若有 500 会打印具体异常。

**若门户/管理后台「无法访问此网络」**：  
1）确认容器已启动：`docker compose ps`，linscio-portal、linscio-admin 状态为 Up；  
2）使用本机浏览器访问：**http://localhost:3000**（门户）、**http://localhost:3001**（管理后台）；若 localhost 无法解析可改用 **http://127.0.0.1:3000**；  
3）若仍无法访问，查看容器日志：`docker compose logs linscio-portal`，确认 Nginx 已监听 80；  
4）端口已绑定到 0.0.0.0（3000:80、3001:80），本机任意网卡均可访问；若需从其他机器访问，需放通防火墙对应端口。

**若出现 502 Bad Gateway**：表示 Nginx 无法连上后端 API。请先确认 `linscio-api` 已健康：`docker compose ps` 中 linscio-api 为 `Up (healthy)` 后再访问管理后台。编排已为 linscio-api 配置健康检查（/health），linscio-admin 与 linscio-portal 会等 API 就绪后再启动；若仍 502，可执行 `docker compose restart linscio-api` 等待约 30 秒后刷新页面。

**若 linscio-api 日志出现 `password authentication failed for user "linscio_user"`**：说明 `.env` 中的 `POSTGRES_PASSWORD` 与 PostgreSQL 当前密码不一致（Postgres 仅在**首次**创建数据卷时把该环境变量设为 `linscio_user` 的密码，之后改 .env 不会自动更新库内密码）。可选修复方式：

- **方式 A（推荐）**：把 `.env` 里的 `POSTGRES_PASSWORD` 改回你**第一次**跑 `docker compose up` 时用的那个密码，然后执行 `docker compose restart linscio-api`。
- **方式 B**：若已忘记当时用的密码，只能重建数据库（**会清空库内所有数据**）。在 portal-system 目录下执行：
  ```bash
  docker compose down
  docker volume rm portal-system_postgres-data
  # 确认 .env 中 POSTGRES_PASSWORD 为你要用的密码
  docker compose up -d
  ```
  启动后需重新创建管理员：`./scripts/create-admin.sh`（默认 admin / admin123）。

### 5. 仅重建前端镜像（例如修改了 portal/admin 或 linscio-docs）

门户镜像构建已含帮助文档（见上文），直接重建并启动即可：

```bash
docker compose build linscio-portal linscio-admin
docker compose up -d linscio-portal linscio-admin
```

### 6. 首次管理员账号（必做，否则无法登录管理后台）

管理后台**不会自动创建**管理员，需执行以下任一方式创建默认账号（用户名 **admin**，密码 **admin123**）：

创建的管理员会**同步写入镜像仓库认证**（registry/auth/htpasswd），可用**同一账号**登录：
- **管理后台**：http://localhost:3001  
- **Registry UI**：http://localhost:5001  
- **docker login**：`docker login localhost:5000`（用户名/密码与管理员一致）

**方式一（推荐）：**

```bash
chmod +x scripts/create-admin.sh
./scripts/create-admin.sh
# 自定义账号: ./scripts/create-admin.sh 我的用户名 我的密码
```

**方式二（直接执行 API 容器内脚本）：**

```bash
docker compose exec linscio-api python scripts/create_admin.py
# 自定义: docker compose exec -e ADMIN_USERNAME=myadmin -e ADMIN_PASSWORD=mysecret linscio-api python scripts/create_admin.py
```

创建成功后，在 http://localhost:3001 使用 **admin / admin123** 登录（或你自定义的账号）。  
若 Registry 已先启动，执行一次 **`docker compose restart linscio-registry`** 以重新加载认证后，再用同一账号登录 Registry UI 或 `docker login`。

**管理员或镜像仓库认证被删后恢复**：再次执行 `./scripts/create-admin.sh [用户名 [密码]]` 即可恢复（会写入数据库并同步到 htpasswd）；若需同时修改已有管理员密码，使用 `./scripts/create-admin.sh 用户名 新密码 update`。详见 [docs/部署-腾讯云轻量与宝塔.md](docs/部署-腾讯云轻量与宝塔.md#44-恢复管理员含镜像仓库)。

### 7. 批量生成授权码：套餐与周期、模块权限（第一优先级在管理后台配置）

批量生成授权码依赖 **plans**、**billing_periods** 表有数据；授权码的 **module_mask** 依赖 **module_definitions** 中受控模块配置。

- **套餐与周期**：推荐在管理后台「套餐与周期」中直接添加（菜单位置：用户管理 与 授权码管理 之间），添加至少一个套餐和一个付费周期后，即可在「授权码管理」→「批量生成」中使用。
- **模块权限配置**：6 个受控模块（schola、medcomm、qcc、literature、analyzer、image_studio）在 **API 启动时会自动补齐**到 `module_definitions`，无需手动逐个添加。也可在管理后台「模块权限配置」页点击 **「一键初始化受控模块」** 或执行预置脚本（见下）一次性写入；修改各套餐开关后，新生成的授权码将按此计算 module_mask，已激活用户需点击「批量更新凭证」后生效。
- **新部署**：登录管理后台 → 进入「套餐与周期」→ 新增套餐、新增周期；模块权限已自动补齐，无需操作。
- **已有库升级**：若从旧版本升级且尚未有 `billing_periods.name` 或 `module_definitions.enterprise_enabled/beta_enabled` 列，需执行一次数据库迁移（见下文「§12 数据库迁移汇总」）。
- **可选预置**：若希望一次性写入多组套餐/周期/全部模块（含非受控展示用模块），可执行预置脚本（Docker 部署时）：
  ```bash
  docker compose exec linscio-api python scripts/seed_plans_periods_modules.py
  ```
  本地跑 API 时在 `api` 目录下执行：`python scripts/seed_plans_periods_modules.py`（需已设置 `.env` 中的 `DATABASE_URL`）。  
  预置后仍可在「套餐与周期」中增删改。

### 8. 若 Registry 容器不断重启

1. **查看日志确认原因**：`docker logs portal-system-linscio-registry-1`（或当前项目下对应的 registry 容器名）。常见为 `panic` 且提示与 `htpasswd` 相关。
2. **确保 htpasswd 已生成**：必须先执行 `./scripts/create-registry-htpasswd.sh`（或方式二的一行命令），再 `docker compose up -d`。
3. **确认文件存在且非空**：`ls -la registry/auth/htpasswd`，应有一行内容（如 `registry:$2y$05$...`）。
4. **数据卷权限**：若曾以不同用户运行过 Registry，可尝试仅删除 Registry 卷后重起：`docker volume rm portal-system_registry-data`（或当前项目对应的 volume 名），再 `docker compose up -d`。**切勿使用 `docker compose down -v`**：它会删除**所有**命名卷（含 `postgres-data`），导致已注册用户、授权码等数据全部丢失；仅在做**全新部署且无需保留任何数据**时使用。
5. **“could not create registry”**：多为对 `registry-data` 卷无写权限。已在 compose 中为 `linscio-registry` 设置 `user: "0:0"` 以 root 写卷；若仍报错，可先 `docker volume rm portal-system_registry-data`（或当前项目对应的 volume 名）再 `docker compose up -d` 重新建卷。

### 9. 镜像仓库（Registry UI）使用管理员账号无法登录

Registry 与 Registry UI 的认证来自 **registry/auth/htpasswd**，管理员账号需**显式同步**到该文件并**重启 Registry** 后才会生效。

**操作步骤：**

1. **确认 API 对 registry/auth 可写**：`docker-compose.yml` 中 `linscio-api` 的 `./registry/auth` 挂载**不要**带 `:ro`。
2. **执行同步脚本**（将当前管理员用户名、密码写入 htpasswd，并自动重启 Registry）：
   ```bash
   chmod +x scripts/sync-admin-to-registry.sh
   ./scripts/sync-admin-to-registry.sh 你的管理员用户名 '你的管理员密码'
   ```
   密码含特殊字符时请用单引号包住，例如：`./scripts/sync-admin-to-registry.sh xiaoshiqi 'Yeahchy@07102'`
3. 等待 Registry 重启完成（约 5～10 秒），再在 **Registry UI**（http://localhost:5001）或 **docker login localhost:5000** 用同一组用户名、密码登录。

若同步脚本报错「同步失败」，请检查：API 容器是否已用最新 compose 启动（无 `:ro`）、本机是否存在 `registry/auth` 目录且可写。

### 10. 下载中心（安装包下载）

门户提供 **下载** 页（导航「下载」或 `/download`）：用户输入授权码后可获取当前版本安装包的 COS 预签名下载链接（2 小时有效）。

**启用前需满足：**

1. **配置腾讯云 COS**：在 `.env` 中设置 `COS_SECRET_ID`、`COS_SECRET_KEY`（`COS_BUCKET`、`COS_REGION` 已有默认值）。未配置时接口返回「下载服务暂未配置」。
2. **至少有一条「当前版本」记录**：在数据库表 `release_versions` 中插入一条且将 `is_current` 设为 `true`，`file_key` 为 COS 桶内对象路径（如 `releases/v1.0.0/linscio-ai-v1.0.0.tar.gz`）。

**示例（首次插入当前版本）：**

```sql
INSERT INTO release_versions (id, version, file_key, file_size, release_notes, is_current, created_at)
VALUES (
  gen_random_uuid()::text,
  '1.0.0',
  'releases/v1.0.0/linscio-ai-v1.0.0.tar.gz',
  0,
  '首次发布',
  true,
  now()
);
```

执行方式：`docker compose exec linscio-db psql -U linscio_user -d linscio_portal -c "INSERT INTO ..."` 或通过管理端（若已实现版本管理）。上传安装包到 COS 的路径需与 `file_key` 一致，详见 [docs/发版-SOP.md](../docs/发版-SOP.md)。

### 11. 已有数据库升级（container-token 全栈方案）

若门户数据库在接入「container-token + 账号状态」方案之前已存在（缺少 `portal_users` 新字段或 `container_tokens`、`orders`、`container_machine_bindings` 表），需执行一次 SQL 迁移：

```bash
docker compose exec -T linscio-db psql -U linscio_user -d linscio_portal < api/scripts/migrate_container_token_schema.sql
```

新部署由 API 启动时自动建表（`Base.metadata.create_all`），无需执行此脚本。

### 12. 数据库迁移汇总（已有库升级时按需执行）

| 迁移 | 说明 | 执行命令 |
|------|------|----------|
| **container-token** | portal_users 扩展 + container_tokens / orders / container_machine_bindings | `docker compose exec -T linscio-db psql -U linscio_user -d linscio_portal < api/scripts/migrate_container_token_schema.sql` |
| **billing_periods.name** | 套餐与周期优化：为付费周期表增加显示名字段 | `docker compose exec -T linscio-db psql -U linscio_user -d linscio_portal < api/scripts/migrate_billing_period_name.sql` |
| **module_definitions 旗舰/内测** | 模块权限：为 module_definitions 增加 enterprise_enabled、beta_enabled 列 | `docker compose exec -T linscio-db psql -U linscio_user -d linscio_portal < api/scripts/migrate_module_definitions_enterprise_beta.sql` |

新部署无需执行；从旧版本升级时若缺少对应表/列，按上表执行相应迁移即可。迁移脚本均为幂等（已存在则跳过）。详细说明与执行顺序见 **api/scripts/README.md**。

---

## 本地开发

### 1. 环境变量

```bash
cp .env.example .env
# 编辑 .env：POSTGRES_PASSWORD、JWT_SECRET_KEY、AES_SECRET_KEY、AES_IV
```

### 2. 启动数据库与后端

```bash
docker compose up -d linscio-db
# 等待健康后
docker compose up -d linscio-api
```

或本地跑 API（需本机 Python 3.12、已安装依赖）：

```bash
cd api
pip install -r requirements.txt
# 设置 .env 中 DATABASE_URL=postgresql+asyncpg://linscio_user:xxx@localhost:5432/linscio_portal
uvicorn main:app --reload --port 8001
```

### 3. 门户前端

```bash
cd portal
npm install
npm run dev   # http://localhost:3000，代理 /api -> 8001
```

### 4. 管理后台

```bash
cd admin
npm install
npm run dev   # http://localhost:3001，代理 /api -> 8001
```

**若登录时出现 502 Bad Gateway**：表示前端代理无法连上后端。请先启动 API（见上文「2. API」），确保 `http://localhost:8001/health` 可访问后再登录；管理员账号需先执行「5. 首次管理员账号」或 `./scripts/create-admin.sh`（默认 admin / admin123）。

### 5. 首次管理员账号

数据库首次启动后需手动插入管理员（或通过脚本）：

```bash
cd api
python -c "
import asyncio
from app.database import AsyncSessionLocal
from app.models import AdminUser
from app.services.auth_service import hash_password

async def main():
    async with AsyncSessionLocal() as db:
        admin = AdminUser(username='admin', password_hash=hash_password('your-admin-password'), scope='super')
        db.add(admin)
        await db.commit()
asyncio.run(main())
"
```

## 生产部署（概要）

1. 服务器创建目录，上传本仓库。
2. 配置 `.env`（强密码、CORS、REGISTRY_URL 等）；生产可参考 **`.env.production.example`**（域名 linscio.com.cn）。
3. 确保 `registry/auth/` 下**已有 htpasswd 文件**（参见上文「Registry 认证文件」），否则 Registry 启动会 panic。
4. **仅通过 Docker 部署**：`docker compose build && docker compose up -d`。无需在宿主机执行 `npm install` 或 `npm run build`，门户与管理后台（含 ECharts）均在镜像构建时完成。
5. 使用 Nginx/宝塔 将域名反向代理到 127.0.0.1:3000/3001/8001/5002/5003；**腾讯云轻量 + 宝塔 + 域名 linscio.com.cn** 的完整步骤见 **[docs/部署-腾讯云轻量与宝塔.md](docs/部署-腾讯云轻量与宝塔.md)**，内含**部署架构总览**、各组件部署方式、端口规划及宝塔 Nginx 配置示例（`deploy/baota-nginx-linscio.conf`）。
   - **域名备案前**：可临时使用公网 IP 提供镜像拉取，见 **[docs/临时使用公网IP作为镜像仓库.md](docs/临时使用公网IP作为镜像仓库.md)**。

**交付纯净版**：需去除 node_modules、.env 等交付时，在项目根目录执行 `./scripts/make-delivery.sh`，会在上级目录生成 **.tar.gz** 与 **.zip** 两个包。部署方若使用腾讯云/宝塔**网页文件管理**上传，请使用 **.zip**（可右键解压）；**.tar.gz 在网页文件管理中无法直接打开**，需通过 SSH 执行 `tar -xzf` 解压。部署按 **[docs/交付版-腾讯云服务器部署指南.md](docs/交付版-腾讯云服务器部署指南.md)** 在腾讯云服务器上从零操作。

## API 接口摘要

- **用户端**：`POST /api/v1/auth/register|login`，`GET /api/v1/user/profile`，`POST /api/v1/user/activate`，`GET /api/v1/user/license`，`GET /api/v1/user/registry-credential`。
- **管理端**：`POST /api/v1/admin/auth/login`，`GET /api/v1/admin/users|licenses|stats`，`GET /api/v1/admin/plans`、`GET /api/v1/admin/billing-periods`（批量生成用），`GET /api/v1/admin/plans/manage`、`POST|PATCH /api/v1/admin/plans`、`GET /api/v1/admin/billing-periods/manage`、`POST|PATCH /api/v1/admin/billing-periods`（套餐与周期管理），`GET /api/v1/admin/modules`、`PATCH /api/v1/admin/modules/{id}`、`POST /api/v1/admin/modules`、`POST /api/v1/admin/modules/seed-controlled`（一键初始化受控模块），`POST /api/v1/admin/users/{user_id}/refresh-credential`（用户管理-更新凭证），`POST /api/v1/admin/licenses/batch`，`POST /api/v1/admin/registry-credentials/sync-modules`（批量更新凭证）。
- **与主产品衔接**：授权校验接口 **validate** / **heartbeat** 的响应中包含 `allowed_login_usernames`（admin + 当前授权码绑定用户的门户用户名），主产品据此做项目端登录管控（允许名单 + 首次登录一次性门户校验 + 本地缓存）；详见仓库根 **docs/下载与项目端登录逻辑说明.md**。

详见开发方案 v4 文档。

## 相关文档

| 文档 | 说明 |
|------|------|
| [docs/README.md](docs/README.md) | 文档索引 |
| [docs/部署-腾讯云轻量与宝塔.md](docs/部署-腾讯云轻量与宝塔.md) | 生产部署：域名规划、部署架构、各组件与端口、宝塔 Nginx |
| [deploy/baota-nginx-linscio.conf](deploy/baota-nginx-linscio.conf) | 宝塔 Nginx 反向代理配置示例 |
| [api/scripts/migrate_container_token_schema.sql](api/scripts/migrate_container_token_schema.sql) | 已有库升级：container-token 相关表与字段 |
| [api/scripts/migrate_billing_period_name.sql](api/scripts/migrate_billing_period_name.sql) | 已有库升级：billing_periods.name（套餐与周期优化） |
| [api/scripts/migrate_module_definitions_enterprise_beta.sql](api/scripts/migrate_module_definitions_enterprise_beta.sql) | 已有库升级：module_definitions 旗舰版/内测版开关列 |
| [api/scripts/README.md](api/scripts/README.md) | 门户迁移脚本索引与执行顺序 |
| [../docs/套餐与周期-设置参考.md](../docs/套餐与周期-设置参考.md) | 套餐与周期在管理后台逐项填写参考（买断+年维护费） |
| [.env.production.example](.env.production.example) | 生产环境变量示例（linscio.com.cn） |
