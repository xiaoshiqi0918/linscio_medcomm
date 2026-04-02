# 核心枢纽：FastAPI 统一服务层 — 职责检查

对照「FastAPI 是三个系统之间所有数据流转的唯一入口」的六项核心职责，逐项核对实现情况。✅ 已完整实现 | ⚠️ 部分实现 | ❌ 未实现。

---

## 一、统一认证

| 凭证类型 | 实现状态 | 说明 |
|----------|----------|------|
| 门户用户 JWT | ✅ | `auth_service.create_access_token`，登录/注册时签发；`auth.py` 使用 `str(user.id)` 为 sub |
| 管理员 JWT | ✅ | `admin.py` 中 `create_admin_token`（ADMIN_JWT_SECRET = JWT_SECRET_KEY + "_admin"），登录时签发 |
| Registry Token | ✅ | `GET /api/v1/registry/token`：Basic 校验后签发 JWT（HS256），含 access 列表，供 Registry v2 Token Auth 使用 |

**结论**：三套凭证均由 FastAPI 签发，已完整实现。

---

## 二、权限计算

| 项 | 实现状态 | 说明 |
|----|----------|------|
| 套餐配置 | ✅ | 从 `plans` 表读 machine_limit、concurrent_limit、pull_limit_monthly；授权码生成与心跳/配额均按 plan_id/plan_code 取限 |
| 模块定义 | ✅ | `license_service.get_module_mask` 根据 `module_definitions`（basic_enabled、pro_enabled、team_enabled）与 plan_code 动态计算 module_mask，写入新授权码 |
| 可拉取镜像 Tag | ✅ | `registry_service.get_allowed_image_tags(plan_code)` 按套餐返回 allowed_image_tags；激活时写入 `registry_credentials`，proxy/Token 校验时使用 |

**结论**：权限均根据数据库中的套餐与模块定义动态计算，已完整实现。

---

## 三、状态同步

| 变更类型 | 实现状态 | 说明 |
|----------|----------|------|
| 作废 | ✅ | `PATCH /admin/licenses/{id}` 将 `license_keys.is_revoked = True`；心跳/激活等均校验 is_revoked |
| 延期 | ✅ | `PATCH /admin/licenses/{id}/extend` 更新 `license_keys.expires_at` 并同步 `registry_credentials.expires_at` |
| 套餐/模块变更 | ✅ | `POST /admin/registry-credentials/sync-modules` 按当前套餐重算 allowed_image_tags 写回所有已激活凭证；管理端修改 module_definitions 后新生成授权码带新 module_mask |

**结论**：状态变更均实时写库，三端（门户、管理后台、Registry 代理/Token）读同一数据源，已完整实现。

---

## 四、htpasswd 维护

| 场景 | 实现状态 | 说明 |
|------|----------|------|
| 用户激活授权码 | ✅ | `user.py` 激活流程中调用 `write_htpasswd(reg_username, reg_password)`，写入 `REGISTRY_AUTH_FILE` |
| 管理员创建/恢复 | ✅ | `create_admin.py` 创建或更新管理员后调用 `write_htpasswd`，脚本 `create-admin.sh`、`sync-admin-to-registry.sh` 可同步管理员账号到 Registry |

**结论**：用户激活与管理员账号均通过 FastAPI/脚本维护 htpasswd，已完整实现。

---

## 五、配额管理

| 类型 | 实现状态 | 说明 |
|------|----------|------|
| 生成次数 | ✅ | **计数**：`quota_service.check_and_use_quota` 扣减 `generation_quotas.used_count` 并写 `generation_records`；**周期**：按激活日起每 90 天周期，`get_cycle_bounds`；**上限**：`get_quota_limit(plan_code, content_type)` 来自套餐配置；`GET /quota/status`、`POST /quota/check`、`GET /user/quota-summary` 统一处理 |
| 拉取次数 | ✅ | **计数**：registry-proxy 在 GET /v2/.../manifests/<tag> 成功（2xx）后按 Basic 用户名查 `registry_credentials`，对 `pull_count_this_month` +1 并写入 `pull_records`。**重置**：同一请求路径内先做「按自然月」检查：若 `pull_count_reset_at` 为空或当前月大于重置月，则置 `pull_count_this_month=0`、`pull_count_reset_at=当月 1 日` 再判断限额。**限额**：从 `license_keys.pull_limit_monthly` 读取上限，若 >0 且 `pull_count_this_month >= limit` 则返回 403。 |

**结论**：生成次数、拉取次数均由 FastAPI 侧（含 registry-proxy）统一计数与周期/自然月重置，已完整实现。

---

## 六、心跳处理

| 项 | 实现状态 | 说明 |
|----|----------|------|
| 接收心跳 | ✅ | `POST /api/v1/license/heartbeat`（license_key、machine_id、instance_id） |
| 授权/过期 | ✅ | 校验 is_used、is_revoked、expires_at；过期时返回 200 且 license_expired=True |
| 机器数/并发 | ✅ | 根据 machine_bindings 与 machine_limit 判断是否允许绑定新机；根据 instance_heartbeats（is_active=True）与 concurrent_limit 判断是否允许新实例 |
| 超时离线 | ✅ | 将 `last_beat < offline_threshold`（15 分钟）的 InstanceHeartbeat 置为 is_active=False，释放并发名额 |
| 机器绑定 | ✅ | 若本机未绑则自动创建或恢复 MachineBinding，更新 last_heartbeat |

**结论**：心跳处理与并发状态维护已完整实现。

---

## 汇总

| 职责 | 状态 | 备注 |
|------|------|------|
| 统一认证 | ✅ | 门户 JWT、管理员 JWT、Registry Token 均由 FastAPI 签发 |
| 权限计算 | ✅ | 套餐 + module_definitions 动态计算；allowed_image_tags 按套餐 |
| 状态同步 | ✅ | 作废、延期、套餐/模块变更写库，三端即时生效 |
| htpasswd 维护 | ✅ | 激活与管理员同步均写入 Registry 认证文件 |
| 配额管理 | ✅ | 生成次数：quota 周期与扣减；拉取次数：registry-proxy 按 manifest 成功 +1、按自然月重置、超限 403 |
| 心跳处理 | ✅ | 心跳接口、机器/并发校验、超时离线、绑定维护均具备 |

**建议**：无；拉取次数已按「拉取时 +1」与「按自然月重置」在 registry-proxy 中实现。

*文档版本：v1 · 2026-02*
