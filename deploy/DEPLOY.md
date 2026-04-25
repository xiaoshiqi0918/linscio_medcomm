# LinScio MedComm SaaS 部署指南

> 香港轻量云 4核8G + Docker Compose 全栈部署

---

## 一、服务器准备

### 1.1 服务器配置

| 项目 | 配置 |
|------|------|
| 机型 | 腾讯云轻量应用服务器（中国香港）通用型 |
| 规格 | 4核 CPU / 8GB 内存 / 180GB SSD |
| 带宽 | 30Mbps 峰值 / 5TB 月流量 |
| 系统 | Ubuntu 24.04 LTS |

### 1.2 安装 Docker

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y ca-certificates curl gnupg
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
```

### 1.3 安装 Node.js（构建前端用）

```bash
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs
```

### 1.4 安全组/防火墙

腾讯云轻量控制台 → 防火墙，开放：**22**(SSH)、**80**(HTTP)、**443**(HTTPS)

### 1.5 域名解析

在 DNSPod / 域名管理中添加：

| 域名 | 类型 | 值 |
|------|------|-----|
| `www.linscio.com` | A | 服务器公网 IP |
| `linscio.com` | A | 服务器公网 IP |
| `releases.linscio.com` | CNAME | COS CDN 域名 |

### 1.6 SSL 证书

```bash
# Let's Encrypt 免费证书（先确保 80 端口可访问）
sudo apt install -y certbot
sudo certbot certonly --standalone -d www.linscio.com -d linscio.com

# 证书位置：
# /etc/letsencrypt/live/www.linscio.com/fullchain.pem
# /etc/letsencrypt/live/www.linscio.com/privkey.pem
```

或使用腾讯云免费证书，下载 Nginx 格式后上传到服务器。

---

## 二、部署步骤

### 2.1 拉取代码

```bash
sudo mkdir -p /opt/medcomm
sudo chown $USER:$USER /opt/medcomm
cd /opt/medcomm
git clone <仓库地址> .
```

### 2.2 配置环境变量

```bash
cd /opt/medcomm/deploy

# 生成安全密码
POSTGRES_PASSWORD=$(python3 -c "import secrets; print(secrets.token_urlsafe(24))")
REDIS_PASSWORD=$(python3 -c "import secrets; print(secrets.token_urlsafe(24))")
JWT_SECRET=$(python3 -c "import secrets; print(secrets.token_urlsafe(48))")

echo "记住这些密码："
echo "POSTGRES_PASSWORD=$POSTGRES_PASSWORD"
echo "REDIS_PASSWORD=$REDIS_PASSWORD"
echo "JWT_SECRET=$JWT_SECRET"
```

编辑生产配置：

```bash
cp .env.production .env.production.bak
nano .env.production
```

填写以下必填项：

```bash
DEPLOYMENT_MODE=saas
DEBUG=0

# 数据库密码（docker-compose 自动注入连接串，这里不需要填 DATABASE_URL）
POSTGRES_PASSWORD=<上面生成的>
REDIS_PASSWORD=<上面生成的>

# JWT
JWT_SECRET=<上面生成的>
JWT_ALGORITHM=HS256

# 腾讯云 COS
COS_SECRET_ID=<你的>
COS_SECRET_KEY=<你的>
COS_REGION=ap-shanghai
COS_BUCKET_RELEASES=linscio-releases-1363203425
COS_BUCKET_MANIFEST=linscio-releases-1363203425

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

### 2.3 放置 SSL 证书

```bash
mkdir -p /opt/medcomm/deploy/ssl

# Let's Encrypt 方式：
sudo cp /etc/letsencrypt/live/www.linscio.com/fullchain.pem /opt/medcomm/deploy/ssl/www.linscio.com_bundle.crt
sudo cp /etc/letsencrypt/live/www.linscio.com/privkey.pem /opt/medcomm/deploy/ssl/www.linscio.com.key
sudo chown $USER:$USER /opt/medcomm/deploy/ssl/*

# 腾讯云证书方式：直接上传到 deploy/ssl/ 目录
```

如果证书文件名不同，修改 `deploy/nginx.conf` 中的 `ssl_certificate` 和 `ssl_certificate_key` 路径。

### 2.4 构建前端

```bash
cd /opt/medcomm
npm install
VITE_API_BASE="" npx vite build
# 产物在 dist/ 目录
```

### 2.5 启动所有服务

```bash
cd /opt/medcomm/deploy
docker compose up -d --build
```

首次启动约需 3-5 分钟（构建后端镜像）。查看启动状态：

```bash
docker compose ps
docker compose logs -f backend
```

### 2.6 初始化数据库

```bash
docker compose exec backend alembic upgrade head
```

### 2.7 创建管理员

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

### 2.8 验证

```bash
curl https://www.linscio.com/health
# 应返回: {"status":"ok","mode":"saas",...}
```

浏览器访问 `https://www.linscio.com`，应看到登录页面。

---

## 三、内存分配规划

总计 8GB，各组件内存限制：

| 组件 | 容器限制 | 实际占用 | 说明 |
|------|---------|---------|------|
| PostgreSQL | 1.5GB | ~800MB-1.2GB | shared_buffers=384MB + 连接 + 缓存 |
| Redis | 384MB | ~50-256MB | maxmemory=256MB + 开销 |
| FastAPI (2 worker) | 1.5GB | ~400-800MB | LLM 调用是 IO 等待，不占内存 |
| Nginx | 128MB | ~30-50MB | 纯转发 |
| Docker 引擎 + 系统 | - | ~1GB | 系统保留 |
| **合计** | **3.5GB** | **~2.5-3.3GB** | **剩余 4.5-5.5GB 作为系统缓冲** |

充裕安全，即使所有容器同时达到限制上限（3.5GB），系统仍有 4.5GB 余量。

---

## 四、日常运维

### 4.1 查看日志

```bash
cd /opt/medcomm/deploy
docker compose logs -f backend      # 后端日志
docker compose logs -f postgres     # 数据库日志
docker compose logs -f nginx        # Nginx 日志
docker compose logs -f redis        # Redis 日志

# 只看最近 100 行
docker compose logs --tail=100 backend
```

### 4.2 重启服务

```bash
docker compose restart backend       # 只重启后端
docker compose restart               # 全部重启
```

### 4.3 更新代码

```bash
cd /opt/medcomm
git pull

# 重新构建前端（如前端有变更）
VITE_API_BASE="" npx vite build

# 重建后端镜像并重启（如后端有变更）
cd deploy
docker compose up -d --build backend

# 执行数据库迁移（如有）
docker compose exec backend alembic upgrade head
```

### 4.4 数据库备份

```bash
# 手动备份
mkdir -p /opt/backups
docker compose exec -T postgres pg_dump -U medcomm medcomm | gzip > /opt/backups/medcomm_$(date +%Y%m%d_%H%M).sql.gz

# 自动每日备份（加入 crontab）
(crontab -l 2>/dev/null; echo '0 3 * * * cd /opt/medcomm/deploy && docker compose exec -T postgres pg_dump -U medcomm medcomm | gzip > /opt/backups/medcomm_$(date +\%Y\%m\%d).sql.gz && find /opt/backups -name "*.sql.gz" -mtime +30 -delete') | crontab -
```

### 4.5 从备份恢复

```bash
gunzip < /opt/backups/medcomm_20260425.sql.gz | docker compose exec -T postgres psql -U medcomm medcomm
```

### 4.6 SSL 证书续期

```bash
# Let's Encrypt 自动续期（加入 crontab）
(crontab -l 2>/dev/null; echo '0 2 1 * * certbot renew --quiet && cp /etc/letsencrypt/live/www.linscio.com/fullchain.pem /opt/medcomm/deploy/ssl/www.linscio.com_bundle.crt && cp /etc/letsencrypt/live/www.linscio.com/privkey.pem /opt/medcomm/deploy/ssl/www.linscio.com.key && cd /opt/medcomm/deploy && docker compose restart nginx') | crontab -
```

### 4.7 监控

```bash
# 容器资源使用
docker stats

# 健康检查
curl -s http://localhost:8765/health | python3 -m json.tool

# 磁盘空间
df -h

# Docker 磁盘占用
docker system df
```

---

## 五、架构图

```
用户浏览器
    │
    ▼
┌─────────────────────────────────────────┐
│ 腾讯云轻量 香港 4核8G                      │
│                                          │
│  Nginx (:443 HTTPS)                      │
│    ├── /assets/*  → 静态文件 (dist/)      │
│    ├── /api/*     → FastAPI (:8765)      │
│    └── /*         → index.html (SPA)     │
│                                          │
│  FastAPI (:8765) [1.5GB 限制]            │
│    ├── PostgreSQL (:5432) [1.5GB 限制]   │
│    ├── Redis (:6379) [384MB 限制]        │
│    └── 外部调用 ↓                         │
└─────────────────────────────────────────┘
         │
         ├── LLM APIs（香港直连，无需代理）
         │    ├── DeepSeek / Moonshot / GPT
         │    ├── Gemini（香港可直连）
         │    └── 通义千问 / 智谱
         │
         ├── 腾讯云 COS（安装包 / 学科包）
         └── 易支付（充值回调）
```

---

## 六、故障排查

| 症状 | 排查命令 |
|------|---------|
| 502 Bad Gateway | `docker compose ps` 看 backend 状态; `docker compose logs backend` |
| 数据库连接失败 | `docker compose exec postgres pg_isready -U medcomm` |
| Redis 连接失败 | `docker compose exec redis redis-cli -a $REDIS_PASSWORD ping` |
| 容器 OOM 被杀 | `docker inspect <容器ID> \| grep OOMKilled`; `docker stats` |
| CORS 错误 | 确认域名是 `https://www.linscio.com`; 检查 `DEBUG=0` |
| 支付回调失败 | 确认 `YIPAY_NOTIFY_URL` 为 HTTPS 且外网可达 |
| LLM 调用失败 | 检查 API Key; `docker compose logs backend \| grep "LLM"` |
| 前端空白 | 确认 `dist/index.html` 存在; `docker compose logs nginx` |
| 磁盘满 | `df -h`; `docker system prune -a` 清理旧镜像 |
| 容器内存超限 | `docker stats`; 调整 docker-compose.yml 中的 mem_limit |

---

## 七、安全加固

```bash
# 1. 禁止 root SSH
sudo sed -i 's/#PermitRootLogin yes/PermitRootLogin no/' /etc/ssh/sshd_config
sudo systemctl restart sshd

# 2. 自动安全更新
sudo apt install -y unattended-upgrades
sudo dpkg-reconfigure -plow unattended-upgrades

# 3. Docker 日志大小限制（防止日志撑爆磁盘）
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

---

## 八、香港服务器优势

| 优势 | 说明 |
|------|------|
| LLM 直连 | OpenAI、Google Gemini 无需代理，延迟低 |
| 免备案 | 域名无需 ICP 备案，即买即用 |
| 国内访问 | 腾讯云香港到大陆延迟约 30-50ms，体验良好 |
| 合规灵活 | 适合使用海外 API 的 SaaS 产品 |
