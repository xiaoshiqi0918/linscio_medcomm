#!/usr/bin/env python3
"""开发环境启动后端"""
import os
import sys
from pathlib import Path

import uvicorn


def _fix_playwright_browsers_path() -> None:
    """开发模式下若 PLAYWRIGHT_BROWSERS_PATH 指向的目录里没有 chromium 可执行文件，
    就取消该环境变量，让 Playwright 回退到默认路径（macOS 默认在
    ~/Library/Caches/ms-playwright，Linux 在 ~/.cache/ms-playwright）。

    背景：在 Cursor 等沙盒环境中启动 npm run dev:saas 时，shell 的
    PLAYWRIGHT_BROWSERS_PATH 会被注入到一个空的沙盒缓存目录，导致海报 PDF
    导出抛 'Executable doesn't exist'。生产 / Electron 打包路径不会受影响。
    """
    pw_path = os.environ.get("PLAYWRIGHT_BROWSERS_PATH")
    if not pw_path:
        return
    base = Path(pw_path)
    has_chromium = False
    if base.is_dir():
        # Playwright 安装的 chromium 目录形如 chromium-{rev} 或 chromium_headless_shell-{rev}
        for child in base.iterdir():
            name = child.name.lower()
            if not (name.startswith("chromium-") or name.startswith("chromium_headless_shell-")):
                continue
            # 只要里面任意一个可执行文件存在就视为可用
            for exe in child.rglob("Chromium*"):
                if exe.is_file():
                    has_chromium = True
                    break
            if has_chromium:
                break
            for exe in child.rglob("chrome*"):
                if exe.is_file():
                    has_chromium = True
                    break
            if has_chromium:
                break
    if not has_chromium:
        os.environ.pop("PLAYWRIGHT_BROWSERS_PATH", None)
        sys.stderr.write(
            "[run.py] PLAYWRIGHT_BROWSERS_PATH=%s 中未发现 chromium，已重置为系统默认路径\n"
            % pw_path
        )


if __name__ == "__main__":
    _fix_playwright_browsers_path()
    # 与 Electron 开发模式一致：启用 DEBUG 后，本机回环可免 X-Local-Api-Key（便于纯浏览器 + Vite）
    if os.environ.get("DEBUG") is None:
        os.environ["DEBUG"] = "1"
    uvicorn.run(
        "app.main:app",
        host="127.0.0.1",
        port=8765,
        reload=True,
    )
