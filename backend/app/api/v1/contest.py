"""参赛图文科普 API — 赛制包、画意范例、风格预设、提示词生成、负向词"""
import logging
import os
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func as sa_func
from pydantic import BaseModel

from app.core.database import AsyncSessionLocal
from app.models.contest import ContestPack, ContestRule, UserContestRule
from app.models.painting_intent import StylePreset, PaintingIntentExample, NegativeWordSet
from app.models.article_image_slot import ArticleImageSlot
from app.models.article import Article, ArticleSection

router = APIRouter()
logger = logging.getLogger(__name__)


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session


# ══════════════════════════════════════════════════════════════
#  Pydantic 请求/响应模型
# ══════════════════════════════════════════════════════════════

class ContestPackCreate(BaseModel):
    name: str
    organizer: str | None = None
    level: str | None = None
    source_url: str | None = None
    source_note: str | None = None
    word_limit: int | None = None
    word_count_includes: dict | None = None
    font: str | None = None
    file_format: str | None = None
    naming_template: str | None = None
    deadline: str | None = None
    ai_disclosure: str | None = None
    image_format: str | None = None
    layout_preference: str | None = None
    extra_rules: dict | None = None


class ContestPackUpdate(BaseModel):
    name: str | None = None
    organizer: str | None = None
    level: str | None = None
    source_url: str | None = None
    source_note: str | None = None
    is_active: bool | None = None
    word_limit: int | None = None
    word_count_includes: dict | None = None
    font: str | None = None
    file_format: str | None = None
    naming_template: str | None = None
    deadline: str | None = None
    ai_disclosure: str | None = None
    image_format: str | None = None
    layout_preference: str | None = None
    extra_rules: dict | None = None


class GeneratePromptRequest(BaseModel):
    intent_text: str
    style_preset_id: int | None = None
    aspect_ratio: str = "16:9"
    adjustments: dict | None = None
    topic_category: str | None = None
    preferred_provider: str | None = None
    target_language: str | None = None  # 'zh' / 'en' / 'both'


class SuggestIntentRequest(BaseModel):
    section_text: str
    topic: str | None = None
    section_type: str | None = None
    section_title: str | None = None
    prior_intents: list[str] | None = None


class EnrichIntentRequest(BaseModel):
    intent_text: str
    style_preset: str | None = None
    aspect_ratio: str = "16:9"
    section_text: str | None = None
    topic: str | None = None
    section_type: str | None = None


class ImageSlotCreate(BaseModel):
    section_id: int | None = None
    order_num: int = 1
    intent_text: str | None = None
    aspect_ratio: str | None = "16:9"
    style_preset_id: int | None = None


class ImageSlotUpdate(BaseModel):
    intent_text: str | None = None
    aspect_ratio: str | None = None
    style_preset_id: int | None = None
    prompt_zh: str | None = None
    prompt_en: str | None = None
    negative_words: str | None = None
    image_path: str | None = None
    image_status: str | None = None
    user_adjustments: dict | None = None


class BindContestRequest(BaseModel):
    contest_pack_id: int | None = None
    contest_rule_source: str | None = None
    contest_custom_rules: dict | None = None


class AiDeclarationUpdate(BaseModel):
    ai_declaration: dict


# ══════════════════════════════════════════════════════════════
#  辅助函数
# ══════════════════════════════════════════════════════════════

def _pack_to_dict(p: ContestPack) -> dict:
    return {
        "id": p.id,
        "name": p.name,
        "organizer": p.organizer,
        "level": p.level,
        "source_url": p.source_url,
        "source_note": p.source_note,
        "is_active": p.is_active,
        "word_limit": p.word_limit,
        "word_count_includes": p.word_count_includes,
        "font": p.font,
        "file_format": p.file_format,
        "naming_template": p.naming_template,
        "deadline": str(p.deadline) if p.deadline else None,
        "ai_disclosure": p.ai_disclosure,
        "image_format": p.image_format,
        "layout_preference": p.layout_preference,
        "extra_rules": p.extra_rules,
        "created_at": str(p.created_at) if p.created_at else None,
        "updated_at": str(p.updated_at) if p.updated_at else None,
    }


def _preset_to_dict(s: StylePreset) -> dict:
    return {
        "id": s.id,
        "name": s.name,
        "display_name": s.display_name,
        "description": s.description,
        "prompt_template_zh": s.prompt_template_zh,
        "prompt_template_en": s.prompt_template_en,
        "negative_words": s.negative_words,
        "quality_tags_zh": s.quality_tags_zh,
        "quality_tags_en": s.quality_tags_en,
        "medium_zh": s.medium_zh,
        "medium_en": s.medium_en,
        "default_composition": s.default_composition,
        "default_lighting": s.default_lighting,
        "default_color": s.default_color,
        "version": s.version,
    }


def _example_to_dict(e: PaintingIntentExample) -> dict:
    return {
        "id": e.id,
        "topic_category": e.topic_category,
        "style_preset_id": e.style_preset_id,
        "preset_version": e.preset_version,
        "intent_text": e.intent_text,
        "scene_description": e.scene_description,
    }


def _slot_to_dict(s: ArticleImageSlot) -> dict:
    return {
        "id": s.id,
        "article_id": s.article_id,
        "section_id": s.section_id,
        "order_num": s.order_num,
        "intent_text": s.intent_text,
        "aspect_ratio": s.aspect_ratio,
        "style_preset_id": s.style_preset_id,
        "prompt_zh": s.prompt_zh,
        "prompt_en": s.prompt_en,
        "negative_words": s.negative_words,
        "image_path": s.image_path,
        "image_status": s.image_status,
        "image_provider": s.image_provider,
        "user_adjustments": s.user_adjustments,
        "prompt_version": s.prompt_version,
        "style_preset_version": s.style_preset_version,
        "created_at": str(s.created_at) if s.created_at else None,
        "updated_at": str(s.updated_at) if s.updated_at else None,
    }


# ══════════════════════════════════════════════════════════════
#  赛制包 CRUD
# ══════════════════════════════════════════════════════════════

@router.get("/packs")
async def list_packs(
    q: str | None = None,
    level: str | None = None,
    is_active: bool = True,
    db: AsyncSession = Depends(get_db),
):
    stmt = select(ContestPack).where(ContestPack.is_active == is_active)
    if q:
        stmt = stmt.where(ContestPack.name.ilike(f"%{q}%"))
    if level:
        stmt = stmt.where(ContestPack.level == level)
    stmt = stmt.order_by(ContestPack.updated_at.desc())
    result = await db.execute(stmt)
    packs = result.scalars().all()
    return {"items": [_pack_to_dict(p) for p in packs]}


@router.get("/packs/{pack_id}")
async def get_pack(pack_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(ContestPack).where(ContestPack.id == pack_id))
    pack = result.scalar_one_or_none()
    if not pack:
        raise HTTPException(404, "赛制包不存在")

    rules_result = await db.execute(
        select(ContestRule).where(ContestRule.contest_pack_id == pack_id)
    )
    rules = rules_result.scalars().all()

    data = _pack_to_dict(pack)
    data["rules"] = [
        {"id": r.id, "rule_key": r.rule_key, "rule_value": r.rule_value,
         "source": r.source, "confidence": r.confidence}
        for r in rules
    ]
    return data


@router.post("/packs")
async def create_pack(req: ContestPackCreate, db: AsyncSession = Depends(get_db)):
    pack = ContestPack(**req.model_dump(exclude_none=True))
    db.add(pack)
    await db.commit()
    await db.refresh(pack)
    return _pack_to_dict(pack)


@router.put("/packs/{pack_id}")
async def update_pack(pack_id: int, req: ContestPackUpdate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(ContestPack).where(ContestPack.id == pack_id))
    pack = result.scalar_one_or_none()
    if not pack:
        raise HTTPException(404, "赛制包不存在")
    for k, v in req.model_dump(exclude_none=True).items():
        setattr(pack, k, v)
    await db.commit()
    await db.refresh(pack)
    return _pack_to_dict(pack)


# ══════════════════════════════════════════════════════════════
#  风格预设
# ══════════════════════════════════════════════════════════════

@router.get("/style-presets")
async def list_style_presets(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(StylePreset).where(StylePreset.is_active == True).order_by(StylePreset.id)
    )
    presets = result.scalars().all()
    return {"items": [_preset_to_dict(s) for s in presets]}


@router.get("/style-presets/{preset_id}")
async def get_style_preset(preset_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(StylePreset).where(StylePreset.id == preset_id))
    preset = result.scalar_one_or_none()
    if not preset:
        raise HTTPException(404, "风格预设不存在")
    return _preset_to_dict(preset)


# ══════════════════════════════════════════════════════════════
#  画意范例
# ══════════════════════════════════════════════════════════════

@router.get("/intent-examples")
async def list_intent_examples(
    topic: str | None = None,
    style_preset_id: int | None = None,
    db: AsyncSession = Depends(get_db),
):
    stmt = select(PaintingIntentExample).where(PaintingIntentExample.is_active == True)
    if topic:
        stmt = stmt.where(PaintingIntentExample.topic_category == topic)
    if style_preset_id:
        stmt = stmt.where(PaintingIntentExample.style_preset_id == style_preset_id)
    stmt = stmt.order_by(PaintingIntentExample.id)
    result = await db.execute(stmt)
    examples = result.scalars().all()
    return {"items": [_example_to_dict(e) for e in examples]}


@router.post("/intent-examples/suggest")
async def suggest_intent(req: SuggestIntentRequest, request: Request = None):
    """根据段落正文 AI 建议 2-3 条候选画意"""
    from app.core.config import is_saas
    billing_sid: str | None = None
    if is_saas() and request:
        from app.core.deps import get_current_user
        from app.services.billing.dependency import open_billing_session
        from app.services.credit.pricing import calc_contest_llm_cost
        from app.services.credit.service import InsufficientCreditsError
        async with AsyncSessionLocal() as db:
            user = await get_current_user(request, db)
            _cost = calc_contest_llm_cost("suggest_intent")
            try:
                billing_sid = await open_billing_session(
                    user.id, "contest_llm", _cost, db,
                    business_ref={"action": "suggest_intent"},
                )
                await db.commit()
            except InsufficientCreditsError as e:
                raise HTTPException(status_code=402, detail=str(e))

    from app.services.contest.prompt_engine import suggest_painting_intents
    try:
        suggestions = await suggest_painting_intents(
            section_text=req.section_text,
            topic=req.topic,
            section_type=req.section_type,
            section_title=req.section_title,
            prior_intents=req.prior_intents,
        )
    except Exception:
        if billing_sid and is_saas():
            async with AsyncSessionLocal() as sdb:
                from app.services.billing.dependency import close_billing_session
                await close_billing_session(billing_sid, sdb, success=False)
                await sdb.commit()
        raise

    if billing_sid and is_saas():
        async with AsyncSessionLocal() as sdb:
            from app.services.billing.dependency import close_billing_session
            await close_billing_session(billing_sid, sdb, success=True, override_cost=_cost)
            await sdb.commit()

    return {"suggestions": suggestions}


@router.post("/intent-examples/enrich")
async def enrich_intent(req: EnrichIntentRequest, request: Request = None):
    """AI 智能扩写：把简短画意扩写为剧本式场景描述（含 hints 与 preserved）。

    计费：0.3 积分（contest_llm.intent_enrich）。同输入 24h 内复用缓存，命中缓存不计费。
    """
    intent_text = (req.intent_text or "").strip()
    if not intent_text:
        raise HTTPException(status_code=400, detail="画意为空")
    if len(intent_text) < 4:
        raise HTTPException(status_code=400, detail="画意太短，无法扩写（至少 4 字）")

    from app.core.config import is_saas
    from app.services.contest.prompt_engine import enrich_intent_to_scene, _hash_intent_input, _cache_get
    from app.services.credit.pricing import calc_contest_llm_cost

    cost = calc_contest_llm_cost("intent_enrich")

    # 提前查缓存：命中则免费返回（不开 billing_session）
    cache_key = _hash_intent_input(
        intent_text, req.style_preset, req.aspect_ratio, (req.section_text or "")
    )
    cached = _cache_get(cache_key)
    if cached:
        result = dict(cached)
        result["from_cache"] = True
        result["original_intent"] = intent_text
        result["cost"] = 0.0
        return result

    billing_sid: str | None = None
    if is_saas() and request:
        from app.core.deps import get_current_user
        from app.services.billing.dependency import open_billing_session
        from app.services.credit.service import InsufficientCreditsError
        async with AsyncSessionLocal() as db:
            user = await get_current_user(request, db)
            try:
                billing_sid = await open_billing_session(
                    user.id, "contest_llm", cost, db,
                    business_ref={"action": "intent_enrich"},
                )
                await db.commit()
            except InsufficientCreditsError as e:
                raise HTTPException(status_code=402, detail=str(e))

    try:
        result = await enrich_intent_to_scene(
            intent_text,
            style_preset=req.style_preset,
            aspect_ratio=req.aspect_ratio,
            section_text=req.section_text or "",
            topic=req.topic or "",
            section_type=req.section_type or "",
        )
    except Exception:
        if billing_sid and is_saas():
            async with AsyncSessionLocal() as sdb:
                from app.services.billing.dependency import close_billing_session
                await close_billing_session(billing_sid, sdb, success=False)
                await sdb.commit()
        raise

    # rejected / error 都不扣分；ok 才扣
    if result.get("status") != "ok":
        if billing_sid and is_saas():
            async with AsyncSessionLocal() as sdb:
                from app.services.billing.dependency import close_billing_session
                await close_billing_session(billing_sid, sdb, success=False)
                await sdb.commit()
        result["cost"] = 0.0
        return result

    if billing_sid and is_saas():
        async with AsyncSessionLocal() as sdb:
            from app.services.billing.dependency import close_billing_session
            await close_billing_session(billing_sid, sdb, success=True, override_cost=cost)
            await sdb.commit()

    result["cost"] = float(cost)
    return result


# ══════════════════════════════════════════════════════════════
#  提示词生成
# ══════════════════════════════════════════════════════════════

@router.post("/generate-prompt")
async def generate_prompt(req: GeneratePromptRequest, request: Request = None, db: AsyncSession = Depends(get_db)):
    """从结构化输入生成中英双语提示词 + 合并负向词"""
    from app.core.config import is_saas
    billing_sid: str | None = None
    if is_saas() and request:
        from app.core.deps import get_current_user
        from app.services.billing.dependency import open_billing_session
        from app.services.credit.pricing import calc_contest_llm_cost
        from app.services.credit.service import InsufficientCreditsError
        user = await get_current_user(request, db)
        _cost = calc_contest_llm_cost("generate_prompt")
        try:
            billing_sid = await open_billing_session(
                user.id, "contest_llm", _cost, db,
                business_ref={"action": "generate_prompt"},
            )
            await db.commit()
        except InsufficientCreditsError as e:
            raise HTTPException(status_code=402, detail=str(e))

    from app.services.contest.prompt_engine import generate_dual_prompt

    preset = None
    if req.style_preset_id:
        result = await db.execute(
            select(StylePreset).where(StylePreset.id == req.style_preset_id)
        )
        preset = result.scalar_one_or_none()

    try:
        prompt_result = await generate_dual_prompt(
            intent_text=req.intent_text,
            preset=preset,
            aspect_ratio=req.aspect_ratio,
            adjustments=req.adjustments,
            topic_category=req.topic_category,
            db=db,
            preferred_provider=req.preferred_provider,
            target_language=req.target_language,
        )
    except Exception:
        if billing_sid and is_saas():
            from app.services.billing.dependency import close_billing_session
            await close_billing_session(billing_sid, db, success=False)
            await db.commit()
        raise

    if billing_sid and is_saas():
        from app.services.billing.dependency import close_billing_session
        await close_billing_session(billing_sid, db, success=True, override_cost=_cost)
        await db.commit()

    return prompt_result


# ══════════════════════════════════════════════════════════════
#  负向词
# ══════════════════════════════════════════════════════════════

@router.get("/negative-words")
async def get_negative_words(
    style_preset_id: int | None = None,
    topic: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """获取合并后的负向词（风格预设 + 领域 + 全局）"""
    from app.services.contest.prompt_engine import get_merged_negative_words
    words = await get_merged_negative_words(
        style_preset_id=style_preset_id,
        topic_category=topic,
        db=db,
    )
    return words


# ══════════════════════════════════════════════════════════════
#  选题分类
# ══════════════════════════════════════════════════════════════

TOPIC_CATEGORIES = [
    {"id": "hypertension", "name": "高血压管理"},
    {"id": "diabetes", "name": "糖尿病管理"},
    {"id": "child_vaccine", "name": "儿童疫苗与常见传染病"},
    {"id": "maternal_health", "name": "孕产期保健"},
    {"id": "mental_health", "name": "心理健康"},
    {"id": "cancer_screening", "name": "肿瘤早筛"},
    {"id": "first_aid", "name": "急救常识"},
    {"id": "medication_safety", "name": "用药安全"},
    {"id": "elderly_health", "name": "老年健康"},
    {"id": "oral_eye_health", "name": "口腔与眼健康"},
]


@router.get("/topics")
async def list_topics():
    return {"items": TOPIC_CATEGORIES}


# ══════════════════════════════════════════════════════════════
#  公告解析（轻量版）
# ══════════════════════════════════════════════════════════════

@router.post("/parse-announcement")
async def parse_announcement(
    file: UploadFile = File(...),
    request: Request = None,
    db: AsyncSession = Depends(get_db),
):
    """上传赛事公告文件，通过大模型抽取关键参数"""
    from app.core.config import is_saas
    billing_sid: str | None = None
    if is_saas() and request:
        from app.core.deps import get_current_user
        from app.services.billing.dependency import open_billing_session
        from app.services.credit.pricing import calc_contest_llm_cost
        from app.services.credit.service import InsufficientCreditsError
        user = await get_current_user(request, db)
        _cost = calc_contest_llm_cost("parse_announcement")
        try:
            billing_sid = await open_billing_session(
                user.id, "contest_llm", _cost, db,
                business_ref={"action": "parse_announcement"},
            )
            await db.commit()
        except InsufficientCreditsError as e:
            raise HTTPException(status_code=402, detail=str(e))

    from app.services.contest.announcement_parser import parse_contest_announcement

    content = await file.read()
    filename = file.filename or "announcement"

    try:
        result = await parse_contest_announcement(content, filename)
    except Exception:
        if billing_sid and is_saas():
            from app.services.billing.dependency import close_billing_session
            await close_billing_session(billing_sid, db, success=False)
            await db.commit()
        raise

    if billing_sid and is_saas():
        from app.services.billing.dependency import close_billing_session
        await close_billing_session(billing_sid, db, success=True, override_cost=_cost)
        await db.commit()

    return result


# ══════════════════════════════════════════════════════════════
#  文章赛制绑定
# ══════════════════════════════════════════════════════════════

@router.post("/articles/{article_id}/bind-contest")
async def bind_contest(
    article_id: int,
    req: BindContestRequest,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Article).where(Article.id == article_id))
    article = result.scalar_one_or_none()
    if not article:
        raise HTTPException(404, "文章不存在")

    if req.contest_pack_id is not None:
        article.contest_pack_id = req.contest_pack_id
    if req.contest_rule_source is not None:
        article.contest_rule_source = req.contest_rule_source
    if req.contest_custom_rules is not None:
        article.contest_custom_rules = req.contest_custom_rules

    await db.commit()
    return {"ok": True}


@router.patch("/articles/{article_id}/ai-declaration")
async def update_ai_declaration(
    article_id: int,
    req: AiDeclarationUpdate,
    request: Request = None,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Article).where(Article.id == article_id))
    article = result.scalar_one_or_none()
    if not article:
        raise HTTPException(404, "文章不存在")
    article.ai_declaration = req.ai_declaration
    await db.commit()

    try:
        from app.core.deps import get_current_user
        user = await get_current_user(request, db)
        if user:
            import json
            from app.models.user_setting import UserSetting
            existing = await db.execute(
                select(UserSetting)
                .where(UserSetting.user_id == user.id, UserSetting.key == "last_ai_declaration")
            )
            setting = existing.scalar_one_or_none()
            val = json.dumps(req.ai_declaration, ensure_ascii=False)
            if setting:
                setting.value = val
            else:
                db.add(UserSetting(user_id=user.id, key="last_ai_declaration", value=val))
            await db.commit()
    except Exception:
        pass

    return {"ok": True}


@router.get("/ai-declaration/last")
async def get_last_ai_declaration(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """获取用户上次使用的 AI 声明配置"""
    try:
        from app.core.deps import get_current_user
        user = await get_current_user(request, db)
        if not user:
            return {"ai_declaration": None}
        from app.models.user_setting import UserSetting
        result = await db.execute(
            select(UserSetting)
            .where(UserSetting.user_id == user.id, UserSetting.key == "last_ai_declaration")
        )
        setting = result.scalar_one_or_none()
        if setting:
            import json
            return {"ai_declaration": json.loads(setting.value)}
    except Exception:
        pass
    return {"ai_declaration": None}


# ══════════════════════════════════════════════════════════════
#  配图槽位 CRUD
# ══════════════════════════════════════════════════════════════

@router.get("/articles/{article_id}/image-slots")
async def list_image_slots(article_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(ArticleImageSlot)
        .where(ArticleImageSlot.article_id == article_id)
        .order_by(ArticleImageSlot.section_id, ArticleImageSlot.order_num)
    )
    slots = result.scalars().all()
    return {"items": [_slot_to_dict(s) for s in slots]}


@router.post("/articles/{article_id}/image-slots")
async def create_image_slot(
    article_id: int,
    req: ImageSlotCreate,
    db: AsyncSession = Depends(get_db),
):
    slot = ArticleImageSlot(
        article_id=article_id,
        section_id=req.section_id,
        order_num=req.order_num,
        intent_text=req.intent_text,
        aspect_ratio=req.aspect_ratio,
        style_preset_id=req.style_preset_id,
    )
    db.add(slot)
    await db.commit()
    await db.refresh(slot)
    return _slot_to_dict(slot)


@router.put("/image-slots/{slot_id}")
async def update_image_slot(
    slot_id: int,
    req: ImageSlotUpdate,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(ArticleImageSlot).where(ArticleImageSlot.id == slot_id))
    slot = result.scalar_one_or_none()
    if not slot:
        raise HTTPException(404, "配图槽位不存在")
    for k, v in req.model_dump(exclude_none=True).items():
        setattr(slot, k, v)
    await db.commit()
    await db.refresh(slot)
    return _slot_to_dict(slot)


@router.delete("/image-slots/{slot_id}")
async def delete_image_slot(
    slot_id: int,
    purge_history: bool = False,
    db: AsyncSession = Depends(get_db),
):
    """删除配图槽位。

    purge_history=True 时，同步清理 generated_images 表里同 (article_id, section_id)
    的历史重绘记录（仅删数据库索引，不动物理文件，避免误伤已被锚点引用的图）。
    """
    result = await db.execute(select(ArticleImageSlot).where(ArticleImageSlot.id == slot_id))
    slot = result.scalar_one_or_none()
    if not slot:
        raise HTTPException(404, "配图槽位不存在")

    article_id = slot.article_id
    section_id = slot.section_id

    purged = 0
    if purge_history and article_id is not None:
        from app.models.image import GeneratedImage
        from sqlalchemy import delete as sa_delete, and_
        cond = [GeneratedImage.article_id == article_id]
        if section_id is not None:
            cond.append(GeneratedImage.section_id == section_id)
        else:
            cond.append(GeneratedImage.section_id.is_(None))
        try:
            res = await db.execute(sa_delete(GeneratedImage).where(and_(*cond)))
            purged = res.rowcount or 0
        except Exception as e:
            logger.warning("purge generated_images failed: %s", e)

    await db.delete(slot)
    await db.commit()
    return {"ok": True, "purged_history": purged}


class GenerateSlotPromptRequest(BaseModel):
    # 用户当前选择的图像引擎（如 kling / jimeng / openai / midjourney / gpt_image …）。
    # 后端据此推断目标 prompt 语言、是否需要独立负向词；为空 → 走双语兼容模式。
    preferred_provider: str | None = None
    # 强制覆盖目标语言：'zh' / 'en' / 'both'。一般留空让后端按 provider 决定。
    target_language: str | None = None


@router.post("/image-slots/{slot_id}/generate-prompt")
async def generate_slot_prompt(
    slot_id: int,
    req: GenerateSlotPromptRequest | None = None,
    request: Request = None,
    db: AsyncSession = Depends(get_db),
):
    """为指定槽位生成/重新生成提示词（按 provider 选语言 + 智能负向词）"""
    result = await db.execute(select(ArticleImageSlot).where(ArticleImageSlot.id == slot_id))
    slot = result.scalar_one_or_none()
    if not slot:
        raise HTTPException(404, "配图槽位不存在")

    if not slot.intent_text:
        raise HTTPException(400, "请先填写画意")

    from app.core.config import is_saas
    billing_sid: str | None = None
    if is_saas() and request:
        from app.core.deps import get_current_user
        from app.services.billing.dependency import open_billing_session
        from app.services.credit.pricing import calc_contest_llm_cost
        from app.services.credit.service import InsufficientCreditsError
        user = await get_current_user(request, db)
        _cost = calc_contest_llm_cost("generate_prompt")
        try:
            billing_sid = await open_billing_session(
                user.id, "contest_llm", _cost, db,
                business_ref={"action": "slot_generate_prompt", "slot_id": slot_id},
            )
            await db.commit()
        except InsufficientCreditsError as e:
            raise HTTPException(status_code=402, detail=str(e))

    from app.services.contest.prompt_engine import generate_dual_prompt

    preset = None
    if slot.style_preset_id:
        pr = await db.execute(
            select(StylePreset).where(StylePreset.id == slot.style_preset_id)
        )
        preset = pr.scalar_one_or_none()

    art_result = await db.execute(select(Article).where(Article.id == slot.article_id))
    article = art_result.scalar_one_or_none()
    topic_category = article.specialty if article else None

    # ── 注入视觉锚点（角色卡 + 风格锁），保证全文图片一致性 ──
    from app.services.contest.visual_anchor import (
        get_or_create_anchor, inject_anchor_to_intent, has_meaningful_anchor,
    )
    anchor = await get_or_create_anchor(slot.article_id, db)
    if has_meaningful_anchor(anchor):
        intent_with_anchor = inject_anchor_to_intent(slot.intent_text, anchor)
    else:
        intent_with_anchor = slot.intent_text

    preferred_provider = (req.preferred_provider if req else None) or None
    target_language = (req.target_language if req else None) or None

    try:
        prompt_result = await generate_dual_prompt(
            intent_text=intent_with_anchor,
            preset=preset,
            aspect_ratio=slot.aspect_ratio or "16:9",
            adjustments=slot.user_adjustments,
            topic_category=topic_category,
            db=db,
            preferred_provider=preferred_provider,
            target_language=target_language,
        )
    except Exception:
        if billing_sid and is_saas():
            from app.services.billing.dependency import close_billing_session
            await close_billing_session(billing_sid, db, success=False)
            await db.commit()
        raise

    if billing_sid and is_saas():
        from app.services.billing.dependency import close_billing_session
        await close_billing_session(billing_sid, db, success=True, override_cost=_cost)
        await db.commit()

    slot.prompt_zh = prompt_result.get("prompt_zh", "")
    slot.prompt_en = prompt_result.get("prompt_en", "")
    slot.negative_words = prompt_result.get("negative_words_text", "")
    slot.image_status = "prompt_ready"
    slot.prompt_version = (slot.prompt_version or 0) + 1
    slot.style_preset_version = preset.version if preset else None
    await db.commit()
    await db.refresh(slot)

    return {
        "slot": _slot_to_dict(slot),
        "prompt_result": prompt_result,
    }


# ── 图像生成 ──────────────────────────────────────────────────

_ASPECT_TO_PIXELS = {
    "16:9":  (1792, 1024),
    "1:1":   (1024, 1024),
    "3:4":   (1024, 1792),
    # 小图（缩略图 / 装饰位用，部分海外 API 最低 1024，调用方可在 provider 侧自动放大）
    "small": (512, 512),
}


class GenerateSlotImageRequest(BaseModel):
    preferred_provider: str | None = None
    # "normal"（默认）/ "high"（故事板模式：i2i provider 启用最强角色保持档）
    consistency_strength: str | None = None


@router.post("/image-slots/{slot_id}/generate-image")
async def generate_slot_image(
    slot_id: int,
    req: GenerateSlotImageRequest | None = None,
    request: Request = None,
    db: AsyncSession = Depends(get_db),
):
    """调用 imagegen 引擎为槽位一键生成配图"""
    result = await db.execute(
        select(ArticleImageSlot).where(ArticleImageSlot.id == slot_id)
    )
    slot = result.scalar_one_or_none()
    if not slot:
        raise HTTPException(404, "配图槽位不存在")

    if not slot.prompt_en and not slot.prompt_zh:
        raise HTTPException(400, "请先生成提示词")

    from app.core.config import is_saas
    billing_sid: str | None = None
    if is_saas() and request:
        from app.core.deps import get_current_user
        from app.services.billing.dependency import open_billing_session
        from app.services.credit.pricing import calc_image_gen_cost
        from app.services.credit.service import InsufficientCreditsError
        user = await get_current_user(request, db)
        _cost = calc_image_gen_cost(1)
        try:
            billing_sid = await open_billing_session(
                user.id, "image_generation", _cost, db,
                business_ref={"action": "contest_slot_image", "slot_id": slot_id},
            )
            await db.commit()
        except InsufficientCreditsError as e:
            raise HTTPException(status_code=402, detail=str(e))

    from app.services.imagegen.engine import generate_image
    from app.services.contest.visual_anchor import (
        get_or_create_anchor, update_anchor_image_path,
    )

    negative = slot.negative_words or ""
    w, h = _ASPECT_TO_PIXELS.get(slot.aspect_ratio or "1:1", (1024, 1024))
    preferred = (req.preferred_provider if req else None) or None
    consistency = (
        (req.consistency_strength if req else None) or "normal"
    ).strip().lower()
    if consistency not in ("normal", "high"):
        consistency = "normal"

    # ── 视觉锚点：seed lock + reference image ──
    anchor = await get_or_create_anchor(slot.article_id, db)
    seed_to_use: int | None = anchor.base_seed if anchor and anchor.base_seed else None
    ref_image: str | None = (
        anchor.anchor_image_path
        if anchor
        and (anchor.anchor_source or "auto_first") != "disabled"
        and anchor.anchor_image_path
        else None
    )
    # 把相对路径转成 provider 可消费的形态：
    #   - 公网 SITE_URL：拼成 https://.../api/v1/imagegen/serve?path=...，让 provider 自己拉
    #   - dev / 私网 SITE_URL：直接读本地文件转 base64 data URI（Kling/Jimeng 都支持；MJ 不支持，会被 _midjourney 自动忽略）
    if ref_image and not ref_image.startswith(("http://", "https://", "data:")):
        from app.core.config import settings as _settings
        from urllib.parse import urlparse
        import ipaddress
        site_url = (
            getattr(_settings, "site_url", None)
            or getattr(_settings, "SITE_URL", None)
            or ""
        ).rstrip("/")

        def _is_public_site_url(u: str) -> bool:
            if not u:
                return False
            try:
                host = (urlparse(u).hostname or "").lower()
            except Exception:
                return False
            if not host:
                return False
            if host in {"localhost", "0.0.0.0"} or host.endswith((".local", ".lan", ".internal")):
                return False
            try:
                ip = ipaddress.ip_address(host)
                return not (ip.is_private or ip.is_loopback or ip.is_link_local)
            except ValueError:
                # 形如 medcomm.example.com 这类非 IP 域名一律视为公网
                return True

        if _is_public_site_url(site_url):
            ref_image = f"{site_url}/api/v1/imagegen/serve?path={ref_image}"
        else:
            # 本地 dev / 私网 → 转 data URI 让 provider 直接吃二进制
            try:
                from app.services.export.html_docx import image_to_data_uri
                data_uri = image_to_data_uri(ref_image)
                if data_uri:
                    ref_image = data_uri
                else:
                    logger.warning(
                        "锚点图无法转为 data URI（路径无效或读取失败）: %s", ref_image
                    )
                    ref_image = None
            except Exception as _e:
                logger.warning("锚点图转 base64 失败: %s", _e)
                ref_image = None

    # ── 选择最终送给图像引擎的 prompt ──
    # 优先使用经过【风格预设 + 视觉锚点】拼装的 prompt_en / prompt_zh：
    #   - 中文系 provider（即梦/可灵/文心/万相/Moonshot/GPT Image）优先用 prompt_zh
    #   - 海外系 provider（DALL-E/SD/FLUX/MJ/ComfyUI/SiliconFlow…）优先用 prompt_en
    #   - 双向 fallback：所选语言为空时退到另一语言；都没有再退到 intent_text
    from app.services.contest.prompt_engine import resolve_target_language
    _lang_pref = resolve_target_language(preferred)
    if _lang_pref == "zh":
        prompt = slot.prompt_zh or slot.prompt_en or (slot.intent_text or "").strip()
    else:
        # 'en' 与 'both' 都按"英文优先"，与历史行为一致
        prompt = slot.prompt_en or slot.prompt_zh or (slot.intent_text or "").strip()

    if slot.prompt_en or slot.prompt_zh:
        prompt_source = (
            f"prompt_{_lang_pref}(i2i with style)" if ref_image else f"prompt_{_lang_pref}(t2i with anchor)"
        )
    else:
        prompt_source = "intent_text(fallback, no prompt yet)"

    # 诊断日志：方便用户在终端确认锚点是否真的传给了生图引擎
    if ref_image:
        ref_kind = (
            "base64_data_uri" if ref_image.startswith("data:")
            else "url" if ref_image.startswith(("http://", "https://"))
            else "local_path"
        )
        logger.info(
            "[visual_anchor] slot=%s article=%s 应用锚点图 (kind=%s, seed=%s, provider=%s, consistency=%s, prompt=%s)",
            slot.id, slot.article_id, ref_kind, seed_to_use, preferred or "auto", consistency, prompt_source,
        )
    else:
        logger.info(
            "[visual_anchor] slot=%s article=%s 未应用锚点图 (anchor_source=%s, has_image=%s, prompt=%s)",
            slot.id, slot.article_id,
            (anchor.anchor_source if anchor else None),
            bool(anchor and anchor.anchor_image_path),
            prompt_source,
        )

    try:
        urls, is_fallback, meta = await generate_image(
            prompt=prompt,
            width=w,
            height=h,
            image_type="contest_illustration",
            preferred_provider=preferred,
            negative_prompt=negative,
            skip_style_envelope=True,
            seed=seed_to_use,
            reference_image=ref_image,
            consistency_strength=consistency,
        )
    except Exception as exc:
        if billing_sid and is_saas():
            from app.services.billing.dependency import close_billing_session
            await close_billing_session(billing_sid, db, success=False)
            await db.commit()
        raise HTTPException(502, f"图像生成失败: {exc}")

    if not urls:
        if billing_sid and is_saas():
            from app.services.billing.dependency import close_billing_session
            await close_billing_session(billing_sid, db, success=False)
            await db.commit()
        raise HTTPException(502, "所有图像引擎均未返回结果，请稍后重试")

    if billing_sid and is_saas():
        from app.services.billing.dependency import close_billing_session
        await close_billing_session(billing_sid, db, success=True, override_cost=_cost)
        await db.commit()

    image_uri = urls[0]
    rel_path = image_uri.replace("medcomm-image://", "") if image_uri.startswith("medcomm-image://") else image_uri

    slot.image_path = rel_path
    slot.image_status = "ai_generated"
    slot.image_provider = meta.get("provider")
    await db.commit()
    await db.refresh(slot)

    # 首图生效后自动设为锚点图（仅当 anchor_source=auto_first 且当前为空）
    try:
        await update_anchor_image_path(slot.article_id, rel_path, db, only_if_empty=True)
    except Exception as _e:
        logger.warning("update anchor image failed: %s", _e)

    return {
        "slot": _slot_to_dict(slot),
        "provider": meta.get("provider"),
        "is_fallback": is_fallback,
    }


@router.get("/image-providers")
async def get_image_providers():
    """检测当前可用的图像生成引擎"""
    from app.services.imagegen.engine import detect_providers
    providers = await detect_providers()
    any_available = any(
        v for k, v in providers.items()
        if k not in ("comfyui_local_running",)
    )
    return {"providers": providers, "any_available": any_available}


# ══════════════════════════════════════════════════════════════
#  视觉锚点（角色卡 + 风格锁 + Seed）
# ══════════════════════════════════════════════════════════════


class VisualAnchorExtractFromImageRequest(BaseModel):
    """vision 抽取角色锚点请求体。

    image_path 可选：
      - 不传：自动取 anchor.anchor_image_path 或文章首张已生成的图
      - 传：使用指定图片（一般来自前端"全章配图概览"中用户选定的图）
    merge_mode：
      - replace（默认）：直接覆盖现有角色
      - append：在现有角色后追加（按 role 去重，总数 ≤ 5）
    """
    image_path: str | None = None
    merge_mode: str | None = "replace"


class VisualAnchorUpdateRequest(BaseModel):
    characters: list[dict] | None = None
    style_lock: dict | None = None
    base_seed: int | None = None
    anchor_source: str | None = None  # auto_first / manual_pick / disabled
    anchor_image_path: str | None = None


@router.get("/articles/{article_id}/visual-anchor")
async def get_visual_anchor(article_id: int, db: AsyncSession = Depends(get_db)):
    """获取文章的视觉锚点配置（不存在时自动创建空记录）。"""
    art = (
        await db.execute(select(Article).where(Article.id == article_id))
    ).scalar_one_or_none()
    if not art:
        raise HTTPException(404, "文章不存在")

    from app.services.contest.visual_anchor import (
        get_or_create_anchor, anchor_to_dict,
    )
    anchor = await get_or_create_anchor(article_id, db)
    return anchor_to_dict(anchor)


@router.post("/articles/{article_id}/visual-anchor/extract")
async def extract_visual_anchor(
    article_id: int,
    request: Request = None,
    db: AsyncSession = Depends(get_db),
):
    """AI 抽取角色卡 + 风格基调（计费 0.6 积分，1h 缓存内同文章不重复扣）。"""
    art = (
        await db.execute(select(Article).where(Article.id == article_id))
    ).scalar_one_or_none()
    if not art:
        raise HTTPException(404, "文章不存在")

    from app.core.config import is_saas
    from app.services.contest.visual_anchor import (
        extract_visual_anchor_for_article,
        get_or_create_anchor,
        anchor_to_dict,
    )
    from app.services.credit.pricing import calc_contest_llm_cost

    cost = calc_contest_llm_cost("visual_anchor_extract")

    # 先确保 anchor 记录存在
    anchor = await get_or_create_anchor(article_id, db)

    billing_sid: str | None = None
    if is_saas() and request:
        from app.core.deps import get_current_user
        from app.services.billing.dependency import open_billing_session
        from app.services.credit.service import InsufficientCreditsError
        user = await get_current_user(request, db)
        try:
            billing_sid = await open_billing_session(
                user.id, "contest_llm", cost, db,
                business_ref={"action": "visual_anchor_extract", "article_id": article_id},
            )
            await db.commit()
        except InsufficientCreditsError as e:
            raise HTTPException(status_code=402, detail=str(e))

    try:
        result = await extract_visual_anchor_for_article(article_id, db, force=False)
    except Exception:
        if billing_sid and is_saas():
            from app.services.billing.dependency import close_billing_session
            await close_billing_session(billing_sid, db, success=False)
            await db.commit()
        raise

    if result.get("status") != "ok":
        if billing_sid and is_saas():
            from app.services.billing.dependency import close_billing_session
            await close_billing_session(billing_sid, db, success=False)
            await db.commit()
        return {**result, "anchor": anchor_to_dict(anchor), "cost": 0.0}

    # 命中缓存：免费返回
    if result.get("from_cache"):
        if billing_sid and is_saas():
            from app.services.billing.dependency import close_billing_session
            await close_billing_session(billing_sid, db, success=False)
            await db.commit()
        anchor.characters = result.get("characters") or anchor.characters
        anchor.style_lock = result.get("style_lock") or anchor.style_lock
        anchor.last_modified_by = "ai"
        from datetime import datetime as _dt
        anchor.auto_extracted_at = _dt.utcnow()
        await db.commit()
        await db.refresh(anchor)
        return {
            **result,
            "anchor": anchor_to_dict(anchor),
            "cost": 0.0,
        }

    # 写库
    anchor.characters = result.get("characters") or []
    anchor.style_lock = result.get("style_lock") or {}
    anchor.last_modified_by = "ai"
    from datetime import datetime as _dt
    anchor.auto_extracted_at = _dt.utcnow()
    await db.commit()
    await db.refresh(anchor)

    if billing_sid and is_saas():
        from app.services.billing.dependency import close_billing_session
        await close_billing_session(billing_sid, db, success=True, override_cost=cost)
        await db.commit()

    return {
        **result,
        "anchor": anchor_to_dict(anchor),
        "cost": float(cost),
    }


@router.post("/articles/{article_id}/visual-anchor/extract-from-image")
async def extract_visual_anchor_from_image_api(
    article_id: int,
    req: VisualAnchorExtractFromImageRequest = None,
    request: Request = None,
    db: AsyncSession = Depends(get_db),
):
    """用 GPT-4o vision 从已生成图片识别角色 + 风格（计费 0.6 积分）。

    适用场景：
      - 文章字数太少、文本抽取效果不理想
      - 用户对首图非常满意，想让"图说了算"，让其它配图复刻这位主角
      - 多角色图：识别 1~5 个角色作为统一锚点
    """
    art = (
        await db.execute(select(Article).where(Article.id == article_id))
    ).scalar_one_or_none()
    if not art:
        raise HTTPException(404, "文章不存在")

    body = req or VisualAnchorExtractFromImageRequest()
    merge_mode = (body.merge_mode or "replace").lower()
    if merge_mode not in ("replace", "append"):
        merge_mode = "replace"

    from app.core.config import is_saas
    from app.services.contest.visual_anchor import (
        extract_visual_anchor_from_image,
        get_or_create_anchor,
        anchor_to_dict,
        merge_characters,
    )
    from app.services.credit.pricing import calc_contest_llm_cost

    cost = calc_contest_llm_cost("visual_anchor_extract")

    anchor = await get_or_create_anchor(article_id, db)

    billing_sid: str | None = None
    if is_saas() and request:
        from app.core.deps import get_current_user
        from app.services.billing.dependency import open_billing_session
        from app.services.credit.service import InsufficientCreditsError
        user = await get_current_user(request, db)
        try:
            billing_sid = await open_billing_session(
                user.id, "contest_llm", cost, db,
                business_ref={
                    "action": "visual_anchor_extract_vision",
                    "article_id": article_id,
                    "merge_mode": merge_mode,
                },
            )
            await db.commit()
        except InsufficientCreditsError as e:
            raise HTTPException(status_code=402, detail=str(e))

    try:
        result = await extract_visual_anchor_from_image(
            article_id, db, image_path=body.image_path
        )
    except Exception:
        if billing_sid and is_saas():
            from app.services.billing.dependency import close_billing_session
            await close_billing_session(billing_sid, db, success=False)
            await db.commit()
        raise

    if result.get("status") != "ok":
        if billing_sid and is_saas():
            from app.services.billing.dependency import close_billing_session
            await close_billing_session(billing_sid, db, success=False)
            await db.commit()
        return {**result, "anchor": anchor_to_dict(anchor), "cost": 0.0}

    # 合并 / 覆盖角色卡
    merged_chars = merge_characters(
        anchor.characters or [], result.get("characters") or [], mode=merge_mode
    )
    anchor.characters = merged_chars

    # 风格锁：append 模式下仅在原值为空时填入；replace 模式下整体覆盖
    new_style = result.get("style_lock") or {}
    if merge_mode == "replace":
        anchor.style_lock = new_style
    else:
        cur = anchor.style_lock or {}
        anchor.style_lock = {
            "color_palette": cur.get("color_palette") or new_style.get("color_palette", ""),
            "lighting": cur.get("lighting") or new_style.get("lighting", ""),
            "art_style_extra": cur.get("art_style_extra") or new_style.get("art_style_extra", ""),
        }

    anchor.last_modified_by = "ai_vision"
    from datetime import datetime as _dt
    anchor.auto_extracted_at = _dt.utcnow()
    await db.commit()
    await db.refresh(anchor)

    if billing_sid and is_saas():
        from app.services.billing.dependency import close_billing_session
        await close_billing_session(billing_sid, db, success=True, override_cost=cost)
        await db.commit()

    return {
        **result,
        "characters": merged_chars,
        "anchor": anchor_to_dict(anchor),
        "cost": float(cost),
        "merge_mode": merge_mode,
    }


@router.put("/articles/{article_id}/visual-anchor")
async def update_visual_anchor(
    article_id: int,
    req: VisualAnchorUpdateRequest,
    db: AsyncSession = Depends(get_db),
):
    """用户手动编辑视觉锚点。"""
    art = (
        await db.execute(select(Article).where(Article.id == article_id))
    ).scalar_one_or_none()
    if not art:
        raise HTTPException(404, "文章不存在")

    from app.services.contest.visual_anchor import (
        get_or_create_anchor, anchor_to_dict,
    )
    anchor = await get_or_create_anchor(article_id, db)

    if req.characters is not None:
        cleaned: list[dict] = []
        for idx, ch in enumerate((req.characters or [])[:5]):
            if not isinstance(ch, dict):
                continue
            cid = str(ch.get("id") or chr(ord("A") + idx))[:4]
            role = str(ch.get("role") or "").strip()[:30]
            desc = str(ch.get("description") or "").strip()[:300]
            try:
                imp = int(ch.get("importance") or (5 - idx))
            except Exception:
                imp = 5 - idx
            imp = max(1, min(5, imp))
            if not role or not desc:
                continue
            cleaned.append({"id": cid, "role": role, "description": desc, "importance": imp})
        anchor.characters = cleaned

    if req.style_lock is not None:
        sl = req.style_lock or {}
        cleaned_style = {
            "color_palette": str(sl.get("color_palette", "")).strip()[:80],
            "lighting": str(sl.get("lighting", "")).strip()[:80],
            "art_style_extra": str(sl.get("art_style_extra", "")).strip()[:120],
        }
        # 三个 value 都为空 → 直接存空 dict，避免 {"key":"","key":"","key":""}
        # 这种"假空"残留导致 is_configured 永远判为 True。
        if not any(cleaned_style.values()):
            anchor.style_lock = {}
        else:
            anchor.style_lock = cleaned_style

    if req.base_seed is not None:
        try:
            seed_val = int(req.base_seed)
            if seed_val <= 0:
                seed_val = 1
            anchor.base_seed = min(seed_val, 2_147_483_647)
        except Exception:
            pass

    if req.anchor_source is not None:
        if req.anchor_source in ("auto_first", "manual_pick", "manual_upload", "disabled"):
            anchor.anchor_source = req.anchor_source

    if req.anchor_image_path is not None:
        # 允许显式置空（清除锚点图）
        anchor.anchor_image_path = req.anchor_image_path or None

    anchor.last_modified_by = "user"
    await db.commit()
    await db.refresh(anchor)
    return anchor_to_dict(anchor)


@router.get("/articles/{article_id}/export-confirmation")
async def get_export_confirmation(
    article_id: int,
    db: AsyncSession = Depends(get_db),
):
    """导出前获取赛制确认信息（含 AI 声明默认值和赛制包确认提示）"""
    result = await db.execute(select(Article).where(Article.id == article_id))
    article = result.scalar_one_or_none()
    if not article:
        raise HTTPException(404, "文章不存在")

    from app.services.export.contest_export import get_confirmation_message

    pack = None
    if article.contest_pack_id:
        pack_result = await db.execute(
            select(ContestPack).where(ContestPack.id == article.contest_pack_id)
        )
        pack = pack_result.scalar_one_or_none()

    confirmation_msg = get_confirmation_message(article, pack)

    ai_disclosure_default = "none"
    if pack:
        ai_disclosure_default = pack.ai_disclosure or "none"
    elif article.contest_custom_rules and isinstance(article.contest_custom_rules, dict):
        ai_disclosure_default = article.contest_custom_rules.get("ai_disclosure", "none")

    return {
        "confirmation_message": confirmation_msg,
        "ai_disclosure_requirement": ai_disclosure_default,
        "current_ai_declaration": article.ai_declaration,
        "contest_pack_name": pack.name if pack else None,
        "naming_template": (pack.naming_template if pack else None)
            or (article.contest_custom_rules or {}).get("naming_template"),
    }


@router.post("/image-slots/{slot_id}/upload")
async def upload_slot_image(
    slot_id: int,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    """上传配图到指定槽位。

    保存路径与 AI 生成保持一致：相对路径 ``images/YYYY/MM/contest_xxx.ext``，
    便于前端 ``/api/v1/imagegen/serve?path=...`` 直接访问。
    历史版本曾把绝对路径写入 image_path，会导致 serve_image 返回 404，
    现已统一为相对路径。
    """
    result = await db.execute(select(ArticleImageSlot).where(ArticleImageSlot.id == slot_id))
    slot = result.scalar_one_or_none()
    if not slot:
        raise HTTPException(404, "配图槽位不存在")

    from app.core.config import settings
    from datetime import datetime
    from pathlib import Path
    import uuid

    raw_ext = os.path.splitext(file.filename or "img.jpg")[1].lower()
    if raw_ext not in (".jpg", ".jpeg", ".png", ".webp"):
        raw_ext = ".jpg"

    now = datetime.utcnow()
    rel_dir = Path("images") / f"{now.year}" / f"{now.month:02d}"
    abs_dir = Path(settings.app_data_root) / rel_dir
    abs_dir.mkdir(parents=True, exist_ok=True)

    filename = f"contest_{slot.article_id}_{slot_id}_{uuid.uuid4().hex[:8]}{raw_ext}"
    rel_path = (rel_dir / filename).as_posix()
    abs_path = abs_dir / filename

    content = await file.read()
    abs_path.write_bytes(content)

    slot.image_path = rel_path
    slot.image_status = "uploaded"
    slot.image_provider = "manual_upload"
    await db.commit()
    await db.refresh(slot)
    return _slot_to_dict(slot)


# ══════════════════════════════════════════════════════════════
#  我的赛制（用户级保存/复用）
# ══════════════════════════════════════════════════════════════

class SaveMyRulesRequest(BaseModel):
    name: str
    rules: dict
    source: str = "manual"  # parsed / manual


class ContributePublicRequest(BaseModel):
    user_rule_id: int


class ReportMissingContestRequest(BaseModel):
    contest_name: str
    description: str | None = None


@router.get("/my-rules")
async def list_my_rules(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """列出当前用户保存的「我的赛制」"""
    try:
        from app.core.deps import get_current_user
        user = await get_current_user(request, db)
        if not user:
            return {"items": []}
    except Exception:
        return {"items": []}
    result = await db.execute(
        select(UserContestRule)
        .where(UserContestRule.user_id == user.id, UserContestRule.is_active == True)
        .order_by(UserContestRule.updated_at.desc())
    )
    items = result.scalars().all()
    return {"items": [
        {
            "id": r.id, "name": r.name, "rules": r.rules,
            "source": r.source, "submitted_as_public": r.submitted_as_public,
            "created_at": str(r.created_at) if r.created_at else None,
            "updated_at": str(r.updated_at) if r.updated_at else None,
        }
        for r in items
    ]}


@router.post("/my-rules")
async def save_my_rules(
    req: SaveMyRulesRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """保存为「我的赛制」"""
    from app.core.deps import get_current_user
    user = await get_current_user(request, db)
    if not user:
        raise HTTPException(401, "请先登录")
    rule = UserContestRule(
        user_id=user.id,
        name=req.name,
        rules=req.rules,
        source=req.source,
    )
    db.add(rule)
    await db.commit()
    await db.refresh(rule)
    return {"id": rule.id, "name": rule.name, "ok": True}


@router.delete("/my-rules/{rule_id}")
async def delete_my_rule(
    rule_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    from app.core.deps import get_current_user
    user = await get_current_user(request, db)
    if not user:
        raise HTTPException(401, "请先登录")
    result = await db.execute(
        select(UserContestRule)
        .where(UserContestRule.id == rule_id, UserContestRule.user_id == user.id)
    )
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(404, "未找到该赛制配置")
    rule.is_active = False
    await db.commit()
    return {"ok": True}


@router.post("/my-rules/contribute")
async def contribute_as_public(
    req: ContributePublicRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """申请贡献为公共赛制包（运营审核）"""
    from app.core.deps import get_current_user
    user = await get_current_user(request, db)
    if not user:
        raise HTTPException(401, "请先登录")
    result = await db.execute(
        select(UserContestRule)
        .where(UserContestRule.id == req.user_rule_id, UserContestRule.user_id == user.id)
    )
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(404, "未找到该赛制配置")
    rule.submitted_as_public = True
    await db.commit()
    return {"ok": True, "message": "已提交，运营审核后将加入公共赛制包"}


@router.post("/report-missing")
async def report_missing_contest(
    req: ReportMissingContestRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """用户反馈：我没找到我的赛事"""
    from app.core.deps import get_current_user
    user = await get_current_user(request, db)
    user_id = user.id if user else None
    from app.models.user_setting import UserSetting
    import json
    feedback = UserSetting(
        user_id=user_id or 0,
        key="missing_contest_report",
        value=json.dumps({
            "contest_name": req.contest_name,
            "description": req.description,
        }, ensure_ascii=False),
    )
    db.add(feedback)
    await db.commit()
    return {"ok": True, "message": "感谢反馈！我们将尽快收录该赛事"}


# ══════════════════════════════════════════════════════════════
#  运营后台 CRUD — 风格预设
# ══════════════════════════════════════════════════════════════

class StylePresetCreate(BaseModel):
    name: str
    display_name: str
    description: str | None = None
    prompt_template_zh: dict | None = None
    prompt_template_en: dict | None = None
    negative_words: dict | None = None
    quality_tags_zh: str | None = None
    quality_tags_en: str | None = None
    medium_zh: str | None = None
    medium_en: str | None = None


class StylePresetUpdate(BaseModel):
    display_name: str | None = None
    description: str | None = None
    prompt_template_zh: dict | None = None
    prompt_template_en: dict | None = None
    negative_words: dict | None = None
    quality_tags_zh: str | None = None
    quality_tags_en: str | None = None
    medium_zh: str | None = None
    medium_en: str | None = None
    is_active: bool | None = None


@router.post("/admin/style-presets")
async def admin_create_style_preset(req: StylePresetCreate, db: AsyncSession = Depends(get_db)):
    preset = StylePreset(**req.model_dump(exclude_none=True))
    db.add(preset)
    await db.commit()
    await db.refresh(preset)
    return _preset_to_dict(preset)


@router.put("/admin/style-presets/{preset_id}")
async def admin_update_style_preset(preset_id: int, req: StylePresetUpdate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(StylePreset).where(StylePreset.id == preset_id))
    preset = result.scalar_one_or_none()
    if not preset:
        raise HTTPException(404, "风格预设不存在")
    for k, v in req.model_dump(exclude_none=True).items():
        setattr(preset, k, v)
    preset.version = (preset.version or 1) + 1
    await db.commit()
    await db.refresh(preset)
    return _preset_to_dict(preset)


@router.delete("/admin/style-presets/{preset_id}")
async def admin_delete_style_preset(preset_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(StylePreset).where(StylePreset.id == preset_id))
    preset = result.scalar_one_or_none()
    if not preset:
        raise HTTPException(404, "风格预设不存在")
    preset.is_active = False
    await db.commit()
    return {"ok": True}


# ══════════════════════════════════════════════════════════════
#  运营后台 CRUD — 负向词库
# ══════════════════════════════════════════════════════════════

def _neg_to_dict(n: NegativeWordSet) -> dict:
    return {
        "id": n.id,
        "category": n.category,
        "scope": n.scope,
        "topic_category": n.topic_category,
        "words_zh": n.words_zh,
        "words_en": n.words_en,
        "is_active": n.is_active,
    }


class NegativeWordSetCreate(BaseModel):
    category: str
    scope: str = "global"
    topic_category: str | None = None
    words_zh: list[str] | None = None
    words_en: list[str] | None = None


class NegativeWordSetUpdate(BaseModel):
    words_zh: list[str] | None = None
    words_en: list[str] | None = None
    is_active: bool | None = None


@router.get("/admin/negative-words")
async def admin_list_negative_words(
    scope: str | None = None,
    category: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    stmt = select(NegativeWordSet).order_by(NegativeWordSet.scope, NegativeWordSet.category)
    if scope:
        stmt = stmt.where(NegativeWordSet.scope == scope)
    if category:
        stmt = stmt.where(NegativeWordSet.category == category)
    result = await db.execute(stmt)
    items = result.scalars().all()
    return {"items": [_neg_to_dict(n) for n in items]}


@router.post("/admin/negative-words")
async def admin_create_negative_words(req: NegativeWordSetCreate, db: AsyncSession = Depends(get_db)):
    nws = NegativeWordSet(**req.model_dump(exclude_none=True))
    db.add(nws)
    await db.commit()
    await db.refresh(nws)
    return _neg_to_dict(nws)


@router.put("/admin/negative-words/{nws_id}")
async def admin_update_negative_words(nws_id: int, req: NegativeWordSetUpdate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(NegativeWordSet).where(NegativeWordSet.id == nws_id))
    nws = result.scalar_one_or_none()
    if not nws:
        raise HTTPException(404, "负向词条目不存在")
    for k, v in req.model_dump(exclude_none=True).items():
        setattr(nws, k, v)
    await db.commit()
    await db.refresh(nws)
    return _neg_to_dict(nws)


@router.delete("/admin/negative-words/{nws_id}")
async def admin_delete_negative_words(nws_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(NegativeWordSet).where(NegativeWordSet.id == nws_id))
    nws = result.scalar_one_or_none()
    if not nws:
        raise HTTPException(404, "负向词条目不存在")
    nws.is_active = False
    await db.commit()
    return {"ok": True}


# ══════════════════════════════════════════════════════════════
#  运营后台 CRUD — 画意范例
# ══════════════════════════════════════════════════════════════

class IntentExampleCreate(BaseModel):
    topic_category: str
    style_preset_id: int | None = None
    intent_text: str
    scene_description: str | None = None


class IntentExampleUpdate(BaseModel):
    topic_category: str | None = None
    style_preset_id: int | None = None
    intent_text: str | None = None
    scene_description: str | None = None
    is_active: bool | None = None


@router.post("/admin/intent-examples")
async def admin_create_intent_example(req: IntentExampleCreate, db: AsyncSession = Depends(get_db)):
    data = req.model_dump(exclude_none=True)
    if data.get("style_preset_id") and "preset_version" not in data:
        preset = await db.get(StylePreset, data["style_preset_id"])
        if preset:
            data["preset_version"] = preset.version or 1
    example = PaintingIntentExample(**data)
    db.add(example)
    await db.commit()
    await db.refresh(example)
    return _example_to_dict(example)


@router.put("/admin/intent-examples/{example_id}")
async def admin_update_intent_example(example_id: int, req: IntentExampleUpdate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(PaintingIntentExample).where(PaintingIntentExample.id == example_id))
    example = result.scalar_one_or_none()
    if not example:
        raise HTTPException(404, "画意范例不存在")
    for k, v in req.model_dump(exclude_none=True).items():
        setattr(example, k, v)
    await db.commit()
    await db.refresh(example)
    return _example_to_dict(example)


@router.delete("/admin/intent-examples/{example_id}")
async def admin_delete_intent_example(example_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(PaintingIntentExample).where(PaintingIntentExample.id == example_id))
    example = result.scalar_one_or_none()
    if not example:
        raise HTTPException(404, "画意范例不存在")
    example.is_active = False
    await db.commit()
    return {"ok": True}
