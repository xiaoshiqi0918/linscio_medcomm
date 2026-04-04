#!/usr/bin/env python3
"""开发环境启动后端"""
import os
import uvicorn

if __name__ == "__main__":
    # 与 Electron 开发模式一致：启用 DEBUG 后，本机回环可免 X-Local-Api-Key（便于纯浏览器 + Vite）
    if os.environ.get("DEBUG") is None:
        os.environ["DEBUG"] = "1"
    uvicorn.run(
        "app.main:app",
        host="127.0.0.1",
        port=8765,
        reload=True,
    )
