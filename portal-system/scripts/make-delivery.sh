#!/usr/bin/env sh
# 制作 portal-system 纯净交付包：去除 node_modules、Python 虚拟环境、构建产物、密钥等。
# 用法：在 portal-system 目录下执行 ./scripts/make-delivery.sh
# 用法：在 portal-system 目录下执行 ./scripts/make-delivery.sh
# 输出：../portal-system-delivery-YYYYMMDD.tar.gz 与 .zip
#       .zip 可在宝塔/腾讯云文件管理中右键解压；.tar.gz 需在 SSH 下用 tar -xzf 解压

set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
DATE="$(date +%Y%m%d)"
OUT_DIR="$(dirname "$ROOT")"
TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

DST="${TMP_DIR}/portal-system"
mkdir -p "$DST"

# 使用 rsync 排除不需要的文件（兼容 macOS / Linux）
rsync -a --delete-excluded \
  --exclude='.git' \
  --exclude='.git/*' \
  --exclude='.env' \
  --exclude='*.local' \
  --exclude='node_modules' \
  --exclude='portal/node_modules' \
  --exclude='admin/node_modules' \
  --exclude='__pycache__' \
  --exclude='api/__pycache__' \
  --exclude='api/.venv' \
  --exclude='api/venv' \
  --exclude='*.pyc' \
  --exclude='.pytest_cache' \
  --exclude='.mypy_cache' \
  --exclude='portal/dist' \
  --exclude='admin/dist' \
  --exclude='registry/auth/htpasswd' \
  --exclude='data/postgres' \
  --exclude='data/registry' \
  --exclude='data/backups/*' \
  --exclude='.idea' \
  --exclude='.vscode' \
  --exclude='.cursor' \
  --exclude='*.log' \
  --exclude='logs' \
  --exclude='*.swp' \
  --exclude='*.swo' \
  "$ROOT/" "$DST/"

# 同时生成 .tar.gz 与 .zip（.zip 便于宝塔/腾讯云文件管理里右键解压）
(cd "$TMP_DIR" && tar -czf "${OUT_DIR}/portal-system-delivery-${DATE}.tar.gz" portal-system)
(cd "$TMP_DIR" && zip -r -q "${OUT_DIR}/portal-system-delivery-${DATE}.zip" portal-system)

echo "已生成交付包:"
echo "  - ${OUT_DIR}/portal-system-delivery-${DATE}.tar.gz"
echo "  - ${OUT_DIR}/portal-system-delivery-${DATE}.zip"
echo "说明："
echo "  - 已排除 node_modules、Python 虚拟环境、dist、.env、htpasswd、.git 等"
echo "  - 部署时请参考 docs/交付版-腾讯云服务器部署指南.md"
echo "  - 解压后得到目录 portal-system/；若在宝塔/腾讯云文件管理中解压，请使用 .zip 包（可右键解压）"
echo "  - .tar.gz 在网页文件管理中无法直接打开，需用 SSH 执行: tar -xzf portal-system-delivery-*.tar.gz"
