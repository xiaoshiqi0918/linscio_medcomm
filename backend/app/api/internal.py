"""内部 API（如 token 刷新）"""
from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class TokenRefreshRequest(BaseModel):
    refresh_token: str | None = None


@router.post("/token/refresh")
async def refresh_token(req: TokenRefreshRequest | None = None):
    """刷新访问令牌（单用户模式：固定返回）"""
    return {
        "token": "local-single-user",
        "expires_in": 86400,
    }
