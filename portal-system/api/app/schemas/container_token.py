# 全栈方案 §3.1：container-token 请求/响应契约（snake_case）
from pydantic import BaseModel
from typing import Optional


class ContainerTokenRequest(BaseModel):
    username: str
    password: str
    machine_id: str


class ContainerTokenResponse(BaseModel):
    token: str
    plan: str
    modules: list[str]
    expires_at: str
    issued_at: str
    username: Optional[str] = None  # 门户用户名，桌面端可展示
    warning: Optional[str] = None
