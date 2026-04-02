-- 为 license_keys 表补全缺失列（兼容旧库仅有 plan_type 等字段的情况）
-- 用法：在 portal-system 目录下执行
--   docker compose exec -T linscio-db psql -U linscio_user -d linscio_portal -f - < scripts/migrate_license_keys_add_columns.sql
-- 或进入容器后：psql -U linscio_user -d linscio_portal -f /path/to/migrate_license_keys_add_columns.sql

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = 'public' AND table_name = 'license_keys' AND column_name = 'plan_id') THEN
    ALTER TABLE license_keys ADD COLUMN plan_id UUID REFERENCES plans(id);
  END IF;
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = 'public' AND table_name = 'license_keys' AND column_name = 'period_id') THEN
    ALTER TABLE license_keys ADD COLUMN period_id UUID REFERENCES billing_periods(id);
  END IF;
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = 'public' AND table_name = 'license_keys' AND column_name = 'module_mask') THEN
    ALTER TABLE license_keys ADD COLUMN module_mask INTEGER;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = 'public' AND table_name = 'license_keys' AND column_name = 'machine_limit') THEN
    ALTER TABLE license_keys ADD COLUMN machine_limit INTEGER NOT NULL DEFAULT 1;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = 'public' AND table_name = 'license_keys' AND column_name = 'concurrent_limit') THEN
    ALTER TABLE license_keys ADD COLUMN concurrent_limit INTEGER NOT NULL DEFAULT 1;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = 'public' AND table_name = 'license_keys' AND column_name = 'pull_limit_monthly') THEN
    ALTER TABLE license_keys ADD COLUMN pull_limit_monthly INTEGER;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = 'public' AND table_name = 'license_keys' AND column_name = 'replace_period_start') THEN
    ALTER TABLE license_keys ADD COLUMN replace_period_start DATE;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = 'public' AND table_name = 'license_keys' AND column_name = 'replace_count_used') THEN
    ALTER TABLE license_keys ADD COLUMN replace_count_used INTEGER NOT NULL DEFAULT 0;
  END IF;
END $$;
