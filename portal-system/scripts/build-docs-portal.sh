#!/usr/bin/env bash
# Build portal docs and copy to portal-system/portal/public/docs for serving at /docs/
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$REPO_ROOT/linscio-docs"
npm run build:portal
mkdir -p "$REPO_ROOT/portal-system/portal/public"
rm -rf "$REPO_ROOT/portal-system/portal/public/docs"
cp -r dist/portal "$REPO_ROOT/portal-system/portal/public/docs"
echo "Portal docs built and copied to portal-system/portal/public/docs"
