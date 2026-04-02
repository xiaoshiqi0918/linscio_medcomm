#!/bin/sh
# 执行镜像自带的 entrypoint 脚本（生成 UI 等），再用“请求时解析 upstream”的配置覆盖后启动 nginx
for f in /docker-entrypoint.d/*.sh; do [ -x "$f" ] && "$f"; done
cp /default.conf.resolver /etc/nginx/conf.d/default.conf
exec nginx -g "daemon off;"
