# Wheels 预置目录

CI 或本地构建前执行：

```bash
# 当前平台
npm run prebuild:wheels

# 指定平台
node scripts/build-wheels.js macos-arm64
node scripts/build-wheels.js macos-x64
node scripts/build-wheels.js win32-x64
node scripts/build-wheels.js linux-x64
```

产出至 `build/wheels/<platform>/`，首次启动时 first-run 会 `pip install --no-index --find-links=...`。
