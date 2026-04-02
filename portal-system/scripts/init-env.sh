#!/usr/bin/env bash
# 在服务器上首次生成 .env，避免「variable is not set」导致数据库无法启动。
# 在 portal-system 目录执行：chmod +x scripts/init-env.sh && ./scripts/init-env.sh

set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT_DIR"

if [ ! -f .env.production.example ]; then
  echo "错误：未找到 .env.production.example，请在 portal-system 目录下执行本脚本。"
  exit 1
fi

if [ -f .env ]; then
  echo "已存在 .env。若仍报 variable is not set，请检查 POSTGRES_PASSWORD 等是否有值，或删除 .env 后重试。"
  exit 0
fi

# 生成随机必填项
gen_hex32() { openssl rand -hex 32 2>/dev/null || head -c 32 /dev/urandom | xxd -p -c 64 | head -c 64; }
gen_b64_32() { openssl rand -base64 24 2>/dev/null | tr -d '\n+' | head -c 32; }
gen_b64_16() { openssl rand -base64 16 2>/dev/null | tr -d '\n+' | head -c 16; }

POSTGRES_PASSWORD=$(gen_hex32)
JWT_SECRET_KEY=$(gen_hex32)
AES_SECRET_KEY=$(gen_b64_32)
AES_IV=$(gen_b64_16)

cp .env.production.example .env
# 替换占位符为实际值（兼容 GNU sed 与 BSD sed）
if sed --version 2>/dev/null | grep -q GNU; then
  sed -i "s/^POSTGRES_PASSWORD=.*/POSTGRES_PASSWORD=$POSTGRES_PASSWORD/" .env
  sed -i "s/^JWT_SECRET_KEY=.*/JWT_SECRET_KEY=$JWT_SECRET_KEY/" .env
  sed -i "s/^AES_SECRET_KEY=.*/AES_SECRET_KEY=$AES_SECRET_KEY/" .env
  sed -i "s/^AES_IV=.*/AES_IV=$AES_IV/" .env
else
  sed -i '' "s|^POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD=$POSTGRES_PASSWORD|" .env
  sed -i '' "s|^JWT_SECRET_KEY=.*|JWT_SECRET_KEY=$JWT_SECRET_KEY|" .env
  sed -i '' "s|^AES_SECRET_KEY=.*|AES_SECRET_KEY=$AES_SECRET_KEY|" .env
  sed -i '' "s|^AES_IV=.*|AES_IV=$AES_IV|" .env
fi

chmod 600 .env
echo "已生成 .env（随机密码已填入 POSTGRES_PASSWORD、JWT_SECRET_KEY、AES_SECRET_KEY、AES_IV）。"
echo "请执行：docker compose up -d linscio-db && docker compose up -d"
