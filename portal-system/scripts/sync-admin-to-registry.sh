#!/usr/bin/env sh
# 将已有管理员账号同步到 Registry htpasswd，便于用同一账号登录 Registry UI / docker login
# 用法: ./scripts/sync-admin-to-registry.sh 用户名 密码
# 示例: ./scripts/sync-admin-to-registry.sh xiaoshiqi 'Yeahchy@07102'

set -e
cd "$(dirname "$0")/.."
USER="$1"
PASS="$2"
if [ -z "$USER" ] || [ -z "$PASS" ]; then
  echo "用法: $0 用户名 密码"
  exit 1
fi
docker compose exec -e SYNC_REGISTRY_USER="$USER" -e SYNC_REGISTRY_PASS="$PASS" linscio-api python -c "import os,sys; from app.services.registry_service import write_htpasswd; u,p=os.environ['SYNC_REGISTRY_USER'],os.environ['SYNC_REGISTRY_PASS']; sys.exit(0 if write_htpasswd(u,p) else 1)" && echo "已同步到 htpasswd" || { echo "同步失败，请确认 API 容器对 registry/auth 有写权限（docker-compose 中勿将 registry/auth 设为 :ro）"; exit 1; }
echo "正在重启 Registry 以加载新认证..."
docker compose restart linscio-registry
echo "完成。请使用上述用户名和密码登录 Registry Web UI（生产：https://hub.linscio.com.cn，本地：http://localhost:5001）或 docker login（生产：registry.linscio.com.cn，本地：localhost:5000）"