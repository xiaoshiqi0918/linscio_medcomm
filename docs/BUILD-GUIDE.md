# LinScio MedComm 构建 & Git 操作指南

> 本文档包含所有打包、推送、拉取相关指令。适用于 v0.2+ 分包模式。

---

## 一、GitHub 推送指令（完整流程）

### 1. 首次推送前准备

```bash
# ── 进入项目目录 ──
cd /Users/xiaoshiqi/linscio/linscio_medcomm

# ── 初始化 Git（如果还未初始化） ──
git init
git branch -M main

# ── 配置远程仓库（使用 Personal Access Token） ──
# ⚠️ 将 <YOUR_TOKEN> 替换为你的 GitHub PAT
git remote add origin https://<YOUR_TOKEN>@github.com/xiaoshiqi0918/linscio_medcomm.git

# ── 如果已有 remote，更新 URL ──
git remote set-url origin https://<YOUR_TOKEN>@github.com/xiaoshiqi0918/linscio_medcomm.git

# ── 验证远程配置 ──
git remote -v
```

### 2. 每次推送前检查

```bash
cd /Users/xiaoshiqi/linscio/linscio_medcomm

# ── 查看当前状态：哪些文件改了、哪些未跟踪 ──
git status

# ── 查看具体改了什么 ──
git diff

# ── 查看未跟踪的文件 ──
git status --porcelain
```

### 3. 添加、提交、推送（三步走）

```bash
cd /Users/xiaoshiqi/linscio/linscio_medcomm

# ── 第一步：添加所有改动到暂存区 ──
git add -A

# ── 第二步：提交（commit message 找我帮你写） ──
git commit -m "你的提交信息"

# ── 第三步：推送到 GitHub ──
git push -u origin main
```

### 4. 一键推送（确认无误后可用）

```bash
cd /Users/xiaoshiqi/linscio/linscio_medcomm
git add -A && git commit -m "你的提交信息" && git push -u origin main
```

### 5. 完整推送示例（含 Token）

```bash
cd /Users/xiaoshiqi/linscio/linscio_medcomm
git remote set-url origin https://<YOUR_TOKEN>@github.com/xiaoshiqi0918/linscio_medcomm.git
git add -A
git commit -m "feat: 分包模式 + 打包脚本优化"
git push -u origin main
```

> **安全提醒**：
> - Token 只需在 remote URL 中配置一次，后续 push/pull 自动使用
> - 不要在 commit message 或代码中包含 Token
> - 建议使用 `git credential-store` 或 macOS Keychain 存储凭证

---

## 二、GitHub 拉取指令

### 1. 在本机拉取最新代码

```bash
cd /Users/xiaoshiqi/linscio/linscio_medcomm

# ── 拉取并合并 ──
git pull origin main

# ── 如果有本地改动冲突，先暂存 ──
git stash
git pull origin main
git stash pop
```

### 2. 在腾讯云 Windows 服务器拉取

```cmd
cd C:\linscio_medcomm

REM 拉取最新代码
git pull origin main

REM 如果是全新服务器
git clone https://<YOUR_TOKEN>@github.com/xiaoshiqi0918/linscio_medcomm.git C:\linscio_medcomm
cd C:\linscio_medcomm
```

### 3. 拉取后重新安装依赖（如 package.json 有变动）

```bash
# macOS
cd /Users/xiaoshiqi/linscio/linscio_medcomm
npm install

# Windows 云服务器
cd C:\linscio_medcomm
npm install --ignore-scripts
node node_modules\electron\install.js
```

---

## 三、macOS 打包指令汇总

### 打包客户端（瘦包，不含 ComfyUI）

```bash
cd /Users/xiaoshiqi/linscio/linscio_medcomm

# 确保依赖已安装
npm install

# 构建 wheels（首次或 requirements.txt 变更后需要）
npm run prebuild:wheels

# 打包客户端（Apple Silicon）
bash scripts/build-mac.sh client

# 产物位置：releases/v{版本号}/LinScio-MedComm-{版本}-mac-arm64.dmg
```

### 打包 ComfyUI 组件包

```bash
cd /Users/xiaoshiqi/linscio/linscio_medcomm

# 打包 ComfyUI bundle（需要约 20GB 磁盘）
bash scripts/build-mac.sh comfyui-bundle

# 产物位置：releases/v{版本号}/comfyui-bundle-{版本}-mac-arm64.zip
# SHA256：  releases/v{版本号}/comfyui-bundle-{版本}-mac-arm64.zip.sha256
```

### 一次性全部打包

```bash
bash scripts/build-mac.sh all
```

---

## 四、Windows 打包指令汇总

### 方式 A：GitHub CI/CD 自动打包客户端

```bash
# 在 GitHub 仓库页面 → Actions → Build Windows Client → Run workflow
# 或使用 gh CLI：
gh workflow run "Build Windows Client"

# 产物：LinScio-MedComm-{版本}-win-x64.exe（NSIS 安装包）
```

### 方式 B：本机/云服务器打包客户端

```cmd
cd C:\linscio_medcomm

REM 首次：环境配置
scripts\setup-cloud-win.bat

REM 打包客户端（瘦包）
scripts\build-win.bat

REM 产物：releases\v{版本}\LinScio-MedComm-{版本}-win-x64.exe（NSIS 安装包）
```

### 云服务器打包 ComfyUI 组件包

```cmd
cd C:\linscio_medcomm

REM 打包 ComfyUI bundle（需要约 30GB 磁盘）
scripts\cloud-build-comfyui-win.bat

REM 产物: releases\v{版本}\comfyui-bundle-{版本}-win-x64.zip
```

---

## 五、COS 上传指令

### macOS 手动上传

```bash
# 安装 coscli（首次）
curl -sSL https://github.com/tencentyun/coscli/releases/download/v1.0.8/coscli-v1.0.8-darwin-arm64 -o /usr/local/bin/coscli
chmod +x /usr/local/bin/coscli

# 配置（首次）
coscli config set \
  --secret-id "你的SecretId" \
  --secret-key "你的SecretKey"

# ── 上传 macOS 客户端 ──
VER="0.1.1"
# .dmg 用于网站下载
coscli cp "releases/v${VER}/LinScio-MedComm-${VER}-mac-arm64.dmg" \
  "cos://你的桶名/releases/MedComm/v${VER}/"
# .zip 用于应用内静默更新
coscli cp "releases/v${VER}/LinScio-MedComm-${VER}-mac-arm64.zip" \
  "cos://你的桶名/releases/MedComm/v${VER}/"

# ── 上传 Windows 客户端（.exe NSIS 安装包，网站下载 + 应用内更新共用） ──
coscli cp "releases/v${VER}/LinScio-MedComm-${VER}-win-x64.exe" \
  "cos://你的桶名/releases/MedComm/v${VER}/"

# ── 上传 ComfyUI 组件包（.zip） ──
coscli cp "releases/v${VER}/comfyui-bundle-0.3.10-mac-arm64.zip" \
  "cos://你的桶名/bundles/MedComm/comfyui-basic/v0.3.10/"
coscli cp "releases/v${VER}/comfyui-bundle-0.3.10-mac-arm64.zip.sha256" \
  "cos://你的桶名/bundles/MedComm/comfyui-basic/v0.3.10/"
```

> **产物格式约定：** 客户端都是安装程序（macOS `.dmg`、Windows `.exe`），
> macOS 额外产出 `.zip` 仅供应用内静默更新使用。ComfyUI 组件包才是 `.zip`。

### CI 自动上传

在 GitHub 仓库 Settings → Secrets and variables → Actions 中配置：
- `TENCENT_COS_SECRET_ID`
- `TENCENT_COS_SECRET_KEY`
- `TENCENT_COS_BUCKET`
- `TENCENT_COS_REGION`

然后在 Variables 中设置 `ENABLE_COS_UPLOAD = true`。

---

## 六、版本号更新

打包前更新版本号：

```bash
cd /Users/xiaoshiqi/linscio/linscio_medcomm

# 查看当前版本
node -p "require('./package.json').version"

# 手动编辑 package.json 中的 version 字段
# 或使用 npm version（会自动 commit + tag）：
npm version patch   # 0.1.1 → 0.1.2
npm version minor   # 0.1.1 → 0.2.0
npm version major   # 0.1.1 → 1.0.0
```

---

## 七、常见问题

### Q: Electron 下载超时
```bash
# 确保 .npmrc 中配置了国内镜像
cat .npmrc
# 应包含：
# electron_mirror=https://npmmirror.com/mirrors/electron/
# electron_builder_binaries_mirror=https://npmmirror.com/mirrors/electron-builder-binaries/
```

### Q: pip 安装 PyTorch 超慢
```bash
# macOS
pip install -i https://pypi.tuna.tsinghua.edu.cn/simple torch torchvision torchaudio

# Windows (CPU)
pip install -i https://pypi.tuna.tsinghua.edu.cn/simple --find-links https://download.pytorch.org/whl/cpu torch torchvision torchaudio
```

### Q: GitHub push 被拒绝
```bash
# 先拉取合并
git pull origin main --rebase
git push origin main
```

### Q: build-mac.sh 权限不足
```bash
chmod +x scripts/build-mac.sh
```
