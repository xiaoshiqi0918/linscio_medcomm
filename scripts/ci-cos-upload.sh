#!/usr/bin/env bash
# GitHub Actions：将 electron-builder 产物上传到腾讯云 COS（需配置 Repository secrets）
# 环境变量：COS_SECRET_ID, COS_SECRET_KEY, COS_BUCKET（含 AppID，如 bucket-1250000000）, COS_REGION
# 可选：COS_PREFIX（默认 medcomm/releases）、MATRIX_PLATFORM（darwin-arm64 / darwin-x64 / win32-x64）
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [ -z "${COS_SECRET_ID:-}" ] || [ -z "${COS_SECRET_KEY:-}" ] || [ -z "${COS_BUCKET:-}" ] || [ -z "${COS_REGION:-}" ]; then
  echo "::notice::Skip Tencent COS upload: set secrets TENCENT_COS_SECRET_ID, TENCENT_COS_SECRET_KEY, TENCENT_COS_BUCKET, TENCENT_COS_REGION"
  exit 0
fi

if [ ! -d dist ]; then
  echo "::error::dist/ missing, skip COS upload"
  exit 1
fi

COSCLI_VER="${COSCLI_VER:-v1.0.8}"
BASE_URL="https://github.com/tencentyun/coscli/releases/download/${COSCLI_VER}"

uname_s="$(uname -s || true)"
uname_m="$(uname -m || true)"
COSCLI_BIN=""

case "$uname_s" in
  Darwin)
    if [ "$uname_m" = "arm64" ]; then
      curl -sSL "${BASE_URL}/coscli-${COSCLI_VER}-darwin-arm64" -o coscli
    else
      curl -sSL "${BASE_URL}/coscli-${COSCLI_VER}-darwin-amd64" -o coscli
    fi
    chmod +x coscli
    COSCLI_BIN="./coscli"
    ;;
  Linux)
    curl -sSL "${BASE_URL}/coscli-${COSCLI_VER}-linux-amd64" -o coscli
    chmod +x coscli
    COSCLI_BIN="./coscli"
    ;;
  MINGW*|MSYS*|CYGWIN*)
    curl -sSL "${BASE_URL}/coscli-${COSCLI_VER}-windows-amd64.exe" -o coscli.exe
    COSCLI_BIN="./coscli.exe"
    ;;
  *)
    echo "::error::Unsupported OS for coscli: $uname_s"
    exit 1
    ;;
esac

VER="$(node -p "require('./package.json').version")"
PREFIX="${COS_PREFIX:-medcomm/releases}"
PLAT="${MATRIX_PLATFORM:-unknown}"
# 例：medcomm/releases/0.1.0/darwin-arm64/
DEST_KEY="${PREFIX}/v${VER}/${PLAT}/"

echo "::group::coscli config (~/.cos.yaml)"
umask 077
mkdir -p "${HOME:-$ROOT}"
# 非交互写入凭证；全路径 cos://BucketName-APPID/... 上传，无需在配置里登记桶别名
cat > "${HOME}/.cos.yaml" <<EOF
cos:
  base:
    secretid: "${COS_SECRET_ID}"
    secretkey: "${COS_SECRET_KEY}"
    sessiontoken: ""
    protocol: https
EOF
echo "::endgroup::"

echo "::notice::Uploading to cos://${COS_BUCKET}/${DEST_KEY}"

uploaded=0
while IFS= read -r -d '' f; do
  base="$(basename "$f")"
  "$COSCLI_BIN" cp "$f" "cos://${COS_BUCKET}/${DEST_KEY}${base}"
  echo "uploaded: ${DEST_KEY}${base}"
  uploaded=$((uploaded + 1))
done < <(find dist -maxdepth 1 -type f \( \
  -name '*.dmg' -o -name '*.zip' -o -name '*.exe' -o \
  -name '*.blockmap' -o -name '*.yml' -o -name '*.yaml' \
\) -print0)

if [ "$uploaded" -eq 0 ]; then
  echo "::warning::No installer artifacts matched in dist/ (dmg/zip/exe/blockmap/yml/yaml)"
  ls -la dist || true
  exit 1
fi

echo "::notice::COS upload done, ${uploaded} file(s)"
