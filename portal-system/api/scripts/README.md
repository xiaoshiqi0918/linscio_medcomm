# 门户 API 脚本与数据库迁移

本目录包含门户系统（portal-system）的数据库迁移脚本与运维脚本。**新部署**由 API 启动时 `Base.metadata.create_all` 自动建表，无需执行迁移；**从旧版本升级**时按需执行下表脚本。

## 迁移执行顺序（已有库升级）

| 顺序 | 脚本 | 说明 | 何时执行 |
|------|------|------|----------|
| 1 | `migrate_container_token_schema.sql` | portal_users 扩展字段 + container_tokens / orders / container_machine_bindings 表 | 门户库在接入 container-token 方案之前已存在、且缺少上述表/字段时 |
| 2 | `migrate_billing_period_name.sql` 或 `add_billing_period_name_column.py` | billing_periods 表增加 `name` 列（套餐与周期显示名） | 从旧版本升级且表中尚无 `name` 列时；新部署建表已含该列 |
| 3 | `migrate_module_definitions_enterprise_beta.sql` | module_definitions 增加旗舰版/内测版开关列 | 从旧版本升级且表中尚无 enterprise_enabled、beta_enabled 时 |

脚本均为**幂等**（已存在则跳过），可重复执行。

## 执行方式

### 方式一：SQL（推荐，Docker 部署）

```bash
# 在 portal-system 目录下
# 1. container-token（若需）
docker compose exec -T linscio-db psql -U linscio_user -d linscio_portal < api/scripts/migrate_container_token_schema.sql

# 2. billing_periods.name（若需）
docker compose exec -T linscio-db psql -U linscio_user -d linscio_portal < api/scripts/migrate_billing_period_name.sql

# 3. module_definitions 旗舰版/内测版（若需）
docker compose exec -T linscio-db psql -U linscio_user -d linscio_portal < api/scripts/migrate_module_definitions_enterprise_beta.sql
```

### 方式二：Python（无 psql 时）

仅 **billing_periods.name** 提供 Python 等效脚本（不修改 container_tokens 等）：

```bash
cd api
python scripts/add_billing_period_name_column.py
# 需已设置 .env 中 DATABASE_URL
```

### 其他脚本

| 脚本 | 说明 |
|------|------|
| `seed_plans_periods_modules.py` | 预置套餐、周期、全部模块（6 个受控 + 9 个非受控）。**受控模块**也可通过 API 启动自动补齐或管理后台「模块权限配置」页「一键初始化受控模块」写入，无需必跑本脚本。 |
| `create_admin.py` | 创建管理员；通常使用项目根目录 `scripts/create-admin.sh` 调用 |
| `generate_license_keypair.py` | 生成 Ed25519 密钥对，用于授权码公钥签名；门户配置私钥、主产品配置公钥 |

## 模块权限配置说明

- **6 个受控模块**（code 与主产品一致）：`schola`、`medcomm`、`qcc`、`literature`、`analyzer`、`image_studio`。
- **API 启动时**会自动执行「确保受控模块存在」：若表中缺少上述 code 则插入，新部署或未跑过 seed 时无需手动添加。
- **管理后台**「模块权限配置」页提供 **「一键初始化受控模块」**，可随时补全 6 个受控模块。
- **可选**执行 `seed_plans_periods_modules.py` 可一次性写入套餐、周期及全部模块（含非受控）；已存在的 code 会跳过。

## 相关文档

- 门户部署与迁移汇总：`portal-system/README.md` §11、§12  
- 统一开发与迁移说明：仓库根目录 `docs/统一开发与腾讯云部署-准备说明.md` §2.2、§2.5  
- 付费授权模式（买断+年维护费）：`docs/付费授权模式-买断与年维护费.md`  
- 授权管理优化（公钥验签、心跳、吊销）：`docs/授权管理优化-可行性方案.md`
