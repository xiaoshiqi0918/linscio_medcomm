# 门户系统文档

本目录为 **portal-system** 的部署与运维文档，与项目根目录 [README.md](../README.md) 配合使用。

## 部署与运维

| 文档 | 说明 |
|------|------|
| [部署-腾讯云轻量与宝塔.md](部署-腾讯云轻量与宝塔.md) | 腾讯云轻量 + 宝塔 + 域名 linscio.com.cn 的完整部署说明：域名规划、部署架构总览、各组件部署方式、端口规划、环境变量、Nginx 配置、日常运维 |
| [数据库设计.md](数据库设计.md) | 数据表结构（含建表 SQL）、授权码格式、Registry 凭证生成逻辑、数据备份策略与脚本说明 |
| [门户页面规划.md](门户页面规划.md) | 门户视觉规范（色彩/字体/组件）、路由、首页区块、用户中心页面规划 |

## 配置示例

- 宝塔 Nginx 反向代理配置见上级目录 [../deploy/baota-nginx-linscio.conf](../deploy/baota-nginx-linscio.conf)。
- 生产环境变量示例见 [../.env.production.example](../.env.production.example)。
