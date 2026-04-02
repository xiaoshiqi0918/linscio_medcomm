# CI/CD 完整性检查

对照规范：GitHub Actions 三平台构建矩阵。

---

## 规范要求

- **平台**：macOS ARM64 / macOS x64 / Windows x64
- **Wheels**：pip download 按平台预下载，dry-run 校验
- **python-build-standalone**：锁定版本，按平台下载 install_only

---

## 当前实现

### `.github/workflows/build.yml`

| 项目 | 状态 |
|------|------|
| 三平台矩阵 | ✅ darwin-arm64, darwin-x64, win32-x64 |
| Pre-download wheels | ✅ 使用 matrix.pip_platform |
| python-build-standalone | ✅ 3.11.7 + 20240107（astral-sh 源） |
| electron-builder | ✅ 按平台传 --mac / --mac --x64 / --win |
| 触发 | push main|master, PR, release, 手动 |

### 版本说明

- 20240107 中 3.11 系列为 **3.11.7**（无 3.11.12），已按实际可用版本配置
- 仓库已迁至 astral-sh/python-build-standalone

### 本地 vs CI

- **本地**：`npm run electron:build` 自动执行 prebuild:python
- **CI**：手动 curl + tar 下载 Python，跳过 prebuild，使用 `electron-builder` 直接打包
