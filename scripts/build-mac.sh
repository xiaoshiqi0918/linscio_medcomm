#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════
#  LinScio MedComm — macOS 本地打包脚本
#
#  用法:
#    bash scripts/build-mac.sh client          # 打包客户端
#
#  架构: 默认 arm64（Apple Silicon），可传第二参数 x64
#    bash scripts/build-mac.sh client arm64    # Apple Silicon
#    bash scripts/build-mac.sh client x64      # Intel Mac
#
#  环境变量:
#    SKIP_ENV_CHECK=1         跳过环境检测
#    MEDCOMM_PY_SKIP_MIRROR=1 跳过国内镜像
#
#  产物命名:
#    客户端:  LinScio-MedComm-{ver}-mac-{arm64|x64}.{dmg,zip}
# ═══════════════════════════════════════════════════════════
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

VER="$(node -p "require('./package.json').version")"
OUT_DIR="releases/v${VER}"
TARGET="${1:-all}"
ARCH="${2:-arm64}"

# ── 国内镜像配置 ──
GHPROXY="https://mirror.ghproxy.com"
GHFAST="https://ghfast.top"
PY_MIRROR="https://pypi.tuna.tsinghua.edu.cn/simple"
HF_MIRROR="https://hf-mirror.com"

# ── 颜色 ──
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

info()  { echo -e "${GREEN}[INFO]${NC} $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*"; }

# ═══════════════════════════════════════════════════════════
#  环境检测
# ═══════════════════════════════════════════════════════════
check_env() {
  if [ "${SKIP_ENV_CHECK:-}" = "1" ]; then
    info "跳过环境检测 (SKIP_ENV_CHECK=1)"
    return
  fi

  echo ""
  echo "── 环境检测 ──"
  local FAIL=0

  # Node.js
  if command -v node &>/dev/null; then
    local NODE_VER; NODE_VER="$(node -v)"
    local NODE_MAJOR; NODE_MAJOR="$(echo "$NODE_VER" | sed 's/v//' | cut -d. -f1)"
    if [ "$NODE_MAJOR" -lt 18 ]; then
      error "Node.js 版本过低: $NODE_VER（需要 ≥18）"
      echo "  安装: brew install node@20"
      FAIL=1
    else
      info "Node.js $NODE_VER ✓"
    fi
  else
    error "未找到 Node.js"
    echo "  安装: brew install node@20"
    FAIL=1
  fi

  # Python
  if command -v python3 &>/dev/null; then
    local PY_VER; PY_VER="$(python3 --version 2>&1)"
    info "$PY_VER ✓"
  else
    error "未找到 Python3"
    echo "  安装: brew install python@3.11"
    FAIL=1
  fi

  # Git
  if command -v git &>/dev/null; then
    info "Git $(git --version | awk '{print $3}') ✓"
  else
    error "未找到 Git"
    echo "  安装: xcode-select --install"
    FAIL=1
  fi

  # Xcode Command Line Tools
  if xcode-select -p &>/dev/null; then
    info "Xcode CLI Tools ✓"
  else
    warn "未找到 Xcode Command Line Tools"
    echo "  安装: xcode-select --install"
  fi

  # 磁盘空间
  local FREE_GB; FREE_GB="$(df -g "$ROOT" | awk 'NR==2{print $4}')"
  local NEED_GB=10
  if [ "$FREE_GB" -lt "$NEED_GB" ]; then
    error "磁盘空间不足: 可用 ${FREE_GB}GB，需要 ${NEED_GB}GB"
    FAIL=1
  else
    info "磁盘空间 ${FREE_GB}GB ✓"
  fi

  # npm 依赖
  if [ ! -d "node_modules" ]; then
    warn "node_modules 不存在，将自动安装"
  fi

  if [ "$FAIL" -ne 0 ]; then
    error "环境检测未通过，请先安装缺失的工具"
    exit 1
  fi
  echo ""
}

# ═══════════════════════════════════════════════════════════
#  架构检测
# ═══════════════════════════════════════════════════════════
check_arch() {
  if [ "$ARCH" = "x64" ]; then
    info "构建目标: Mac Intel (x64)"
    if [ "$(uname -m)" = "arm64" ]; then
      warn "当前机器为 ARM64，将交叉编译 x64 版本"
    fi
  else
    info "构建目标: Mac Apple Silicon (arm64)"
    if [ "$(uname -m)" = "x86_64" ]; then
      warn "当前机器为 Intel，将交叉编译 arm64 版本"
    fi
  fi
}

# ═══════════════════════════════════════════════════════════
#  国内镜像下载 wrapper
# ═══════════════════════════════════════════════════════════
download_with_mirrors() {
  local OFFICIAL_URL="$1"
  local DEST="$2"

  if [ "${MEDCOMM_PY_SKIP_MIRROR:-}" = "1" ]; then
    info "直接下载: $OFFICIAL_URL"
    curl -fSL --connect-timeout 30 --retry 3 -o "$DEST" "$OFFICIAL_URL"
    return
  fi

  local REL="${OFFICIAL_URL#https://}"
  local URLS=(
    "${GHPROXY}/https://${REL}"
    "${GHFAST}/https://${REL}"
    "$OFFICIAL_URL"
  )

  for url in "${URLS[@]}"; do
    info "尝试下载: $url"
    if curl -fSL --connect-timeout 30 --retry 2 -o "${DEST}.part" "$url" 2>/dev/null; then
      local SZ; SZ="$(stat -f%z "${DEST}.part" 2>/dev/null || stat -c%s "${DEST}.part" 2>/dev/null || echo 0)"
      if [ "$SZ" -gt 5000000 ]; then
        mv "${DEST}.part" "$DEST"
        info "下载成功 ($(( SZ / 1024 / 1024 )) MB)"
        return
      fi
      warn "文件过小 (${SZ} bytes)，尝试下一个源"
      rm -f "${DEST}.part"
    else
      warn "下载失败，尝试下一个源"
      rm -f "${DEST}.part"
    fi
  done

  error "所有下载源均失败: $OFFICIAL_URL"
  exit 1
}

# ═══════════════════════════════════════════════════════════
#  构建客户端
# ═══════════════════════════════════════════════════════════
build_client() {
  echo ""
  echo "══════════════════════════════════════════════"
  echo "  构建客户端 mac-${ARCH}  v${VER}"
  echo "══════════════════════════════════════════════"

  local PY_URL WHEELS_DIR
  case "$ARCH" in
    arm64)
      PY_URL="https://github.com/astral-sh/python-build-standalone/releases/download/20241205/cpython-3.11.11+20241205-aarch64-apple-darwin-install_only.tar.gz"
      WHEELS_DIR="build/wheels/darwin-arm64"
      ;;
    x64)
      PY_URL="https://github.com/astral-sh/python-build-standalone/releases/download/20241205/cpython-3.11.11+20241205-x86_64-apple-darwin-install_only.tar.gz"
      WHEELS_DIR="build/wheels/darwin-x64"
      ;;
    *) error "Unknown arch: $ARCH"; exit 1 ;;
  esac

  # 1. npm install
  if [ ! -d "node_modules" ]; then
    info "[1/5] npm install..."
    npm install
  else
    info "[1/5] node_modules 已存在，跳过"
  fi

  # 2. 下载嵌入式 Python
  info "[2/5] 下载 Python 3.11 for ${ARCH}..."
  rm -rf build/python build/python-extract
  local TARBALL="build/python-standalone-${ARCH}.tar.gz"
  if [ ! -f "$TARBALL" ]; then
    download_with_mirrors "$PY_URL" "$TARBALL"
  else
    info "使用缓存: $TARBALL"
  fi
  mkdir -p build/python-extract
  tar -xzf "$TARBALL" -C build/python-extract
  mv build/python-extract/python build/python
  rm -rf build/python-extract

  local PY="build/python/bin/python3"
  info "Python: $($PY --version) ($(file -b "$PY" | grep -o 'arm64\|x86_64'))"

  # 3. 安装后端依赖到嵌入式 Python
  info "[3/5] 安装后端 Python 依赖..."
  if [ ! -d "$WHEELS_DIR" ]; then
    warn "Wheels 不存在，执行 npm run prebuild:wheels"
    npm run prebuild:wheels
  fi
  $PY -m pip install --no-index --find-links="$WHEELS_DIR" \
    --no-warn-script-location \
    -r backend/requirements.txt --quiet 2>&1 | tail -5 || {
    warn "本地 wheels 不完整，使用清华镜像安装..."
    $PY -m pip install -i "$PY_MIRROR" --find-links="$WHEELS_DIR" \
      --no-warn-script-location \
      -r backend/requirements.txt --quiet
  }
  info "已安装 $($PY -m pip list --format=columns 2>/dev/null | wc -l | tr -d ' ') 个包"

  # 4. 构建前端
  info "[4/5] 构建前端 (vite)..."
  npx vite build 2>&1 | tail -3

  # 5. Electron 打包
  info "[5/5] electron-builder --mac --${ARCH}..."
  npx electron-builder --mac "--${ARCH}" 2>&1 | grep -E '(packaging|building|target|skipped|error|⨯)' || true

  echo ""
  info "客户端构建完成:"
  ls -lh "${OUT_DIR}/"*"${ARCH}"*.dmg 2>/dev/null || warn "(未生成 DMG)"
  echo ""
}

# ═══════════════════════════════════════════════════════════
#  主入口
# ═══════════════════════════════════════════════════════════
echo ""
echo "══════════════════════════════════════════════"
echo "  LinScio MedComm v${VER} — macOS Build"
echo "  目标: ${TARGET}  架构: ${ARCH}"
echo "══════════════════════════════════════════════"

check_env
check_arch

case "$TARGET" in
  client|all)
    build_client
    ;;
  *)
    echo "用法: $0 {client|all} [arm64|x64]"
    exit 1
    ;;
esac
