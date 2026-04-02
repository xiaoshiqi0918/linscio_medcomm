# LinScio MedComm v3 授权体系 - 开发说明

基于《LinScio_MedComm_授权体系方案_v3.md》的首阶段实现。

## 一、已实现内容

### 1. 数据库（MedComm 专用表，与现有 portal 并存）

| 表名 | 说明 |
|------|------|
| medcomm_users | 用户（email/phone 双渠道） |
| medcomm_license_codes | 授权码（LINSCIO-XXXX-XXXX-XXXX） |
| medcomm_user_licenses | 用户授权（1:1，含 access_token） |
| medcomm_user_specialties | 用户学科包 |
| medcomm_device_change_codes | 换机码（验证成功后即删；定时任务每日清理 1 天前记录） |
| medcomm_device_rebind_logs | 换绑日志 |
| medcomm_download_logs | 下载日志 |
| medcomm_security_limits | 速率限制（激活 IP、换机等） |
| medcomm_specialty_version_policy | 学科包版本策略 |
| medcomm_account_migration_requests | 账号迁移申请 |

**迁移**：新部署由 `Base.metadata.create_all` 自动建表。已有库依次执行：

```bash
docker compose exec -T linscio-db psql -U linscio_user -d linscio_portal < api/scripts/migrate_medcomm_v3_schema.sql
docker compose exec -T linscio-db psql -U linscio_user -d linscio_portal < api/scripts/migrate_medcomm_auth_extensions.sql
```

**认证扩展**（`migrate_medcomm_auth_extensions.sql`）：`medcomm_users.username`、`medcomm_pending_registrations`、`medcomm_password_resets`。

### 2. API 路由（/api/v1/medcomm/）

#### 认证与账号

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /medcomm/auth/register | 注册：发送验证码（规范 3.1） |
| POST | /medcomm/auth/verify | 验证账号：校验验证码后完成注册 |
| POST | /medcomm/auth/login | 登录（支持邮箱/手机号/用户名），返回 `session_token` |
| POST | /medcomm/auth/change-password | 修改密码（Bearer session） |
| POST | /medcomm/auth/forgot-password | 忘记密码：发送重置验证码 |
| POST | /medcomm/auth/reset-password | 重置密码：验证码 + 新密码 |

#### 授权

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /medcomm/license/activate | 激活授权码（Bearer session 或软件 access_token） |
| GET | /medcomm/license/status | 授权状态（可选 `reported_specialties` 查询参数） |

激活错误码补充：`trial_no_specialty` — 当前账号为基础版**试用**时，不允许再激活学科包授权码。

#### 换机

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /medcomm/device/change-code/request | 新设备用账号密码申请 6 位换机码（无 Bearer） |
| POST | /medcomm/device/change-code/verify | 旧浏览器登录态校验换机码，返回 `deep_link` |

#### 更新与下载

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /medcomm/update/check | 合并检查软件 + 学科包更新 |
| POST | /medcomm/download/software | 软件安装包预签名 URL |
| POST | /medcomm/download/complete | 下载完成回调 |
| POST | /medcomm/specialty/download | 学科包全量/增量预签名 URL |
| GET | /medcomm/specialty/{specialty_id}/documents | 学科关联文档列表 |

#### 迁移

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /medcomm/account/migration-request | 账号迁移申请（Bearer） |

#### 管理端（需 admin_token）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /admin/medcomm/migration-requests | 迁移申请列表（?status=pending） |
| POST | /admin/medcomm/migration-requests/{id}/approve | 审批通过并迁移 |
| POST | /admin/medcomm/migration-requests/{id}/reject | 审批拒绝 |

### 3. 配置

- **主产品 backend**：`backend/app/core/config.py` 的 `portal_api_url`（环境变量 `LINSCIO_PORTAL_API_URL`）。
- **门户 API**：`app/config.py` 中 `MEDCOMM_SPECIALTY_MANIFEST_KEY`（COS 中学科 manifest 对象键，默认 `specialties/manifest.json`）。未配置 COS 时，依赖 manifest 的接口会降级（如无 `download_url`、空列表等）。

### 4. 门户前端（`portal-system/portal/`）

- 独立本地存储键：`medcomm_session_token`（与 LinScio AI 的 `portal_token` 分离）。
- API 封装：`src/api/medcomm.js`（axios 基址 `/api/v1`，自动带 MedComm Bearer）。
- Pinia：`src/stores/medcommAuth.js`。
- 路由：
  - `/medcomm/login` — 注册/登录（无需 MedComm 登录态）
  - `/medcomm/activate`、`/medcomm/specialties`、`/medcomm/download`、`/medcomm/device`、`/medcomm/migration` — 需 MedComm 登录；站点主导航 **MedComm** 指向 `/medcomm/activate`（未登录会跳转到登录页并带回跳地址）。

本地开发：`vite` 将 `/api` 代理到 `http://localhost:8001`（见 `vite.config.js`）。

## 二、预置测试授权码

```bash
cd portal-system
docker compose exec linscio-api python scripts/seed_medcomm_license.py
```

会生成 LINSCIO-XXXX-XXXX-XXXX 格式的基础版授权码（具体以脚本为准）。

## 三、验证建议

1. 启动 API 与前端，打开 OpenAPI `/docs` 核对 `medcomm` 标签下接口。
2. COS 未配置时：`/medcomm/download/software` 等可能返回 `cos_not_configured`；manifest 缺失时学科版本字段可能为空。

## 四、软件端数据库扩展（backend，设计 2.2）

MedComm 桌面端 / backend 本地 SQLite 扩展：

- **medical_terms**、**writing_examples** 新增 `source` 字段：`user` = 用户自建，`package` = 学科包导入。学科包更新时仅处理 `source='package'` 记录。
- **specialty_packages** 表：学科包状态（not_installed / downloading / installed / update_available / error）、断点续传、崩溃恢复字段。由 `backend/alembic` 迁移创建。

## 五、与现有 portal 的关系

- 现有 `portal_users`、`license_keys` 等为 LinScio AI 通用体系。
- MedComm 使用独立表（`medcomm_*`），两套体系并存。
- 部署时共用同一 PostgreSQL、同一 API 服务。
- 软件端（backend）使用独立 SQLite（`medcomm.db`），含 medical_terms、writing_examples、specialty_packages。
