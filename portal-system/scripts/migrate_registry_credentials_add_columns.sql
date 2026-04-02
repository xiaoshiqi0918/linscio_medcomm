-- 为 registry_credentials 表补全缺失列（兼容旧库）
-- 用法：docker compose exec -T linscio-db psql -U linscio_user -d linscio_portal < scripts/migrate_registry_credentials_add_columns.sql

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = 'public' AND table_name = 'registry_credentials' AND column_name = 'license_id') THEN
    ALTER TABLE registry_credentials ADD COLUMN license_id UUID REFERENCES license_keys(id);
  END IF;
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = 'public' AND table_name = 'registry_credentials' AND column_name = 'allowed_image_tags') THEN
    ALTER TABLE registry_credentials ADD COLUMN allowed_image_tags TEXT[];
  END IF;
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = 'public' AND table_name = 'registry_credentials' AND column_name = 'pull_count_this_month') THEN
    ALTER TABLE registry_credentials ADD COLUMN pull_count_this_month INTEGER NOT NULL DEFAULT 0;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = 'public' AND table_name = 'registry_credentials' AND column_name = 'pull_count_reset_at') THEN
    ALTER TABLE registry_credentials ADD COLUMN pull_count_reset_at TIMESTAMP WITH TIME ZONE;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = 'public' AND table_name = 'registry_credentials' AND column_name = 'expires_at') THEN
    ALTER TABLE registry_credentials ADD COLUMN expires_at TIMESTAMP WITH TIME ZONE;
  END IF;
END $$;
