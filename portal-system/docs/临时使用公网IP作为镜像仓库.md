# 临时使用公网 IP 作为镜像仓库（域名备案前）

在域名备案完成前，可临时使用服务器公网 IP `1.15.136.213` 提供镜像拉取，用户通过 `docker login 1.15.136.213:5000` 拉取镜像。

---

## 一、服务器端配置

### 1. 环境变量（.env）

在服务器上的 **portal-system** 项目根目录 `.env` 中设置：

```bash
# 临时：镜像仓库对外地址改为公网 IP:端口（用户 docker login / pull 时使用）
REGISTRY_URL=1.15.136.213:5000
```

API 会把该地址写入用户凭证，门户「用户中心」里显示的 Registry 地址即为 `1.15.136.213:5000`。

### 2. 暴露 5000 端口

当前 `docker-compose.yml` 中 registry-proxy 端口为 `127.0.0.1:5000:5000`，仅本机可访问。要允许外网访问，任选其一：

**方式 A：使用 override 文件（推荐）**

在项目根目录创建 `docker-compose.override.yml`（仅用于当前服务器，可不提交到 Git）：

```yaml
# 临时暴露 5000 到所有网卡，供外网 docker pull
services:
  linscio-registry-proxy:
    ports:
      - "5000:5000"
```

然后执行：

```bash
docker compose up -d
```

Compose 会自动合并 `docker-compose.yml` 与 `docker-compose.override.yml`，registry-proxy 将监听 `0.0.0.0:5000`。

**方式 B：直接改 docker-compose.yml**

将 `linscio-registry-proxy` 的 `ports` 从 `"127.0.0.1:5000:5000"` 改为 `"5000:5000"`。  
备案完成后记得改回 `127.0.0.1:5000:5000`，并通过 Nginx 域名对外提供 443。

### 3. 云服务器安全组 / 防火墙

在腾讯云（或其它云）控制台为该实例开放 **入站 5000/TCP**，否则外网无法访问。

- 腾讯云轻量：防火墙 → 添加规则 → 端口 5000，协议 TCP，来源 0.0.0.0/0（或按需限制）。
- 若使用宝塔：安全 → 放行 5000。

### 4. 重启服务使配置生效

```bash
cd /www/wwwroot/linscio/portal-system   # 或你的实际路径
# 若使用了 override，确保 docker-compose.override.yml 存在
docker compose up -d linscio-api linscio-registry-proxy
```

---

## 二、用户端配置（拉取镜像的电脑）

Docker 默认对非 localhost 的 Registry 要求 HTTPS。使用 IP:5000 需将 Registry 设为“非安全”：

**Linux（/etc/docker/daemon.json）：**

```json
{
  "insecure-registries": ["1.15.136.213:5000"]
}
```

然后执行：`sudo systemctl restart docker`

**macOS / Windows（Docker Desktop）— 按下方详细步骤操作。**

**示例**：若 Docker Engine 中已有如下内容，只需在 `registry-mirrors` 的 `]` 后加逗号，并新增 `insecure-registries` 一行：

```json
{
  "builder": {
    "gc": {
      "defaultKeepStorage": "20GB",
      "enabled": true
    }
  },
  "experimental": false,
  "registry-mirrors": [
    "https://docker.1ms.run",
    "https://docker.xuanyuan.me",
    "https://hub.rat.dev"
  ],
  "insecure-registries": ["1.15.136.213:5000"]
}
```

（关键：`]` 后要加 **逗号** `,`，再写 `"insecure-registries"` 那一行。）

#### macOS（Docker Desktop）

1. 点击菜单栏右上角的 **Docker 图标**（鲸鱼）。
2. 选择 **Settings / 设置**（或 **Preferences / 偏好设置**）。
3. 左侧点击 **Docker Engine**。
4. 右侧会显示一个 JSON 文本框（可能已有 `"builder"`、`"experimental"` 等）。
5. 在 JSON 的**最外层花括号 `{}` 内**添加一行（注意逗号）：
   ```json
   "insecure-registries": ["1.15.136.213:5000"]
   ```
   - 若当前只有 `{}`，改成：
     ```json
     {
       "insecure-registries": ["1.15.136.213:5000"]
     }
     ```
   - 若已有其他配置，在最后一个属性后加逗号，再加这一行，例如：
     ```json
     {
       "builder": { ... },
       "insecure-registries": ["1.15.136.213:5000"]
     }
     ```
6. 点击 **Apply & restart / 应用并重启**，等待 Docker 重启完成。

#### Windows（Docker Desktop）

1. 右键点击系统托盘（任务栏右下角）的 **Docker 图标**。
2. 选择 **Settings**（设置）。
3. 左侧点击 **Docker Engine**。
4. 右侧会显示 **JSON 配置**（可能已有 `"builder"`、`"experimental"` 等）。
5. 在 JSON 的**最外层花括号 `{}` 内**添加一行（注意逗号）：
   ```json
   "insecure-registries": ["1.15.136.213:5000"]
   ```
   - 若当前只有 `{}`，改成：
     ```json
     {
       "insecure-registries": ["1.15.136.213:5000"]
     }
     ```
   - 若已有其他配置，在最后一个属性后加逗号，再加这一行。
6. 点击 **Apply & restart**（应用并重启），等待 Docker 重启完成。

**注意**：JSON 中每行末尾要有逗号，但最后一个属性后不能有逗号；若修改后报错“JSON 格式错误”，请检查花括号和逗号是否匹配。

---

## 三、管理员：上传镜像到仓库

将 **linscio-ai**、**linscio-db** 等镜像推送到 `1.15.136.213:5000`，用户才能从该地址拉取。镜像需在 **LinScio AI 主项目**中构建，再推送到本仓库。

### 1. 本机准备

- 已配置 **insecure-registries**（见上文「二、用户端配置」）。
- 本机已能访问 `1.15.136.213:5000`（网络/防火墙正常）。

### 2. 使用管理员账号登录 Registry

推送需使用**已写入 Registry 认证**的账号（如管理员 `admin`，与门户「创建管理员」时一致）：

```bash
docker login 1.15.136.213:5000
# Username: admin（或你的管理员用户名）
# Password: （创建管理员时设置的密码，如 admin123）
```

### 3. 构建镜像（在主项目中）

在 **LinScio AI 主项目**（含 Dockerfile 构建 linscio-ai、linscio-db 的仓库）中构建镜像，例如：

```bash
cd /path/to/linscio-ai-main-project
docker build -t linscio-ai:latest -f Dockerfile .
# 若有独立数据库镜像：
# docker build -t linscio-db:latest -f docker/linscio-db.Dockerfile .
```

### 4. 打标签并推送

把本地镜像打成「Registry 地址 + 仓库名 + Tag」，再推送：

```bash
# 应用镜像
docker tag linscio-ai:latest 1.15.136.213:5000/linscio-ai:latest
docker push 1.15.136.213:5000/linscio-ai:latest

# 数据库镜像（若有）
docker tag linscio-db:latest 1.15.136.213:5000/linscio-db:latest
docker push 1.15.136.213:5000/linscio-db:latest
```

可按需推送多个 Tag（如 `latest`、`v1.0.0`）：

```bash
docker tag linscio-ai:latest 1.15.136.213:5000/linscio-ai:v1.0.0
docker push 1.15.136.213:5000/linscio-ai:v1.0.0
```

### 5. 验证

- 在服务器上打开 Registry Web UI（若已部署）：`http://1.15.136.213:5001`，用管理员账号登录，查看是否有 `linscio-ai`、`linscio-db` 及对应 Tag。
- 或在本机执行：`docker pull 1.15.136.213:5000/linscio-ai:latest` 验证可拉取。

**说明**：门户「套餐 / 可拉取 Tag」由管理后台的**模块权限**与**套餐的 allowed_image_tags** 控制；推送的镜像名与 Tag 需与授权码套餐允许的规则一致（如 `linscio-ai:latest`、`linscio-ai:v*`），用户激活后才能在「用户中心」看到对应拉取示例并成功拉取。

---

## 四、用户使用流程（拉取）

1. 在门户注册并登录，进入「用户中心」。
2. 激活授权码，在「获取 LinScio AI 镜像」卡片中查看 **Registry 登录凭证**（地址会显示为 `1.15.136.213:5000`）。
3. 在本机按上文配置好 `insecure-registries` 后执行：

```bash
docker login 1.15.136.213:5000
# 输入用户中心显示的用户名和密码

docker pull 1.15.136.213:5000/linscio-ai:latest
# 其它镜像同理，如 1.15.136.213:5000/linscio-db:latest
```

---

## 五、常见问题：push 报错 "server closed idle connection"

**现象**：`docker push 1.15.136.213:5000/linscio-ai:latest` 时出现 `failed to do request: Post "...": http: server closed idle connection`。

**原因与处理**：

1. **确认使用 HTTP**  
   错误信息里若出现 `https://1.15.136.213:5000`，说明 Docker 可能仍走 HTTPS，而当前仓库是 HTTP。请确认 Docker Engine 里已添加 `"insecure-registries": ["1.15.136.213:5000"]` 并已重启 Docker，再重试 push。

2. **代理超时过短（已修复）**  
   registry-proxy 原先对上游请求超时为 60 秒，推送大镜像时易被判定为空闲并断连。已在代码中将 **推送（POST/PUT）** 的超时改为 **30 分钟**。  
   **操作**：在服务器上拉取最新代码后重新构建并重启 registry-proxy：
   ```bash
   cd /www/wwwroot/linscio/portal-system   # 或你的实际路径
   docker compose build linscio-registry-proxy
   docker compose up -d linscio-registry-proxy
   ```
   然后再在本机执行 `docker push`。

3. **若前面有 Nginx 反向代理**  
   若 5000 前还有 Nginx，需调大超时与 body 大小，例如在对应 `server` 或 `location` 中：
   ```nginx
   proxy_read_timeout 1800s;
   proxy_send_timeout 1800s;
   client_max_body_size 0;
   ```
   然后 `nginx -t` 与 `nginx -s reload`。

---

## 六、备案完成后切回域名

1. 在 `.env` 中把 `REGISTRY_URL` 改回域名，例如：`REGISTRY_URL=registry.linscio.com.cn`。
2. 若使用了 `docker-compose.override.yml`，删除其中对 5000 端口的覆盖，或改回 `127.0.0.1:5000:5000`，对外只通过 Nginx 的 `registry.linscio.com.cn`（443）访问。
3. 在 Nginx 中配置 `registry.linscio.com.cn` 反向代理到 `127.0.0.1:5000`（参见 `deploy/baota-nginx-linscio.conf`）。
4. 重启 API 与 registry-proxy：`docker compose up -d linscio-api linscio-registry-proxy`。
5. 通知用户后续使用 `docker login registry.linscio.com.cn` 和 `docker pull registry.linscio.com.cn/...`，并可从本机 `insecure-registries` 中移除 `1.15.136.213:5000`。
