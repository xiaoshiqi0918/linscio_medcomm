#!/usr/bin/env bash
# 推送前「纯净版」：不修改任何已存在源码文件内容，只更新暂存区并校验后提交、推送。
# 用法:
#   bash scripts/git-push-clean.sh "你的提交说明"
# 行为:
#   - git add -A（遵守 .gitignore，本地 node_modules、.data、wheel 缓存等不会进库）
#   - 若暂存区含禁止路径则失败退出
#   - git status → git commit → git push -u origin <分支>
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

MSG="${1:-}"
if [[ -z "$MSG" ]]; then
  echo "用法: $0 \"提交说明\""
  exit 1
fi

REMOTE="${GIT_REMOTE:-origin}"
BRANCH="${GIT_BRANCH:-$(git rev-parse --abbrev-ref HEAD)}"

forbidden_in_list() {
  local f="$1"
  case "$f" in
    */.auth_secret|*/.env|*/.env.local|*htpasswd|*.pem|*.p12|*.mobileprovision) return 0 ;;
    node_modules/*|.venv/*|venv/*|dist/*|build/python/*) return 0 ;;
  esac
  return 1
}

echo "==> git add -A（源码与工作区文件不改，仅更新暂存区）"
git add -A

echo "==> 校验暂存区路径"
bad=0
while IFS= read -r f; do
  [[ -z "$f" ]] && continue
  if forbidden_in_list "$f"; then
    echo "错误: 禁止纳入版本库的路径出现在暂存区: $f"
    bad=1
  fi
done < <(git diff --cached --name-only)

if [[ "$bad" -ne 0 ]]; then
  echo "请从暂存区移除上述文件（例如 git reset HEAD -- <path>），并确认已加入 .gitignore。"
  exit 1
fi

git status

if git diff --cached --quiet; then
  echo "暂存区为空，跳过 commit，仅尝试 push。"
else
  git commit -m "$MSG"
fi

git push -u "$REMOTE" "$BRANCH"
echo "OK: 已推送到 $REMOTE $BRANCH"
