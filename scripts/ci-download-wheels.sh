#!/usr/bin/env bash
# GitHub Actions：为目标平台预下载 wheels 到 build/wheels/<matrix.platform>/
# 用法: ci-download-wheels.sh <pip_platform> <dest_subdir>
# 例:   ci-download-wheels.sh macosx_11_0_arm64 darwin-arm64
#
# jieba、bibtexparser 在 PyPI 上常为 sdist 或无匹配 wheel，不能与 --platform + --only-binary=:all: 同批解析；
# 故先下载其余依赖的二进制 wheel，再单独拉取上述包（及 bibtexparser 的依赖如 pyparsing）。
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
REQ="$ROOT/backend/requirements.txt"
PIP_PLATFORM="${1:?pip platform tag}"
DEST_NAME="${2:?dest subdir e.g. darwin-arm64}"
WHEEL_DIR="$ROOT/build/wheels/$DEST_NAME"

PY="${PYTHON:-python}"
command -v "$PY" >/dev/null 2>&1 || PY=python3
if ! command -v "$PY" >/dev/null 2>&1; then
  echo "ERROR: python not found (tried PYTHON, python, python3)"
  exit 1
fi

if [[ ! -f "$REQ" ]]; then
  echo "ERROR: $REQ not found"
  exit 1
fi

mkdir -p "$WHEEL_DIR"
TMP_REQ="$(mktemp)"
grep -vE '^\s*jieba' "$REQ" | grep -vE '^\s*bibtexparser' > "$TMP_REQ"

"$PY" -m pip download -r "$TMP_REQ" \
  --platform "$PIP_PLATFORM" --python-version 3.11 \
  --only-binary=:all: -d "$WHEEL_DIR/"
rm -f "$TMP_REQ"

# 无平台约束：拉取 sdist / 通用 wheel，供嵌入 Python 离线安装
SDIST_ARGS=()
while IFS= read -r line; do
  [[ -z "${line// }" ]] && continue
  [[ "$line" =~ ^# ]] && continue
  SDIST_ARGS+=("$line")
done < <(grep -E '^\s*(jieba|bibtexparser)' "$REQ" || true)

if [[ ${#SDIST_ARGS[@]} -gt 0 ]]; then
  "$PY" -m pip download "${SDIST_ARGS[@]}" -d "$WHEEL_DIR/"
fi

echo "OK: wheels -> $WHEEL_DIR"
