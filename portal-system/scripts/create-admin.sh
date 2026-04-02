#!/usr/bin/env sh
# 创建或恢复管理员（用户名、密码同步到数据库与镜像仓库认证）
# 用法: ./scripts/create-admin.sh [用户名 [密码]]
#        ./scripts/create-admin.sh 用户名 密码 update   # 管理员已存在时同时更新数据库中的密码
# 默认: admin / admin123。需先启动: docker compose up -d linscio-db linscio-api

set -e
cd "$(dirname "$0")/.."
USER="${1:-admin}"
PASS="${2:-admin123}"
if [ "$3" = "update" ]; then
  export ADMIN_UPDATE_PASSWORD=1
fi
docker compose exec -e ADMIN_USERNAME="$USER" -e ADMIN_PASSWORD="$PASS" linscio-api python scripts/create_admin.py
