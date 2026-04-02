# 门户内容总览 · 需求与实现清单

本文档对应**云端管控接口规范 9.1～9.4**：心跳、版本检测、Tauri Updater、数据表。已实现项标注 ✅。

---

## 一、必须实现的 HTTP 接口

### 9.1 心跳接口

- **POST** `https://api.linscio.com.cn/api/v1/client/heartbeat`，**Bearer** 鉴权。
- **请求**：app_version、os_type、os_version、machine_id、uptime_seconds、deployment（"desktop"）。
- **响应**：心跳间隔（next_interval_seconds）、force_update、force_rollback、公告（announcement）等。  
- **状态**：✅ 已实现。

### 9.2 版本检测接口

- **GET** `https://api.linscio.com.cn/api/v1/client/latest-version`，**Bearer** 鉴权。
- **Query**：可选 `current_version`，用于计算 has_update。
- **响应**：latest_version、has_update、force_update、release_notes、download_urls（各平台）、min_supported_version。  
- **状态**：✅ 已实现。

### 9.3 Tauri Updater 端点

- **GET** `https://api.linscio.com.cn/api/v1/client/tauri-update`，**公开**（无需 Bearer）。
- **Query**：current_version、platform（如 darwin-aarch64、windows-x86_64）。
- **行为**：当前已是最新时响应 **HTTP 204 No Content**；有更新时返回 Tauri 标准 JSON（version、notes、pub_date、url、signature）。  
- **状态**：✅ 已实现。

### 已有接口（兼容）

| 接口 | 说明 | 状态 |
|------|------|------|
| **POST /api/v1/auth/container-token** | 请求体：username、password、machine_id。成功返回：token、expires_at、issued_at、plan、modules、username。错误码：invalid_credentials、not_purchased、account_suspended、machine_limit_exceeded、rate_limited。 | ✅ 已实现 |
| **POST /api/v1/auth/login** | 门户登录。 | ✅ 已实现 |

---

## 二、下载页两个入口（门户前端/运营）

- **入口一：桌面安装包** — 「桌面安装包」或「Windows / macOS / Linux 客户端」，链接可与 latest-version 的 download_urls 一致。
- **入口二：服务端部署包** — 「服务端部署包」或「Docker 版」：镜像拉取说明、docker-compose 或 linscio-ai-server-{version}.zip。

---

## 三、安装包存储与版本配置

- 桌面安装包上传至 COS/OSS，生成公网 URL 或预签名 URL。
- latest-version 的 download_urls 与 tauri-update 的 url 指向上述地址。
- app_versions 表维护：version、release_notes、各平台 URL、tauri_platforms（含 signature）、force_update、min_supported_version、rollback_version、announcement。

---

## 四、管理后台扩展（建议）

- 版本管理：发布版本、各平台 URL/签名、强制更新、回滚。
- 客户端概览：桌面活跃数、平台/版本分布（数据来源 client_heartbeats）。
- 用户设备列表：OS、客户端版本、最后心跳时间、machine_id。

---

## 五、数据表（门户库）—— 9.4

| 表名 | 用途与关键字段 | 状态 |
|------|----------------|------|
| **client_heartbeats** | 记录每次心跳。user_id、machine_id、app_version、os_type、os_version、uptime_seconds、deployment、created_at。 | ✅ 已实现 |
| **app_versions** | 版本信息。version（UNIQUE）、release_notes、各平台 download_url_*、tauri_platforms（url+signature）、force_update、min_supported_version、rollback_version、announcement、pub_date、is_current。 | ✅ 已实现 |

---

## 六、客户端与门户约定

- **心跳**：POST 携带 app_version、os_type、os_version、machine_id、uptime_seconds、deployment；客户端按响应 next_interval_seconds 调整间隔，并缓存 force_update、force_rollback、announcement。
- **版本检测**：GET latest-version 可带 current_version，返回 has_update、latest_version、download_urls、min_supported_version。
- **Tauri 更新**：GET tauri-update?current_version=x&platform=darwin-aarch64，无更新 204，有更新 200 + 标准 JSON（url、signature 等）。
