"""翻译 API — 选中文本英译中（支持 DeepL / Google / Azure / LLM 回退）"""
import os
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.auth import get_current_user
from app.core.database import AsyncSessionLocal
from app.models.user import User

router = APIRouter()


async def _get_db():
    async with AsyncSessionLocal() as session:
        yield session


class TranslateRequest(BaseModel):
    text: str
    target_lang: str = "zh"
    source_lang: str = "en"


class TranslateResponse(BaseModel):
    text: str
    provider: str
    fallback_reason: str | None = None
    cost: float = 0


@router.post("", response_model=TranslateResponse)
async def translate_text(
    req: TranslateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(_get_db),
):
    from app.services.translate.translator import translate

    if not req.text.strip():
        return TranslateResponse(text="", provider="none")

    if len(req.text) > 15000:
        raise HTTPException(status_code=400, detail="文本过长，请缩短选区（上限 15000 字符）")

    from app.core.config import is_saas
    billing_sid: str | None = None
    estimated_cost = None
    if is_saas():
        from app.services.billing.dependency import open_billing_session, close_billing_session
        from app.services.billing.service import estimate_cost_for_task
        from app.services.credit.service import InsufficientCreditsError
        estimated_cost = await estimate_cost_for_task("translation", input_chars=len(req.text))
        try:
            billing_sid = await open_billing_session(
                user.id, "translation", estimated_cost, db,
                business_ref={"input_chars": len(req.text), "target_lang": req.target_lang},
            )
            await db.commit()
        except InsufficientCreditsError as e:
            raise HTTPException(
                status_code=402,
                detail=f"积分不足：需要 {e.required} 积分，当前可用 {e.available} 积分",
            )

    try:
        result = await translate(
            text=req.text,
            target_lang=req.target_lang,
            source_lang=req.source_lang,
        )
    except Exception as e:
        if billing_sid and is_saas():
            from app.services.billing.dependency import close_billing_session
            await close_billing_session(billing_sid, db, success=False)
            await db.commit()
        raise HTTPException(status_code=502, detail=f"翻译失败: {e}")

    final_cost = estimated_cost or 0
    if billing_sid and is_saas():
        from app.services.credit.pricing import calc_translation_cost_final
        from app.services.billing.dependency import close_billing_session
        output_chars = len(result.get("text", ""))
        final_cost = calc_translation_cost_final(
            len(req.text), output_chars, estimated_cost=estimated_cost,
        )
        await close_billing_session(billing_sid, db, success=True, override_cost=final_cost)
        await db.commit()

    return TranslateResponse(**result, cost=float(final_cost) if final_cost else 0)


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
