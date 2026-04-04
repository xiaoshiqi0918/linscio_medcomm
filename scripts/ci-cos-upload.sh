#!/usr/bin/env bash
# GitHub Actions：将 electron-builder 产物上传到腾讯云 COS
# 环境变量：COS_SECRET_ID, COS_SECRET_KEY, COS_BUCKET, COS_REGION
# 可选：COS_PREFIX（默认 releases/MedComm）
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [ -z "${COS_SECRET_ID:-}" ] || [ -z "${COS_SECRET_KEY:-}" ] || [ -z "${COS_BUCKET:-}" ] || [ -z "${COS_REGION:-}" ]; then
  echo "::notice::Skip Tencent COS upload: set secrets TENCENT_COS_SECRET_ID, TENCENT_COS_SECRET_KEY, TENCENT_COS_BUCKET, TENCENT_COS_REGION"
  exit 0
fi

VER="$(node -p "require('./package.json').version")"
RELEASE_DIR="releases/v${VER}"

if [ ! -d "$RELEASE_DIR" ]; then
  echo "::error::${RELEASE_DIR} missing, skip COS upload"
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

PREFIX="${COS_PREFIX:-releases/MedComm}"
DEST_KEY="${PREFIX}/v${VER}/"

echo "::group::coscli config (~/.cos.yaml)"
umask 077
mkdir -p "${HOME:-$ROOT}"
COS_ENDPOINT="cos.${COS_REGION}.myqcloud.com"
cat > "${HOME}/.cos.yaml" <<EOF
cos:
  base:
    secretid: "${COS_SECRET_ID}"
    secretkey: "${COS_SECRET_KEY}"
    sessiontoken: ""
    protocol: https
  buckets:
    - name: "${COS_BUCKET}"
      alias: default
      region: "${COS_REGION}"
      endpoint: "${COS_ENDPOINT}"
EOF
echo "::endgroup::"

echo "::notice::Uploading to cos://${COS_BUCKET}/${DEST_KEY}"

uploaded=0
while IFS= read -r -d '' f; do
  base="$(basename "$f")"
  "$COSCLI_BIN" cp "$f" "cos://${COS_BUCKET}/${DEST_KEY}${base}"
  echo "uploaded: ${DEST_KEY}${base}"
  uploaded=$((uploaded + 1))
done < <(find "$RELEASE_DIR" -maxdepth 1 -type f \( \
  -name '*.dmg' -o -name '*.zip' -o -name '*.exe' -o \
  -name '*.blockmap' -o -name '*.yml' -o -name '*.yaml' \
\) -print0)

if [ "$uploaded" -eq 0 ]; then
  echo "::warning::No installer artifacts matched in ${RELEASE_DIR}/ (dmg/zip/exe/blockmap/yml/yaml)"
  ls -la "$RELEASE_DIR" || true
  exit 1
fi

echo "::notice::COS upload done, ${uploaded} file(s) → ${DEST_KEY}"
