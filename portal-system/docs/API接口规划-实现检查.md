# API 接口规划 — 实现检查

对照 6.1～6.4 的接口列表，以《三系统职责边界》路径为准，核对实现与文档的对应关系。

---

## 6.1 门户网站使用的接口

| 文档 | 实际路径 | 说明 |
|------|----------|------|
| **认证** | | |
| POST /api/v1/auth/register | ✅ 同 | 注册 |
| POST /api/v1/auth/login | ✅ 同 | 登录，返回用户 JWT |
| POST /api/v1/auth/logout | ✅ 同 | 登出 |
| **用户中心** | | |
| GET /api/v1/user/profile | ✅ 同 | 用户信息 |
| GET /api/v1/user/license | ✅ 同 | 授权状态（套餐/有效期/模块） |
| POST /api/v1/license/activate | POST /api/v1/user/activate | 激活授权码（以实现为准） |
| GET /api/v1/user/registry-credential | ✅ 同；推荐 GET /api/v1/registry/credential | 获取 Registry 凭证 |
| GET /api/v1/user/machines | ✅ 同 | 绑定机器列表 |
| DELETE /api/v1/user/machines/{id} | DELETE /api/v1/user/machines/{binding_id} | 解绑机器（binding_id） |
| **配额查看** | | |
| GET /api/v1/quota/summary | GET /api/v1/user/quota-summary | 生成次数 + 周期（以实现为准） |
| GET /api/v1/quota/pull-count | GET /api/v1/user/pull-quota | 本月拉取次数 + 剩余 + 重置日 |

---

## 6.2 管理后台使用的接口

| 文档 | 实际路径 | 说明 |
|------|----------|------|
| **管理员认证** | | |
| POST /api/v1/admin/auth/login | ✅ 同 | 管理员登录 |
| **授权码管理** | | |
| GET /api/v1/admin/licenses | ✅ 同 | 列表（含筛选） |
| POST /api/v1/admin/licenses/batch | ✅ 同 | 批量生成 |
| GET /api/v1/admin/licenses/{id} | GET /api/v1/admin/licenses/{license_id} | 详情 |
| PATCH /api/v1/admin/licenses/{id}/extend | ✅ 同（{license_id}） | 延期 |
| PATCH /api/v1/admin/licenses/{id}/revoke | PATCH /api/v1/admin/licenses/{license_id}（无 body 即作废） | 作废 |
| GET /api/v1/admin/licenses/export | ✅ 同 | 导出 CSV |
| **用户管理** | | |
| GET /api/v1/admin/users | ✅ 同 | 用户列表 |
| PATCH /api/v1/admin/users/{id} | PATCH /api/v1/admin/users/{user_id} | 禁用/启用 |
| DELETE /api/v1/admin/machines/{id} | DELETE /api/v1/admin/licenses/{license_id}/machines/{binding_id} | 强制解绑（需 license_id + binding_id） |
| **模块权限配置** | | |
| GET /api/v1/admin/modules | ✅ 同 | 获取模块配置 |
| PUT /api/v1/admin/modules | PATCH /api/v1/admin/modules/{module_id} · POST /api/v1/admin/modules | 按条更新 + 新增 |
| POST /api/v1/admin/modules | ✅ 同 | 新增受控模块 |
| POST /api/v1/admin/credentials/refresh | POST /api/v1/admin/registry-credentials/sync-modules | 批量更新已激活用户凭证 |
| **配额管理** | | |
| GET /api/v1/admin/quota/{license_id} | GET /api/v1/admin/licenses/{license_id}/quota-usage | 配额消耗详情 |
| POST /api/v1/admin/quota/reset | ✅ 同 | 手动重置配额 |
| **数据统计** | | |
| GET /api/v1/admin/stats | ✅ 同 | 总览看板（含 pull_top10、alerts） |
| GET /api/v1/admin/stats/pull-top | — | 已合并进 GET /admin/stats 的 pull_top10_this_month |
| GET /api/v1/admin/stats/alerts | — | 已合并进 GET /admin/stats 的 alerts |

---

## 6.3 Registry Token 服务接口（内部）

| 文档描述 | 实现 |
|----------|------|
| GET /api/v1/registry/token，Basic 认证，?service= & scope= | ✅ 同 |
| ① 验证 username/password（查 registry_credentials） | ✅ |
| ② 验证 license 有效期（is_revoked、expires_at） | ✅ |
| ③ 验证请求的镜像 Tag 是否在 allowed_image_tags 内 | ✅ 按 scope 计算 access |
| ④ 验证本月拉取次数 | ✅ 超限返回 429 |
| ⑤ 签发 JWT（1 小时） | ✅ |
| ⑥ 拉取完成后回调计数 | 在 registry-proxy 拉取 manifest 成功后 _record_pull_success +1，无独立「回调」接口 |

---

## 6.4 应用实例使用的接口（镜像内调用）

| 文档 | 实际路径 / 响应 | 说明 |
|------|-----------------|------|
| POST /api/v1/license/heartbeat | ✅ 同 | |
| Body: license_key, machine_id, instance_id | ✅ 同 | |
| 返回: valid, module_mask, expires_at, concurrent_count | ok, module_mask, expires_at, machine_limit, concurrent_limit, **concurrent_count** | 已含 concurrent_count |
| POST /api/v1/quota/check | ✅ 同 | |
| Body: license_key, machine_id, content_type | ✅ 同（可选 user_id, project_id） | |
| 返回: allowed, used, limit, cycle_reset_date | allowed, content_type, used, limit, cycle_start/end, next_reset_date | 通过即扣减，无独立 consume |
| POST /api/v1/quota/consume | — | 当前无独立 consume；quota/check 通过时已扣减。若需「先 check 再创建再 consume」可后续增加 |

---

**结论**：6.1～6.4 所列能力均已实现或由等价路径覆盖；路径差异已按《三系统职责边界》以实现为准。本次补全：门户 GET /user/pull-quota（本月拉取次数）、心跳返回 concurrent_count。无独立 POST /quota/consume 与独立 /admin/stats/pull-top、/admin/stats/alerts，已在表中说明。

*文档版本：v1 · 2026-02*
