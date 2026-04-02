#!/usr/bin/env bash
# 对当前机器上常见的 medcomm.db 位置依次执行 alembic upgrade head。
# 用法：在 backend 目录下 ./scripts/migrate_all_medcomm_db.sh
# 可传入额外目录：./scripts/migrate_all_medcomm_db.sh /path/to/custom/.data
set -euo pipefail
BACKEND_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$BACKEND_ROOT"

run_one() {
  local data_root="$1"
  local db="$data_root/medcomm.db"
  if [[ ! -f "$db" ]]; then
    return 0
  fi
  echo "==> LINSCIO_APP_DATA=$data_root  ($db)"
  LINSCIO_APP_DATA="$data_root" alembic upgrade head
  echo "    current: $(LINSCIO_APP_DATA="$data_root" alembic current 2>/dev/null | tail -1)"
}

# 默认：本仓库开发用 .data；若 db 误放在 backend 根目录也处理一次
run_one "$BACKEND_ROOT/.data"
run_one "$BACKEND_ROOT"

for extra in "$@"; do
  [[ -n "$extra" ]] || continue
  run_one "$(cd "$extra" && pwd)"
done

echo "Done."
