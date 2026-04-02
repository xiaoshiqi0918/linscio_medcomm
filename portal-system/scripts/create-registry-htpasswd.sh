#!/usr/bin/env sh
# 在首次启动 Registry 前生成 htpasswd，否则 registry:2 会因找不到认证文件而 panic
# 优先使用本机 htpasswd（apt install apache2-utils），避免国内服务器无法拉取 Docker 镜像
# 用法: ./scripts/create-registry-htpasswd.sh [用户名 [密码]]
# 默认: 用户名=registry, 密码=registry（仅用于开发；生产请改强密码）

set -e
AUTH_DIR="$(cd "$(dirname "$0")/.." && pwd)/registry/auth"
USER="${1:-registry}"
PASS="${2:-registry}"
mkdir -p "$AUTH_DIR"
if [ -f "$AUTH_DIR/htpasswd" ]; then
  echo "已存在 $AUTH_DIR/htpasswd，跳过生成。若要追加用户，请用: htpasswd -Bbn 用户名 密码 >> $AUTH_DIR/htpasswd"
  exit 0
fi

if command -v htpasswd >/dev/null 2>&1; then
  # 使用本机 htpasswd（Ubuntu/Debian: apt-get install apache2-utils）
  htpasswd -Bbn "$USER" "$PASS" > "$AUTH_DIR/htpasswd"
  echo "已生成 $AUTH_DIR/htpasswd（用户: $USER，本机 htpasswd）。现在可执行 docker compose up -d 启动服务。"
  exit 0
fi

# 回退到 Docker（若无法拉取镜像，请先安装本机 htpasswd: apt-get install -y apache2-utils）
if docker run --rm -v "$AUTH_DIR:/out" --entrypoint sh httpd:2.4 -c "htpasswd -Bbn $USER $PASS > /out/htpasswd" 2>/dev/null; then
  echo "已生成 $AUTH_DIR/htpasswd（用户: $USER，Docker httpd:2.4）。现在可执行 docker compose up -d 启动服务。"
  exit 0
fi

echo "错误：无法生成 htpasswd。请任选一种方式："
echo "  1) 安装本机 htpasswd 后重试: sudo apt-get update && sudo apt-get install -y apache2-utils"
echo "  2) 或配置 Docker 镜像加速后重试（见腾讯云/宝塔文档）"
exit 1
