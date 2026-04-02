-- 套餐与周期优化：billing_periods 表增加 name 列（显示名，供管理后台「套餐与周期」配置）
-- 执行：docker compose exec -T linscio-db psql -U linscio_user -d linscio_portal < api/scripts/migrate_billing_period_name.sql
-- 或：psql -U linscio_user -d linscio_portal -f api/scripts/migrate_billing_period_name.sql
-- 新部署由 API 建表时已含 name 列，无需执行；仅从旧版本升级且表中尚无 name 时执行一次。

-- 1. 增加 name 列
ALTER TABLE billing_periods ADD COLUMN IF NOT EXISTS name VARCHAR(60) DEFAULT NULL;

-- 2. 为已有数据回填常用显示名（可选，不覆盖已有 name）
UPDATE billing_periods SET name = '月付' WHERE code = 'monthly' AND (name IS NULL OR name = '');
UPDATE billing_periods SET name = '季付' WHERE code = 'quarterly' AND (name IS NULL OR name = '');
UPDATE billing_periods SET name = '年付' WHERE code = 'yearly' AND (name IS NULL OR name = '');
UPDATE billing_periods SET name = '内测' WHERE code = 'internal' AND (name IS NULL OR name = '');
