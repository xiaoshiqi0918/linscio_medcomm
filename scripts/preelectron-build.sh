#!/usr/bin/env bash
# 在 npm run electron:build 之前执行：升级本机常见路径上的 medcomm.db，并打印发版备忘。
# CI（GitHub Actions）通常直接 npx electron-builder，不会跑本脚本；见 workflows/build.yml 中的 ci-alembic-check。
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Electron 打包前：Alembic 迁移（开发机 backend/.data 等）"
echo "  正式用户库位于各 OS 的 userData/data，由应用启动时 run_migrations 执行。"
echo "  CI 打包请依赖 workflow 里的 scripts/ci-alembic-check.sh（单 head 校验）。"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

if [[ "${MEDCOMM_SKIP_ELECTRON_PREBUILD_MIGRATE:-}" == "1" ]]; then
  echo "已跳过 migrate（MEDCOMM_SKIP_ELECTRON_PREBUILD_MIGRATE=1）；发版请以 CI alembic 校验为准。"
  echo ""
else
bash backend/scripts/migrate_all_medcomm_db.sh || {
  cat <<'MSG'

migrate 失败（常见原因：本机 medcomm.db 与迁移在 SQLite 上不完全兼容；CI 使用 PostgreSQL 校验）。

可选方案：
  1) MEDCOMM_SKIP_ELECTRON_PREBUILD_MIGRATE=1 npm run electron:build   # 跳过本步迁移
  2) 备份后删除 backend/.data/medcomm.db（或新建干净克隆仅用于打包）

MSG
  exit 1
}
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  若新增迁移：确认 alembic/versions 已提交；发版说明可提醒老用户备份后升级。"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
