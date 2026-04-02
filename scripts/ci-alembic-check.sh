#!/usr/bin/env bash
# CI / 发版前：确认 Alembic 仅有一个 head（避免漏合并迁移），不依赖本机 medcomm.db。
# 与本地 scripts/preelectron-build.sh（迁开发库）互补；GitHub Actions 见 .github/workflows/build.yml
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON="${PYTHON:-python}"

# 跨平台临时目录（Windows Git Bash 中 TMPDIR / /tmp 可能不存在）
_TMPBASE="${TMPDIR:-${TEMP:-${TMP:-/tmp}}}"
export LINSCIO_APP_DATA="${LINSCIO_APP_DATA:-${_TMPBASE}/linscio-alembic-ci-$$}"
mkdir -p "$LINSCIO_APP_DATA"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Alembic 迁移检查（CI）"
echo "  用户正式库在启动时由 Electron run_migrations + LINSCIO_APP_DATA 升级"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

cd "$ROOT/backend"
OUT="$("$PYTHON" -m alembic heads 2>&1)"
echo "$OUT"

HEAD_LINES="$(echo "$OUT" | grep -E '\(head\)' || true)"
HEAD_COUNT="$(echo "$HEAD_LINES" | grep -c . || true)"
if [[ -z "$HEAD_LINES" ]] || [[ "$HEAD_COUNT" != "1" ]]; then
  echo ""
  echo "ERROR: 需要恰好一个 Alembic head；当前为 ${HEAD_COUNT:-0} 行含 (head)。"
  exit 1
fi

echo ""
echo "OK: 单一 migration head。"
echo ""

# 清理临时目录
rm -rf "$LINSCIO_APP_DATA" 2>/dev/null || true
