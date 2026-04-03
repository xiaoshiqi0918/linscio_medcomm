#!/usr/bin/env bash
# Usage:
#   bash scripts/build-mac.sh arm64      # Apple Silicon
#   bash scripts/build-mac.sh x64        # Intel
#   bash scripts/build-mac.sh all        # Both
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

build_one() {
  local ARCH="$1"
  echo ""
  echo "══════════════════════════════════════════════"
  echo "  Building mac-${ARCH}"
  echo "══════════════════════════════════════════════"

  # ① Determine Python standalone URL and wheels platform
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
    *) echo "Unknown arch: $ARCH"; exit 1 ;;
  esac

  # ② Download Python standalone for target arch
  echo "[1/5] Downloading Python 3.11 for ${ARCH}..."
  rm -rf build/python build/python-extract
  local TARBALL="build/python-standalone-${ARCH}.tar.gz"
  if [ ! -f "$TARBALL" ]; then
    curl -L -o "$TARBALL" "$PY_URL"
  fi
  mkdir -p build/python-extract
  tar -xzf "$TARBALL" -C build/python-extract
  mv build/python-extract/python build/python
  rm -rf build/python-extract

  local PY="build/python/bin/python3"
  echo "  Python: $($PY --version) ($(file -b $PY | grep -o 'arm64\|x86_64'))"

  # ③ Install wheels into embedded Python
  echo "[2/5] Installing wheels into embedded Python..."
  if [ ! -d "$WHEELS_DIR" ]; then
    echo "  Wheels not found at $WHEELS_DIR. Run: npm run prebuild:wheels"
    exit 1
  fi
  $PY -m pip install --no-index --find-links="$WHEELS_DIR" \
    -r backend/requirements.txt --quiet 2>&1 | tail -5
  echo "  Installed $($PY -m pip list --format=columns 2>/dev/null | wc -l | tr -d ' ') packages"

  # ④ Build frontend
  echo "[3/5] Building frontend (vite)..."
  npx vite build --outDir dist 2>&1 | tail -3

  # ⑤ Package with electron-builder
  echo "[4/5] Packaging with electron-builder --mac --${ARCH}..."
  npx electron-builder --mac "--${ARCH}" 2>&1 | grep -E '(packaging|building|target|skipped|error|⨯)' || true

  # ⑥ Show results
  echo "[5/5] Done!"
  echo "  Output:"
  ls -lh release/*"${ARCH}"*.dmg 2>/dev/null || ls -lh release/*.dmg 2>/dev/null || echo "  (no DMG found)"
  echo ""
}

TARGET="${1:-all}"

if [ ! -d "build/wheels" ]; then
  echo "No wheels found. Running prebuild:wheels first..."
  npm run prebuild:wheels
fi

case "$TARGET" in
  arm64) build_one arm64 ;;
  x64)   build_one x64 ;;
  all)
    rm -rf release/*
    build_one arm64
    build_one x64
    echo "══════════════════════════════════════════════"
    echo "  All builds complete:"
    ls -lh release/*.dmg
    echo "══════════════════════════════════════════════"
    ;;
  *) echo "Usage: $0 {arm64|x64|all}"; exit 1 ;;
esac
