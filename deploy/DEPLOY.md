# LinScio MedComm SaaS 部署指南

> 宝塔面板 + Docker Compose 方案
> 腾讯云轻量（香港）通用型 4核8G · 公网 IP 43.129.175.64

---

## 架构总览

```
用户浏览器
    │
    ▼
┌──────────────────────────────────────────────────┐
│ 腾讯云轻量 香港 4核8G  (43.129.175.64)           │
│                                                   │
│  ┌─ 宝塔面板管理 ─────────────────────────────┐   │
│  │  Nginx (:443 HTTPS)                        │   │
│  │    ├── /assets/*  → 静态文件 (dist/)        │   │
│  │    ├── /api/*     → 反代 127.0.0.1:8765    │   │
│  │    └── /*         → index.html (SPA)       │   │
│  │  SSL 证书自动续期 (Let's Encrypt)           │   │
│  │  防火墙管理                                 │   │
│  └────────────────────────────────────────────┘   │
│                                                   │
│  ┌─ Docker Compose ──────────────────────────┐    │
│  │  FastAPI  (:8765) [1.5GB 限制]            │    │
│  │  PostgreSQL (:5432) [1.5GB 限制]          │    │
│  │  Redis (:6379) [384MB 限制]               │    │
│  └───────────────────────────────────────────┘    │
│                                                   │
│  外部调用:                                        │
│    ├── LLM APIs（香港直连，无需代理）              │
│    ├── 腾讯云 COS（安装包 / 学科包）              │
│    └── 易支付（充值回调）                          │
└──────────────────────────────────────────────────┘
```

### 职责划分

| 组件 | 管理方 | 说明 |
|------|--------|------|
| Nginx + SSL | 宝塔面板 | 反向代理、HTTPS、限流、静态文件 |
| FastAPI 后端 | Docker Compose | 业务逻辑、API |
| PostgreSQL | Docker Compose | 数据库 |
| Redis | Docker Compose | 缓存、会话、限流 |
| 防火墙 | 宝塔面板 | 端口管理 |
| 监控 | 宝塔面板 | CPU/内存/磁盘监控 |

---

## 一、服务器准备

### 1.1 服务器配置

| 项目 | 配置 |
|------|------|
| 机型 | 腾讯云轻量应用服务器（中国香港）通用型 |
| 规格 | 4核 CPU / 8GB 内存 / 180GB SSD |
| 带宽 | 30Mbps 峰值 / 5TB 月流量 |
| 公网 IP | 43.129.175.64 |
| 系统 | Ubuntu 24.04 LTS |

### 1.2 安装宝塔面板

```bash
# Ubuntu/Debian
wget -O install.sh https://download.bt.cn/install/install-ubuntu_6.0.sh && sudo bash install.sh ed8484bec

# 安装完成后会显示：
# 面板地址: http://服务器IP:8888/xxxxxxxx
# 用户名: xxxxxxxx
# 密码: xxxxxxxx
# ⚠️ 立即记录这些信息！
```

首次登录宝塔面板后：

1. **安装推荐套件**：选择 **Nginx**（必装），MySQL/PHP 不需要
2. **进入面板 → 面板设置**：
   - 修改默认端口（8888 → 其他端口，如 29876）
   - 修改用户名和密码
   - 开启面板 SSL

### 1.3 安装 Docker（通过宝塔）

宝塔面板 → **Docker** → 安装 Docker 服务

或手动安装：

```bash
sudo apt update && sudo apt install -y ca-certificates curl gnupg
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
```

### 1.4 安装 Node.js（构建前端用）

```bash
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs
```

### 1.5 防火墙配置

宝塔面板 → **安全** → 放行端口：

| 端口 | 说明 |
|------|------|
| 22 | SSH |
| 80 | HTTP（Nginx） |
| 443 | HTTPS（Nginx） |
| 你的宝塔端口 | 宝塔面板访问 |

> ⚠️ **5432、6379、8765 不要开放到公网**，它们只绑定 127.0.0.1

同时在腾讯云轻量控制台 → 防火墙中放行相同端口。

### 1.6 域名解析

在 DNSPod / 域名管理中添加：

| 域名 | 类型 | 值 |
|------|------|-----|
| `www.linscio.com` | A | `43.129.175.64` |
| `linscio.com` | A | `43.129.175.64` |
| `releases.linscio.com` | CNAME | COS CDN 域名 |

---

## 二、Docker Compose 部署

### 2.1 拉取代码

```bash
sudo mkdir -p /www/wwwroot/linscio_medcomm
sudo chown $USER:$USER /www/wwwroot/linscio_medcomm
cd /www/wwwroot/linscio_medcomm
git clone https://github.com/xiaoshiqi0918/linscio_medcomm.git .
```

### 2.2 配置环境变量

```bash
cd /www/wwwroot/linscio_medcomm/deploy

# 生成安全密码
POSTGRES_PASSWORD=$(python3 -c "import secrets; print(secrets.token_urlsafe(24))")
REDIS_PASSWORD=$(python3 -c "import secrets; print(secrets.token_urlsafe(24))")
JWT_SECRET=$(python3 -c "import secrets; print(secrets.token_urlsafe(48))")

echo "═══════════════════════════════════════"
echo "请保存以下密码："
echo "POSTGRES_PASSWORD=$POSTGRES_PASSWORD"
echo "REDIS_PASSWORD=$REDIS_PASSWORD"
echo "JWT_SECRET=$JWT_SECRET"
echo "═══════════════════════════════════════"
```

创建 docker-compose 使用的 `.env` 文件：

```bash
cat > .env << EOF
POSTGRES_PASSWORD=$POSTGRES_PASSWORD
REDIS_PASSWORD=$REDIS_PASSWORD
EOF
```

编辑生产配置：

```bash
nano .env.production
```

填写以下必填项：

```ini
DEPLOYMENT_MODE=saas
DEBUG=0

# JWT
JWT_SECRET=<上面生成的>
JWT_ALGORITHM=HS256

# 腾讯云 COS
COS_SECRET_ID=<你的>
COS_SECRET_KEY=<你的>
COS_REGION=ap-shanghai
COS_BUCKET_RELEASES=linscio-releases-1363203425
COS_BUCKET_MANIFEST=linscio-releases-1363203425

# CDN
CDN_DOMAIN_RELEASES=releases.linscio.com
CDN_AUTH_SECRET=<CDN鉴权密钥>

# LLM API Keys（至少填一个）
DEEPSEEK_API_KEY=sk-xxx
DEEPSEEK_BASE_URL=https://api.deepseek.com
# ... 其他 LLM Key 按需填写

# 支付
YIPAY_PID=<你的>
YIPAY_KEY=<你的>
YIPAY_GATEWAY=https://zpayz.cn
YIPAY_NOTIFY_URL=https://www.linscio.com/api/v1/payment/notify
YIPAY_RETURN_URL=https://www.linscio.com/settings

# 桌面端远程认证
SAAS_API_URL=https://www.linscio.com
```

### 2.3 构建前端

```bash
cd /www/wwwroot/linscio_medcomm
npm install
VITE_API_BASE="" npx vite build
# 产物在 dist/ 目录
```

### 2.4 启动 Docker 服务

```bash
cd /www/wwwroot/linscio_medcomm/deploy
docker compose up -d --build
```

首次启动约需 3-5 分钟（构建后端镜像）。查看状态：

```bash
docker compose ps        # 三个服务应全部 running
docker compose logs -f backend   # 查看后端启动日志
```

### 2.5 初始化数据库

```bash
docker compose exec backend alembic upgrade head
```

### 2.6 创建管理员

```bash
docker compose exec backend python3 -c "
import asyncio
from app.core.database import get_session, init_db
from app.models.user import User
from app.core.security import hash_password

async def create_admin():
    await init_db()
    async for db in get_session():
        user = User(
            phone='你的手机号',
            password_hash=hash_password('你的密码'),
            display_name='管理员',
            is_admin=True,
        )
        db.add(user)
        await db.commit()
        print(f'管理员创建成功, ID: {user.id}')
        break

asyncio.run(create_admin())
"
```

---

## 三、宝塔面板配置

### 3.1 创建网站

宝塔面板 → **网站** → **添加站点**：

| 设置项 | 值 |
|--------|-----|
| 域名 | `www.linscio.com` |
| 备注 | LinScio MedComm SaaS |
| 根目录 | `/www/wwwroot/linscio_medcomm/dist` |
| PHP版本 | 纯静态 |

### 3.1.1 裸域跳转（推荐）

为 `linscio.com` 单独添加一个站点，然后在该站点设置中开启 **重定向**：

- 目标 URL：`https://www.linscio.com`
- 状态码：301

这样用户访问 `linscio.com` 会自动跳转到 `www.linscio.com`，避免双入口导致的 SEO 和登录态不一致问题。

### 3.2 配置 SSL 证书

宝塔面板 → 网站 → `www.linscio.com` → **SSL**：

1. 选择 **Let's Encrypt**
2. 勾选 `www.linscio.com` 和 `linscio.com`
3. 点击 **申请**
4. 开启 **强制 HTTPS**

> 宝塔会自动配置证书续期，无需手动管理。

### 3.3 配置 Nginx 限流（全局）

宝塔面板 → **软件商店** → Nginx → **设置** → **配置修改**

在 `http { }` 块末尾（`}` 之前）添加：

```nginx
# LinScio 限流区域
limit_req_zone $binary_remote_addr zone=api_general:10m rate=30r/s;
limit_req_zone $binary_remote_addr zone=auth_login:5m rate=5r/m;
limit_req_zone $binary_remote_addr zone=auth_register:5m rate=3r/m;
limit_req_zone $binary_remote_addr zone=api_generate:5m rate=10r/m;
limit_req_zone $binary_remote_addr zone=api_payment:5m rate=5r/m;
```

保存并重启 Nginx。

### 3.4 配置网站反向代理和路由规则

宝塔面板 → 网站 → `www.linscio.com` → **配置文件**

找到 `server { }` 块，在其中（`ssl` 相关配置之后）**替换或添加**以下 `location` 规则：

```nginx
    # ── 安全响应头 ──
    add_header X-Frame-Options SAMEORIGIN always;
    add_header X-Content-Type-Options nosniff always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;

    # ── Gzip 压缩 ──
    gzip on;
    gzip_vary on;
    gzip_min_length 1024;
    gzip_types text/plain text/css application/json application/javascript text/xml application/xml text/javascript image/svg+xml;

    # ── 上传大小限制（文献 PDF）──
    client_max_body_size 50m;

    # ── 静态资源长缓存 ──
    location /assets/ {
        expires 30d;
        add_header Cache-Control "public, immutable";
    }

    # ── 登录限流 ──
    location /api/v1/auth/login {
        limit_req zone=auth_login burst=3 nodelay;
        limit_req_status 429;
        proxy_pass http://127.0.0.1:8765;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # ── 注册限流 ──
    location /api/v1/auth/register {
        limit_req zone=auth_register burst=2 nodelay;
        limit_req_status 429;
        proxy_pass http://127.0.0.1:8765;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # ── 生成接口限流 + SSE ──
    location ~ /api/v1/medcomm/(sections/.*/generate|articles/.*/generate-all) {
        limit_req zone=api_generate burst=5 nodelay;
        limit_req_status 429;
        proxy_pass http://127.0.0.1:8765;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 300s;
    }

    # ── 支付创建限流 ──
    location /api/v1/payment/create-order {
        limit_req zone=api_payment burst=2 nodelay;
        limit_req_status 429;
        proxy_pass http://127.0.0.1:8765;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # ── 支付回调（不限流）──
    location /api/v1/payment/notify {
        proxy_pass http://127.0.0.1:8765;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # ── API 通用反代 ──
    location /api/ {
        limit_req zone=api_general burst=20 nodelay;
        proxy_pass http://127.0.0.1:8765;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 300s;
    }

    # ── 健康检查 ──
    location /health {
        proxy_pass http://127.0.0.1:8765;
    }

    # ── Prometheus（仅本机）──
    location /metrics {
        allow 127.0.0.1;
        deny all;
        proxy_pass http://127.0.0.1:8765;
    }

    # ── Vue Router history 模式（必须放最后）──
    location / {
        try_files $uri $uri/ /index.html;
    }
```

> 完整配置文件也可参考 `deploy/bt-nginx.conf`。

保存后点击「重载配置」。

### 3.5 验证部署

```bash
curl https://www.linscio.com/health
# 应返回: {"status":"ok","mode":"saas",...}
```

浏览器访问 `https://www.linscio.com`，应看到科普写作页面。

---

## 四、内存分配

总计 8GB，各组件内存分配：

| 组件 | 限制 | 实际占用 | 说明 |
|------|------|---------|------|
| PostgreSQL | 1.5GB | ~800MB-1.2GB | shared_buffers=384MB + 连接 + 缓存 |
| Redis | 384MB | ~50-256MB | maxmemory=256MB + 开销 |
| FastAPI | 1.5GB | ~400-800MB | LLM 调用是 IO 等待，不占内存 |
| 宝塔 + Nginx | - | ~200-300MB | 宝塔面板 + Nginx worker |
| Docker 引擎 + 系统 | - | ~1GB | 系统保留 |
| **合计** | | **~2.5-3.5GB** | **剩余 4.5-5.5GB 作为缓冲** |

---

## 五、日常运维

### 5.1 查看日志

```bash
cd /www/wwwroot/linscio_medcomm/deploy
docker compose logs -f backend      # 后端日志
docker compose logs -f postgres     # 数据库日志
docker compose logs -f redis        # Redis 日志

# 只看最近 100 行
docker compose logs --tail=100 backend
```

Nginx 日志在宝塔面板中查看：网站 → `www.linscio.com` → 日志

### 5.2 重启服务

```bash
docker compose restart backend       # 只重启后端
docker compose restart               # 全部重启
```

Nginx 重启：宝塔面板 → Nginx → 重启

### 5.3 更新代码

```bash
cd /www/wwwroot/linscio_medcomm
git pull

# 重新构建前端（如前端有变更）
VITE_API_BASE="" npx vite build

# 重建后端镜像并重启（如后端有变更）
cd deploy
docker compose up -d --build backend

# 执行数据库迁移（如有）
docker compose exec backend alembic upgrade head
```

### 5.4 数据库备份

```bash
# 手动备份
mkdir -p /opt/backups
docker compose exec -T postgres pg_dump -U medcomm medcomm | gzip > /opt/backups/medcomm_$(date +%Y%m%d_%H%M).sql.gz

# 自动每日备份（宝塔 → 计划任务 → Shell 脚本，每天 03:00）
cd /www/wwwroot/linscio_medcomm/deploy && docker compose exec -T postgres pg_dump -U medcomm medcomm | gzip > /opt/backups/medcomm_$(date +%Y%m%d).sql.gz && find /opt/backups -name "*.sql.gz" -mtime +30 -delete
```

也可以用宝塔自带的**计划任务**功能，添加 Shell 脚本类型的定时任务。

### 5.5 从备份恢复

```bash
gunzip < /opt/backups/medcomm_20260426.sql.gz | docker compose exec -T postgres psql -U medcomm medcomm
```

### 5.6 监控

```bash
# 容器资源使用
docker stats

# 健康检查
curl -s http://localhost:8765/health | python3 -m json.tool
```

宝塔面板自带 CPU、内存、磁盘、网络的实时监控图表。

---

## 六、故障排查

| 症状 | 排查方法 |
|------|---------|
| 502 Bad Gateway | `docker compose ps` 看 backend 状态; `docker compose logs backend` |
| 数据库连接失败 | `docker compose exec postgres pg_isready -U medcomm` |
| Redis 连接失败 | `docker compose exec redis redis-cli -a $REDIS_PASSWORD ping` |
| 容器 OOM 被杀 | `docker inspect <容器ID> \| grep OOMKilled`; `docker stats` |
| CORS 错误 | 确认域名是 `https://www.linscio.com`; 检查 `DEBUG=0` |
| 支付回调失败 | 确认 `YIPAY_NOTIFY_URL` 为 HTTPS 且外网可达 |
| LLM 调用失败 | 检查 API Key; `docker compose logs backend \| grep "LLM"` |
| 前端空白 | 确认 `dist/index.html` 存在; 宝塔查看 Nginx 日志 |
| 磁盘满 | `df -h`; `docker system prune -a` 清理旧镜像 |
| Nginx 配置错误 | 宝塔面板 → Nginx → 检查配置语法 |

---

## 七、安全加固

### 7.1 SSH 安全

```bash
# 禁止 root 登录
sudo sed -i 's/#PermitRootLogin yes/PermitRootLogin no/' /etc/ssh/sshd_config
sudo systemctl restart sshd
```

### 7.2 自动安全更新

```bash
sudo apt install -y unattended-upgrades
sudo dpkg-reconfigure -plow unattended-upgrades
```

### 7.3 Docker 日志大小限制

```bash
sudo tee /etc/docker/daemon.json << 'EOF'
{
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "50m",
    "max-file": "3"
  }
}
EOF
sudo systemctl restart docker
```

### 7.4 宝塔面板安全

- 修改默认端口（8888 → 自定义高端口）
- 修改默认用户名和密码
- 开启面板 SSL
- 设置授权 IP（仅自己 IP 可访问面板）
- 开启 BasicAuth 二次验证

---

## 八、香港服务器优势

| 优势 | 说明 |
|------|------|
| LLM 直连 | OpenAI、Google Gemini 无需代理，延迟低 |
| 免备案 | 域名无需 ICP 备案，即买即用 |
| 国内访问 | 腾讯云香港到大陆延迟约 30-50ms，体验良好 |
| 合规灵活 | 适合使用海外 API 的 SaaS 产品 |

---

## 九、部署清单（Checklist）

部署前逐项确认：

- [ ] 服务器购买并初始化（Ubuntu 24.04）
- [ ] 宝塔面板安装并修改默认端口/密码
- [ ] Docker 安装完成
- [ ] Node.js 安装完成
- [ ] 域名 DNS 解析配置（www / 裸域 / releases）
- [ ] 防火墙开放 22 / 80 / 443 / 宝塔端口
- [ ] 代码克隆到 `/www/wwwroot/linscio_medcomm`
- [ ] `.env.production` 填写所有必填项
- [ ] `.env` 设置 PG/Redis 密码
- [ ] 前端构建完成（`dist/` 目录存在）
- [ ] Docker 三服务启动成功
- [ ] Alembic 数据库迁移完成
- [ ] 管理员账号创建
- [ ] 宝塔创建网站指向 `/www/wwwroot/linscio_medcomm/dist`
- [ ] SSL 证书申请成功
- [ ] Nginx 反代配置完成（参考 `bt-nginx.conf`）
- [ ] `curl https://www.linscio.com/health` 返回正常
- [ ] 浏览器访问正常，登录测试通过
- [ ] 每日备份计划任务已创建
