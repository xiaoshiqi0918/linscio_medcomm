#!/usr/bin/env sh
# 为已有数据库补全旧表缺失列（从旧版升级时执行一次）
# 包含：license_keys（plan_id、period_id 等）、registry_credentials（pull_count_this_month 等）
# 用法: 在 portal-system 目录下执行 ./scripts/run-migrate-license-keys.sh

set -e
cd "$(dirname "$0")/.."
SCRIPT_DIR="$(dirname "$0")"

echo "迁移 license_keys ..."
docker compose exec -T linscio-db psql -U linscio_user -d linscio_portal < "$SCRIPT_DIR/migrate_license_keys_add_columns.sql"

echo "迁移 registry_credentials ..."
docker compose exec -T linscio-db psql -U linscio_user -d linscio_portal < "$SCRIPT_DIR/migrate_registry_credentials_add_columns.sql"

echo "迁移完成。请执行: docker compose restart linscio-api"
