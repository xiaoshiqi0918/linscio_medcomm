#!/usr/bin/env bash
# 数据库备份脚本，可由宝塔计划任务或 cron 调用。
# 用法：在 portal-system 目录上一级执行，或设置 BACKUP_ROOT 指向备份目录。
# 示例：cd /www/wwwroot/linscio/portal-system && ./scripts/backup-db.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
BACKUP_ROOT="${BACKUP_ROOT:-/www/wwwroot/linscio/data/backups}"
DB_CONTAINER="${DB_CONTAINER:-linscio-db}"
POSTGRES_USER="${POSTGRES_USER:-linscio_user}"
POSTGRES_DB="${POSTGRES_DB:-linscio_portal}"
RETENTION_DAYS="${RETENTION_DAYS:-7}"

mkdir -p "$BACKUP_ROOT"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
BACKUP_FILE="$BACKUP_ROOT/portal_${TIMESTAMP}.sql"

cd "$ROOT_DIR"
if docker compose exec -T "$DB_CONTAINER" pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB" > "$BACKUP_FILE"; then
  echo "Backup written: $BACKUP_FILE"
else
  echo "Backup failed (check container name: $DB_CONTAINER)" >&2
  exit 1
fi

# 清理超过保留天数的备份
find "$BACKUP_ROOT" -name "portal_*.sql" -mtime +"$RETENTION_DAYS" -delete 2>/dev/null || true
