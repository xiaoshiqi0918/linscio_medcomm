# 在 joxit 镜像生成的配置之上，用“请求时解析 upstream”的配置覆盖，避免 host not found in upstream
# 构建上下文为 portal-system 根目录
FROM joxit/docker-registry-ui:latest

COPY registry/registry-ui-default.conf /default.conf.resolver
COPY registry-ui/custom-entrypoint.sh /custom-entrypoint.sh
RUN chmod +x /custom-entrypoint.sh

ENTRYPOINT ["/custom-entrypoint.sh"]
