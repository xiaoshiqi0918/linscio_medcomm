#!/usr/bin/env bash
# portal-system 纯净版 zip：排除所有环境与构建产物，输出到指定目录
# 用法: ./scripts/build-delivery-zip-clean.sh [输出目录]
# 默认输出到 /Users/xiaoshiqi/

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
OUT_DIR="${1:-/Users/xiaoshiqi}"
DATE="$(date +%Y%m%d)"
ZIP_NAME="portal-system_纯净版_${DATE}.zip"
TMP_DIR="$(mktemp -d -t portal_clean.XXXXXX)"
trap 'rm -rf "$TMP_DIR"' EXIT

cd "$REPO_ROOT"

echo "=========================================="
echo "portal-system 纯净版打包（排除所有环境）"
echo "=========================================="
echo "  项目根: ${REPO_ROOT}"
echo "  输出:   ${OUT_DIR}/${ZIP_NAME}"
echo "=========================================="

rsync -a --delete-excluded \
  --exclude='.git' \
  --exclude='.gitignore' \
  --exclude='.gitattributes' \
  --exclude='*.zip' \
  --exclude='node_modules' \
  --exclude='api/node_modules' \
  --exclude='portal/node_modules' \
  --exclude='admin/node_modules' \
  --exclude='__pycache__' \
  --exclude='api/__pycache__' \
  --exclude='*.py[cod]' \
  --exclude='*$py.class' \
  --exclude='.venv' \
  --exclude='api/.venv' \
  --exclude='api/venv' \
  --exclude='venv' \
  --exclude='.env' \
  --exclude='.env.*' \
  --exclude='*.local' \
  --exclude='docker-compose.override.yml' \
  --exclude='portal/dist' \
  --exclude='admin/dist' \
  --exclude='.vscode' \
  --exclude='.idea' \
  --exclude='.pytest_cache' \
  --exclude='.mypy_cache' \
  --exclude='*.log' \
  --exclude='logs' \
  --exclude='data/postgres' \
  --exclude='data/registry' \
  --exclude='data/backups' \
  --exclude='registry/auth/htpasswd' \
  --exclude='.DS_Store' \
  --exclude='Thumbs.db' \
  --exclude='*.swp' \
  --exclude='*.swo' \
  . "$TMP_DIR/"

mkdir -p "$OUT_DIR"
(cd "$TMP_DIR" && zip -rq "${OUT_DIR}/${ZIP_NAME}" .)

echo ""
echo "已生成: ${OUT_DIR}/${ZIP_NAME}"
echo "解压后: cd portal-system && docker compose up -d（需先配置 .env）"
echo "=========================================="
