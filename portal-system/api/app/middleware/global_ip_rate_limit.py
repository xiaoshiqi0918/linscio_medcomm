"""
MedComm 全局 IP 限流：同 IP 每分钟超过 60 次请求返回 429
"""
import time
from collections import deque
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response, JSONResponse


_IP_REQUESTS: dict[str, deque[float]] = {}
_MAX_REQUESTS = 60
_WINDOW_SEC = 60
_EXEMPT_PATHS = {"/", "/health", "/docs", "/redoc", "/openapi.json"}


class GlobalIPRateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        path = request.scope.get("path", "")
        if any(path == p or path.startswith(p + "/") for p in _EXEMPT_PATHS):
            return await call_next(request)
        client_ip = request.client.host if request.client else "unknown"
        now = time.monotonic()
        if client_ip not in _IP_REQUESTS:
            _IP_REQUESTS[client_ip] = deque()
        q = _IP_REQUESTS[client_ip]
        while q and now - q[0] > _WINDOW_SEC:
            q.popleft()
        if len(q) >= _MAX_REQUESTS:
            return JSONResponse(
                status_code=429,
                content={"detail": "请求过于频繁，请稍后再试"},
            )
        q.append(now)
        return await call_next(request)
