-- 模块权限配置：增加旗舰版、内测版开关（除基础版/专业版/团队版外）
-- 执行：docker compose exec -T linscio-db psql -U linscio_user -d linscio_portal < api/scripts/migrate_module_definitions_enterprise_beta.sql
-- 或：psql -U linscio_user -d linscio_portal -f api/scripts/migrate_module_definitions_enterprise_beta.sql
-- 新部署由 API 建表时已含两列，无需执行；仅从旧版本升级且表中尚无该列时执行一次。

ALTER TABLE module_definitions ADD COLUMN IF NOT EXISTS enterprise_enabled BOOLEAN NOT NULL DEFAULT true;
ALTER TABLE module_definitions ADD COLUMN IF NOT EXISTS beta_enabled BOOLEAN NOT NULL DEFAULT true;
