"""翻译 API — 选中文本英译中（支持 DeepL / Google / Azure / LLM 回退）"""
import os
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.api.v1.auth import get_current_user
from app.models.user import User

router = APIRouter()


class TranslateRequest(BaseModel):
    text: str
    target_lang: str = "zh"
    source_lang: str = "en"


class TranslateResponse(BaseModel):
    text: str
    provider: str
    fallback_reason: str | None = None


@router.post("", response_model=TranslateResponse)
async def translate_text(
    req: TranslateRequest,
    user: User = Depends(get_current_user),
):
    from app.services.translate.translator import translate
    from fastapi import HTTPException

    if not req.text.strip():
        return TranslateResponse(text="", provider="none")

    if len(req.text) > 15000:
        raise HTTPException(status_code=400, detail="文本过长，请缩短选区（上限 15000 字符）")

    try:
        result = await translate(
            text=req.text,
            target_lang=req.target_lang,
            source_lang=req.source_lang,
        )
        return TranslateResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"翻译失败: {e}")


@router.get("/status")
async def translate_status(user: User = Depends(get_current_user)):
    """返回当前可用的翻译提供商信息。"""
    providers = []
    if os.environ.get("DEEPL_API_KEY"):
        providers.append({"id": "deepl", "name": "DeepL", "available": True})
    if os.environ.get("GOOGLE_TRANSLATE_API_KEY"):
        providers.append({"id": "google", "name": "Google Translate", "available": True})
    if os.environ.get("AZURE_TRANSLATE_KEY"):
        providers.append({"id": "azure", "name": "Azure Translator", "available": True})
    providers.append({"id": "llm", "name": "默认大模型（回退）", "available": True})
    return {"providers": providers, "active": providers[0]["id"] if providers else "llm"}
