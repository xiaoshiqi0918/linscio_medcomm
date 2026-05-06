"""图像生成 API"""
import asyncio
import uuid
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import select

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.models.image_prompt_template import ImagePromptTemplate
from app.models.image import GeneratedImage
from app.models.article import Article, ArticleSection, ArticleContent
from app.services.imagegen.engine import detect_providers
from app.services.imagegen.prompt_builder import ai_generate_image_prompts
from app.workflow.graphs.image_graph import run_image_gen_graph

router = APIRouter()


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session

# 内存任务存储：task_id -> { status, images, error, provider_fallback, _cancelled }
_tasks: dict[str, dict] = {}


async def _load_article_series_fields(article_id: int) -> tuple[str, int | None]:
    """读取文章级图示连贯文案与系列种子基准（ComfyUI 等有效）。"""
    async with AsyncSessionLocal() as db:
        r = await db.execute(
            select(Article.visual_continuity_prompt, Article.image_series_seed_base).where(
                Article.id == article_id,
                Article.deleted_at.is_(None),
            )
        )
        row = r.one_or_none()
        if not row:
            return "", None
        v, s = row[0], row[1]
        return ((v or "").strip(), s)


def _resolve_continuity_and_seed(
    *,
    visual_continuity_prompt: str | None,
    seed_base: int | None,
    db_visual: str,
    db_seed: int | None,
) -> tuple[str, int | None]:
    if visual_continuity_prompt is None:
        v = (db_visual or "").strip()
    else:
        v = (visual_continuity_prompt or "").strip()
    sb = db_seed if seed_base is None else seed_base
    return v, sb


class GenerateRequest(BaseModel):
    """prompt 为场景描述；user_positive_prompt 非空时跳过自动构建"""
    prompt: str = ""
    user_positive_prompt: str | None = None
    user_negative_prompt: str | None = None
    style: str = "medical_illustration"
    width: int = 1024
    height: int = 1024
    batch_count: int = 1
    seed: int | None = None
    steps: int | None = None
    cfg_scale: float | None = None
    sampler_name: str | None = None
    content_format: str = "article"
    image_type: str | None = None
    specialty: str = ""
    target_audience: str = "public"
    preferred_provider: str | None = None
    siliconflow_image_model: str | None = None
    comfy_workflow_path: str | None = None
    comfy_mode: str | None = None
    comfy_base_url: str | None = None
    comfy_prompt_node_id: str | None = None
    comfy_prompt_input_key: str | None = None
    comfy_negative_node_id: str | None = None
    comfy_negative_input_key: str | None = None
    comfy_ksampler_node_id: str | None = None
    article_id: int | None = None
    visual_continuity_prompt: str | None = None
    seed_base: int | None = None
    panel_index: int | None = None
    loras: list[list] | None = None


class CreateTaskRequest(BaseModel):
    prompt: str = ""
    user_positive_prompt: str | None = None
    user_negative_prompt: str | None = None
    style: str = "medical_illustration"
    width: int = 1024
    height: int = 1024
    batch_count: int = 1
    seed: int | None = None
    steps: int | None = None
    cfg_scale: float | None = None
    sampler_name: str | None = None
    content_format: str = "article"
    image_type: str | None = None
    specialty: str = ""
    target_audience: str = "public"
    preferred_provider: str | None = None
    siliconflow_image_model: str | None = None
    comfy_workflow_path: str | None = None
    comfy_mode: str | None = None
    comfy_base_url: str | None = None
    comfy_prompt_node_id: str | None = None
    comfy_prompt_input_key: str | None = None
    comfy_negative_node_id: str | None = None
    comfy_negative_input_key: str | None = None
    comfy_ksampler_node_id: str | None = None
    article_id: int | None = None
    visual_continuity_prompt: str | None = None
    seed_base: int | None = None
    panel_index: int | None = None


class AiImagePromptsRequest(BaseModel):
    scene_idea: str
    style: str = "medical_illustration"
    image_type: str = "anatomy"
    target_audience: str = "public"
    content_format: str = "article"
    provider: str = "api"


def _graph_payload_from_task_kwargs(
    *,
    prompt: str,
    style: str,
    width: int,
    height: int,
    content_format: str = "article",
    image_type: str | None = None,
    user_positive_prompt: str | None = None,
    user_negative_prompt: str | None = None,
    batch_count: int = 1,
    seed: int | None = None,
    steps: int | None = None,
    cfg_scale: float | None = None,
    sampler_name: str | None = None,
    specialty: str = "",
    target_audience: str = "public",
    preferred_provider: str | None = None,
    siliconflow_image_model: str | None = None,
    comfy_workflow_path: str | None = None,
    comfy_mode: str | None = None,
    comfy_base_url: str | None = None,
    comfy_prompt_node_id: str | None = None,
    comfy_prompt_input_key: str | None = None,
    comfy_negative_node_id: str | None = None,
    comfy_negative_input_key: str | None = None,
    comfy_ksampler_node_id: str | None = None,
    visual_continuity_prompt: str = "",
    seed_base: int | None = None,
    panel_index: int | None = None,
    article_id: int | None = None,
    loras: list | None = None,
) -> dict:
    return {
        "scene_desc": prompt,
        "user_positive_prompt": user_positive_prompt or "",
        "user_negative_prompt": user_negative_prompt or "",
        "style": style,
        "width": width,
        "height": height,
        "batch_count": batch_count,
        "seed": seed,
        "steps": steps,
        "cfg_scale": cfg_scale,
        "sampler_name": sampler_name or "",
        "content_format": content_format,
        "image_type": image_type,
        "specialty": specialty or "",
        "target_audience": target_audience or "public",
        "preferred_provider": preferred_provider,
        "siliconflow_image_model": siliconflow_image_model,
        "comfy_workflow_path": comfy_workflow_path,
        "comfy_mode": comfy_mode,
        "comfy_base_url": comfy_base_url,
        "comfy_prompt_node_id": comfy_prompt_node_id,
        "comfy_prompt_input_key": comfy_prompt_input_key,
        "comfy_negative_node_id": comfy_negative_node_id,
        "comfy_negative_input_key": comfy_negative_input_key,
        "comfy_ksampler_node_id": comfy_ksampler_node_id,
        "visual_continuity_prompt": visual_continuity_prompt or "",
        "seed_base": seed_base,
        "panel_index": panel_index,
        "article_id": article_id,
        "loras": loras,
    }


async def _run_task(task_id: str, *, _billing_sid: str | None = None, _billing_cost=None, **kwargs) -> None:
    """走图像生成图：build_med_prompt → safety_check → generate → postprocess → save"""
    success = False
    try:
        if _tasks.get(task_id, {}).get("_cancelled"):
            _tasks[task_id]["status"] = "cancelled"
            return
        state = await run_image_gen_graph(_graph_payload_from_task_kwargs(**kwargs))
        if _tasks.get(task_id, {}).get("_cancelled"):
            _tasks[task_id]["status"] = "cancelled"
            return
        urls = state.get("urls") or []
        err = state.get("error")
        if err:
            _tasks[task_id]["status"] = "failed"
            _tasks[task_id]["error"] = err
        else:
            success = True
            _tasks[task_id]["status"] = "done"
            _tasks[task_id]["images"] = [{"path": u} for u in urls]
            meta = state.get("gen_meta") or {}
            _tasks[task_id]["provider"] = meta.get("provider")
            _tasks[task_id]["provider_fallback"] = meta.get("provider_fallback") if state.get("is_fallback") else None
            _tasks[task_id]["seeds"] = state.get("used_seeds") or []
    except Exception as e:
        if task_id in _tasks and not _tasks[task_id].get("_cancelled"):
            _tasks[task_id]["status"] = "failed"
            _tasks[task_id]["error"] = str(e)
    finally:
        if _billing_sid:
            try:
                from app.services.billing.dependency import close_billing_session
                async with AsyncSessionLocal() as sdb:
                    await close_billing_session(
                        _billing_sid, sdb, success=success,
                        override_cost=_billing_cost if success else None,
                    )
                    await sdb.commit()
            except Exception:
                pass


@router.get("/prompt-templates")
async def list_prompt_templates(
    content_format: str | None = Query(None),
    style: str | None = Query(None),
    db=Depends(get_db),
):
    """图像提示词模板列表，支持按形式/风格过滤"""
    q = select(ImagePromptTemplate).where(ImagePromptTemplate.is_active == True)
    if content_format:
        q = q.where(ImagePromptTemplate.content_format == content_format)
    if style:
        q = q.where(ImagePromptTemplate.style == style)
    q = q.order_by(ImagePromptTemplate.content_format, ImagePromptTemplate.style)
    result = await db.execute(q)
    items = result.scalars().all()
    return {
        "items": [
            {
                "id": t.id,
                "name": t.name,
                "content_format": t.content_format,
                "style": t.style,
                "prompt_template": t.prompt_template,
                "description": t.description,
            }
            for t in items
        ]
    }


@router.get("/image-types")
async def get_image_types():
    """图像类型与风格配置，供前端 FormatPicker / 条漫配图等使用"""
    from app.services.imagegen.image_types import (
        IMAGE_TYPES,
        IMAGE_STYLES,
        FORMAT_DEFAULT_IMAGE_TYPE,
        FORMAT_DEFAULT_STYLE,
    )
    return {
        "image_types": [{"id": t[0], "name": t[1], "formats": t[2]} for t in IMAGE_TYPES],
        "image_styles": [{"id": k, "name": v} for k, v in IMAGE_STYLES.items()],
        "format_default_image_type": FORMAT_DEFAULT_IMAGE_TYPE,
        "format_default_style": FORMAT_DEFAULT_STYLE,
    }


@router.get("/providers")
async def get_providers():
    """检测可用 Provider"""
    return await detect_providers()


@router.get("/serve")
async def serve_image(path: str):
    """供前端访问 medcomm-image 图片（web 模式）"""
    if ".." in path or path.startswith("/"):
        raise HTTPException(404)
    full = Path(settings.app_data_root) / path
    if not full.exists():
        raise HTTPException(404)
    return FileResponse(full)


@router.post("/tasks")
async def create_task(req: CreateTaskRequest, request: Request = None):
    """创建图像生成任务，支持 content_format/image_type（条漫 style=comic, image_type=comic_panel）"""
    from app.core.config import is_saas
    billing_sid: str | None = None
    _cost = None
    if is_saas() and request:
        from app.core.deps import get_current_user_or_default
        from app.services.billing.dependency import open_billing_session
        from app.services.credit.pricing import calc_image_gen_cost
        from app.services.credit.service import InsufficientCreditsError
        async with AsyncSessionLocal() as db:
            user = await get_current_user_or_default(request, db)
            _cost = calc_image_gen_cost(req.batch_count)
            try:
                billing_sid = await open_billing_session(
                    user.id, "image_generation", _cost, db,
                    business_ref={"batch_count": req.batch_count},
                )
                await db.commit()
            except InsufficientCreditsError as e:
                raise HTTPException(status_code=402, detail=str(e))

    task_id = str(uuid.uuid4())
    _tasks[task_id] = {
        "status": "pending",
        "images": [],
        "error": None,
        "provider_fallback": None,
        "seeds": [],
        "_cancelled": False,
    }
    db_v, db_s = "", None
    if req.article_id:
        db_v, db_s = await _load_article_series_fields(req.article_id)
    vc, sb = _resolve_continuity_and_seed(
        visual_continuity_prompt=req.visual_continuity_prompt,
        seed_base=req.seed_base,
        db_visual=db_v,
        db_seed=db_s,
    )
    asyncio.create_task(_run_task(
        task_id,
        _billing_sid=billing_sid,
        _billing_cost=_cost,
        prompt=req.prompt,
        style=req.style,
        width=req.width,
        height=req.height,
        content_format=req.content_format,
        image_type=req.image_type,
        user_positive_prompt=req.user_positive_prompt,
        user_negative_prompt=req.user_negative_prompt,
        batch_count=req.batch_count,
        seed=req.seed,
        steps=req.steps,
        cfg_scale=req.cfg_scale,
        sampler_name=req.sampler_name,
        specialty=req.specialty,
        target_audience=req.target_audience,
        preferred_provider=req.preferred_provider,
        siliconflow_image_model=req.siliconflow_image_model,
        comfy_workflow_path=req.comfy_workflow_path,
        comfy_mode=req.comfy_mode,
        comfy_base_url=req.comfy_base_url,
        comfy_prompt_node_id=req.comfy_prompt_node_id,
        comfy_prompt_input_key=req.comfy_prompt_input_key,
        comfy_negative_node_id=req.comfy_negative_node_id,
        comfy_negative_input_key=req.comfy_negative_input_key,
        comfy_ksampler_node_id=req.comfy_ksampler_node_id,
        visual_continuity_prompt=vc,
        seed_base=sb,
        panel_index=req.panel_index,
        article_id=req.article_id,
    ))
    return {"task_id": task_id}


@router.get("/tasks/{task_id}")
async def get_task_status(task_id: str):
    """查询任务状态"""
    if task_id not in _tasks:
        raise HTTPException(404, detail="Task not found")
    t = _tasks[task_id].copy()
    t.pop("_cancelled", None)
    return t


@router.delete("/tasks/{task_id}")
async def cancel_task(task_id: str):
    """取消图像生成任务"""
    if task_id not in _tasks:
        raise HTTPException(404, detail="Task not found")
    _tasks[task_id]["_cancelled"] = True
    if _tasks[task_id]["status"] == "pending":
        _tasks[task_id]["status"] = "cancelled"
    return {"ok": True}


@router.post("/generate")
async def post_generate(req: GenerateRequest, request: Request = None):
    """生成图像（走图像生成图：prompt 增强 + safety_check + 生成 + 保存）"""
    from app.core.config import is_saas
    billing_sid: str | None = None
    if is_saas() and request:
        from app.core.deps import get_current_user_or_default
        from app.services.billing.dependency import open_billing_session, close_billing_session
        from app.services.credit.pricing import calc_image_gen_cost
        from app.services.credit.service import InsufficientCreditsError
        async with AsyncSessionLocal() as db:
            user = await get_current_user_or_default(request, db)
            _cost = calc_image_gen_cost(req.batch_count)
            try:
                billing_sid = await open_billing_session(
                    user.id, "image_generation", _cost, db,
                    business_ref={"batch_count": req.batch_count},
                )
                await db.commit()
            except InsufficientCreditsError as e:
                raise HTTPException(status_code=402, detail=str(e))

    db_v, db_s = "", None
    if req.article_id:
        db_v, db_s = await _load_article_series_fields(req.article_id)
    vc, sb = _resolve_continuity_and_seed(
        visual_continuity_prompt=req.visual_continuity_prompt,
        seed_base=req.seed_base,
        db_visual=db_v,
        db_seed=db_s,
    )
    try:
        state = await run_image_gen_graph(
            _graph_payload_from_task_kwargs(
                prompt=req.prompt,
                style=req.style,
                width=req.width,
                height=req.height,
                content_format=req.content_format,
                image_type=req.image_type,
                user_positive_prompt=req.user_positive_prompt,
                user_negative_prompt=req.user_negative_prompt,
                batch_count=req.batch_count,
                seed=req.seed,
                steps=req.steps,
                cfg_scale=req.cfg_scale,
                sampler_name=req.sampler_name,
                specialty=req.specialty,
                target_audience=req.target_audience,
                preferred_provider=req.preferred_provider,
                siliconflow_image_model=req.siliconflow_image_model,
                comfy_workflow_path=req.comfy_workflow_path,
                comfy_mode=req.comfy_mode,
                comfy_base_url=req.comfy_base_url,
                comfy_prompt_node_id=req.comfy_prompt_node_id,
                comfy_prompt_input_key=req.comfy_prompt_input_key,
                comfy_negative_node_id=req.comfy_negative_node_id,
                comfy_negative_input_key=req.comfy_negative_input_key,
                comfy_ksampler_node_id=req.comfy_ksampler_node_id,
                visual_continuity_prompt=vc,
                seed_base=sb,
                panel_index=req.panel_index,
                article_id=req.article_id,
                loras=req.loras,
            )
        )
    except Exception:
        if billing_sid and is_saas():
            async with AsyncSessionLocal() as sdb:
                from app.services.billing.dependency import close_billing_session
                await close_billing_session(billing_sid, sdb, success=False)
                await sdb.commit()
        raise

    success = not state.get("error")
    if billing_sid and is_saas():
        async with AsyncSessionLocal() as sdb:
            from app.services.billing.dependency import close_billing_session
            await close_billing_session(billing_sid, sdb, success=success,
                                        override_cost=_cost if success else None)
            await sdb.commit()

    if state.get("error"):
        raise HTTPException(status_code=400, detail=state["error"])
    meta = state.get("gen_meta") or {}
    return {
        "urls": state.get("urls", []),
        "is_fallback": state.get("is_fallback", False),
        "provider": meta.get("provider"),
        "provider_fallback": meta.get("provider_fallback"),
        "seeds": state.get("used_seeds") or [],
    }


@router.post("/ai-prompts")
async def post_ai_image_prompts(req: AiImagePromptsRequest, request: Request = None):
    """AI 生成正/负向提示词（每次覆盖，由前端写入输入框）"""
    from app.core.config import is_saas
    billing_sid: str | None = None
    if is_saas() and request:
        from app.core.deps import get_current_user_or_default
        from app.services.billing.dependency import open_billing_session, close_billing_session
        from app.services.credit.pricing import calc_imagegen_prompt_cost
        from app.services.credit.service import InsufficientCreditsError
        async with AsyncSessionLocal() as db:
            user = await get_current_user_or_default(request, db)
            _cost = calc_imagegen_prompt_cost()
            try:
                billing_sid = await open_billing_session(
                    user.id, "imagegen_prompt", _cost, db,
                    business_ref={"action": "ai_prompts"},
                )
                await db.commit()
            except InsufficientCreditsError as e:
                raise HTTPException(status_code=402, detail=str(e))

    try:
        pos, neg, used_template_fallback = await ai_generate_image_prompts(
            scene_idea=req.scene_idea,
            style=req.style,
            image_type=req.image_type,
            target_audience=req.target_audience,
            content_format=req.content_format,
            provider=req.provider,
        )
    except Exception:
        if billing_sid and is_saas():
            async with AsyncSessionLocal() as sdb:
                from app.services.billing.dependency import close_billing_session
                await close_billing_session(billing_sid, sdb, success=False)
                await sdb.commit()
        raise

    success = bool(pos)
    if billing_sid and is_saas():
        async with AsyncSessionLocal() as sdb:
            from app.services.billing.dependency import close_billing_session
            await close_billing_session(billing_sid, sdb, success=success,
                                        override_cost=_cost if success else None)
            await sdb.commit()

    if not pos:
        raise HTTPException(status_code=502, detail="AI 提示词生成失败，请重试或手写提示词")
    return {
        "positive": pos,
        "negative": neg,
        "used_template_fallback": used_template_fallback,
    }


@router.get("/templates")
async def list_templates(
    content_format: str | None = Query(None),
    style: str | None = Query(None),
    db=Depends(get_db),
):
    """规范别名：/templates 指向 prompt-templates"""
    return await list_prompt_templates(content_format, style, db)


@router.get("/images")
async def list_images(
    article_id: int | None = Query(None),
    section_id: int | None = Query(None),
    db=Depends(get_db),
):
    """已生成图像列表"""
    q = select(GeneratedImage).order_by(GeneratedImage.created_at.desc())
    if article_id is not None:
        q = q.where(GeneratedImage.article_id == article_id)
    if section_id is not None:
        q = q.where(GeneratedImage.section_id == section_id)
    result = await db.execute(q)
    items = result.scalars().all()
    return {
        "items": [
            {
                "id": g.id,
                "file_path": g.file_path,
                "article_id": g.article_id,
                "section_id": g.section_id,
                "image_type": g.image_type,
                "style": g.style,
                "created_at": g.created_at.isoformat() if g.created_at else None,
            }
            for g in items
        ]
    }


@router.get("/images/{image_id}")
async def get_image(image_id: int, db=Depends(get_db)):
    """获取单张图像详情"""
    result = await db.execute(select(GeneratedImage).where(GeneratedImage.id == image_id))
    g = result.scalar_one_or_none()
    if not g:
        raise HTTPException(404, detail="Image not found")
    return {
        "id": g.id,
        "file_path": g.file_path,
        "article_id": g.article_id,
        "section_id": g.section_id,
        "content_format": g.content_format,
        "panel_index": g.panel_index,
        "image_type": g.image_type,
        "style": g.style,
        "prompt": g.prompt,
        "provider": g.provider,
        "created_at": g.created_at.isoformat() if g.created_at else None,
    }


@router.delete("/images/{image_id}")
async def delete_image(image_id: int, db=Depends(get_db)):
    """删除生成图像记录（不删物理文件，可扩展清理）"""
    result = await db.execute(select(GeneratedImage).where(GeneratedImage.id == image_id))
    g = result.scalar_one_or_none()
    if not g:
        raise HTTPException(404, detail="Image not found")
    await db.delete(g)
    await db.commit()
    return {"ok": True}


class AttachImageRequest(BaseModel):
    article_id: int
    section_id: int | None = None


@router.post("/images/{image_id}/attach")
async def attach_image(image_id: int, req: AttachImageRequest, db=Depends(get_db)):
    """将图像关联到文章/章节"""
    result = await db.execute(select(GeneratedImage).where(GeneratedImage.id == image_id))
    g = result.scalar_one_or_none()
    if not g:
        raise HTTPException(404, detail="Image not found")
    g.article_id = req.article_id
    g.section_id = req.section_id
    await db.commit()
    return {"ok": True}


class ComicPanelItem(BaseModel):
    panel_index: int
    scene_desc: str
    dialogue: str | None = None


class ComicBatchRequest(BaseModel):
    article_id: int
    panels: list[ComicPanelItem]
    style: str = "comic"
    seed_base: int | None = None
    preferred_provider: str | None = None
    comfy_workflow_path: str | None = None
    comfy_mode: str | None = None
    comfy_base_url: str | None = None
    comfy_prompt_node_id: str | None = None
    comfy_prompt_input_key: str | None = None
    comfy_negative_node_id: str | None = None
    comfy_negative_input_key: str | None = None
    comfy_ksampler_node_id: str | None = None


@router.post("/comic/batch")
async def comic_batch(req: ComicBatchRequest, request: Request = None, db=Depends(get_db)):
    """条漫批量生成：多格一次提交；继承文章级连贯文案与系列种子基准"""
    from app.core.config import is_saas
    panel_billing: list[tuple[str | None, object]] = []
    if is_saas() and request:
        from app.core.deps import get_current_user_or_default
        from app.services.billing.dependency import open_billing_session
        from app.services.credit.pricing import calc_image_gen_cost
        from app.services.credit.service import InsufficientCreditsError
        total_cost = calc_image_gen_cost(len(req.panels))
        async with AsyncSessionLocal() as bdb:
            user = await get_current_user_or_default(request, bdb)
            for _pi in range(len(req.panels)):
                _pc = calc_image_gen_cost(1)
                try:
                    _psid = await open_billing_session(
                        user.id, "image_generation", _pc, bdb,
                        business_ref={"action": "comic_panel", "panel": _pi},
                    )
                    panel_billing.append((_psid, _pc))
                except InsufficientCreditsError as e:
                    for _prev_sid, _ in panel_billing:
                        if _prev_sid:
                            from app.services.billing.dependency import close_billing_session
                            await close_billing_session(_prev_sid, bdb, success=False)
                    await bdb.commit()
                    raise HTTPException(status_code=402, detail=str(e))
            await bdb.commit()
    else:
        panel_billing = [(None, None)] * len(req.panels)

    tasks_created = []
    db_v, db_s = await _load_article_series_fields(req.article_id)
    vc, sb = _resolve_continuity_and_seed(
        visual_continuity_prompt=None,
        seed_base=req.seed_base,
        db_visual=db_v,
        db_seed=db_s,
    )
    for i, p in enumerate(req.panels):
        task_id = str(uuid.uuid4())
        _tasks[task_id] = {
            "status": "pending",
            "images": [],
            "error": None,
            "provider_fallback": None,
            "seeds": [],
            "_cancelled": False,
        }
        panel_off = i
        if p.panel_index is not None:
            try:
                panel_off = max(0, int(p.panel_index) - 1)
            except (TypeError, ValueError):
                panel_off = i
        _b_sid, _b_cost = panel_billing[i]
        asyncio.create_task(_run_task(
            task_id,
            _billing_sid=_b_sid,
            _billing_cost=_b_cost,
            prompt=f"{p.scene_desc}\n{p.dialogue or ''}".strip(),
            style=req.style,
            width=1024,
            height=1024,
            content_format="comic_strip",
            image_type="comic_panel",
            visual_continuity_prompt=vc,
            seed_base=sb,
            panel_index=panel_off,
            article_id=req.article_id,
            preferred_provider=req.preferred_provider,
            comfy_workflow_path=req.comfy_workflow_path,
            comfy_mode=req.comfy_mode,
            comfy_base_url=req.comfy_base_url,
            comfy_prompt_node_id=req.comfy_prompt_node_id,
            comfy_prompt_input_key=req.comfy_prompt_input_key,
            comfy_negative_node_id=req.comfy_negative_node_id,
            comfy_negative_input_key=req.comfy_negative_input_key,
            comfy_ksampler_node_id=req.comfy_ksampler_node_id,
        ))
        tasks_created.append({"task_id": task_id, "panel_index": p.panel_index})
    return {"tasks": tasks_created}


import re as _re

_TYPE_KEYWORDS: list[tuple[str, list[str]]] = [
    ("anatomy", ["解剖", "结构", "器官", "组织", "细胞", "骨骼", "肌肉", "神经", "血管", "心脏", "肺", "肝", "肾"]),
    ("pathology", ["病理", "病变", "损伤", "炎症", "感染", "肿瘤", "癌", "坏死", "纤维化", "硬化"]),
    ("flowchart", ["步骤", "流程", "阶段", "过程", "方法", "操作", "首先", "然后", "最后", "检查流程"]),
    ("comparison", ["对比", "比较", "区别", "不同", "差异", "VS", "正常.*异常", "健康.*疾病"]),
    ("infographic", ["数据", "统计", "比例", "百分", "%", "发病率", "死亡率", "研究表明", "调查"]),
    ("symptom", ["症状", "表现", "疼痛", "不适", "发热", "咳嗽", "头晕", "乏力"]),
    ("prevention", ["预防", "防护", "注意", "建议", "饮食", "运动", "生活方式", "习惯"]),
]

_REASON_MAP = {
    "anatomy": "包含解剖结构描述，配图有助于理解",
    "pathology": "涉及病理机制，图示更直观",
    "flowchart": "描述流程/步骤，适合用流程图展示",
    "comparison": "包含对比内容，图表更清晰",
    "infographic": "含数据/统计信息，适合可视化",
    "symptom": "描述症状表现，配图辅助识别",
    "prevention": "提供预防建议，图示增强记忆",
}

# 医学中文关键词 → 英文词汇映射，用于本地生成英文绘图提示词
_ZH_EN_MEDICAL: list[tuple[str, str]] = [
    ("心脏", "heart"), ("肺", "lungs"), ("肝", "liver"), ("肾", "kidney"),
    ("脑", "brain"), ("胃", "stomach"), ("肠", "intestine"), ("骨", "bone"),
    ("血管", "blood vessel"), ("神经", "nerve"), ("肌肉", "muscle"),
    ("细胞", "cell"), ("DNA", "DNA"), ("蛋白质", "protein"),
    ("肿瘤", "tumor"), ("癌", "cancer"), ("炎症", "inflammation"),
    ("感染", "infection"), ("病毒", "virus"), ("细菌", "bacteria"),
    ("手术", "surgery"), ("治疗", "treatment"), ("诊断", "diagnosis"),
    ("药物", "medication"), ("注射", "injection"), ("检查", "examination"),
    ("症状", "symptom"), ("疼痛", "pain"), ("发热", "fever"),
    ("糖尿病", "diabetes"), ("高血压", "hypertension"), ("冠心病", "coronary heart disease"),
    ("中风", "stroke"), ("哮喘", "asthma"), ("关节炎", "arthritis"),
    ("免疫", "immune"), ("抗体", "antibody"), ("疫苗", "vaccine"),
    ("预防", "prevention"), ("康复", "rehabilitation"), ("护理", "nursing care"),
    ("饮食", "diet"), ("运动", "exercise"), ("睡眠", "sleep"),
    ("儿童", "children"), ("老年", "elderly"), ("孕妇", "pregnant women"),
    ("患者", "patient"), ("医生", "doctor"), ("护士", "nurse"),
]

_TYPE_EN_SCENE = {
    "anatomy": "detailed anatomical diagram, labeled cross-section view, medical textbook style",
    "pathology": "pathological process illustration, microscopic tissue view, clinical pathology",
    "flowchart": "medical flowchart, step-by-step clinical process diagram, clean infographic layout",
    "comparison": "side-by-side comparison diagram, normal vs abnormal, medical educational chart",
    "infographic": "medical data infographic, statistical visualization, clean chart design",
    "symptom": "symptom illustration, clinical presentation diagram, patient assessment visual",
    "prevention": "health prevention guide illustration, wellness lifestyle diagram, educational visual",
    "illustration": "professional medical illustration, clean educational diagram, healthcare visual",
}


def _heuristic_en_prompt(description: str, image_type: str) -> str:
    """基于中文描述和关键词映射，生成可用的英文 SD 绘图提示词（不依赖 LLM）"""
    scene = _TYPE_EN_SCENE.get(image_type, _TYPE_EN_SCENE["illustration"])
    en_terms = []
    desc_lower = description.lower()
    for zh, en in _ZH_EN_MEDICAL:
        if zh in desc_lower:
            en_terms.append(en)
    terms_str = ", ".join(en_terms[:6]) if en_terms else "medical concept"
    quality = "professional, detailed, clean background, high quality, scientific accuracy, educational"
    return f"{scene}, depicting {terms_str}, {quality}"


def _infer_image_type(para: str) -> str:
    text = para.lower()
    for itype, keywords in _TYPE_KEYWORDS:
        for kw in keywords:
            if _re.search(kw, text):
                return itype
    return "illustration"


@router.get("/suggestions/{section_id}")
async def get_suggestions(
    section_id: int,
    enhance: int = 0,
    db=Depends(get_db),
):
    """获取章节配图建议。优先读取数据库已存储的建议，否则启发式+轻量LLM。"""
    import json, logging, asyncio

    _log = logging.getLogger("uvicorn.error")

    sec_result = await db.execute(
        select(ArticleSection, Article).join(Article, ArticleSection.article_id == Article.id).where(ArticleSection.id == section_id)
    )
    row = sec_result.one_or_none()
    if not row:
        raise HTTPException(404, detail="Section not found")
    section, article = row
    cf = article.content_format or "article"
    if cf in ("comic_strip", "storyboard", "card_series"):
        return {"suggestions": [], "fallback": False}

    # --- 优先从 DB 读取已存储的建议（含 en_description） ---
    if not enhance and section.image_suggestions:
        try:
            stored = json.loads(section.image_suggestions) if isinstance(section.image_suggestions, str) else section.image_suggestions
            if isinstance(stored, list) and stored:
                return {"suggestions": stored, "fallback": False}
        except Exception:
            pass

    cont_result = await db.execute(
        select(ArticleContent).where(
            ArticleContent.section_id == section_id,
            ArticleContent.is_current == True,
        ).limit(1)
    )
    content_rec = cont_result.scalar_one_or_none()
    if not content_rec or not content_rec.content_json:
        return {"suggestions": [], "fallback": False}

    BLOCK_TYPES = {"paragraph", "heading", "blockquote", "listItem", "codeBlock"}

    def _extract_text(node):
        """从 Tiptap JSON 提取纯文本，在块级节点之间插入换行以保留段落结构"""
        if isinstance(node, str):
            return node
        if not isinstance(node, dict):
            return ""
        if node.get("type") == "text":
            return node.get("text", "")
        children = node.get("content", [])
        parts = [_extract_text(c) for c in children]
        joined = "".join(parts)
        if node.get("type") in BLOCK_TYPES:
            return joined + "\n\n"
        return joined

    try:
        doc = json.loads(content_rec.content_json) if isinstance(content_rec.content_json, str) else content_rec.content_json
    except Exception:
        return {"suggestions": [], "fallback": False}
    full_text = _extract_text(doc).strip()
    if len(full_text) < 100:
        return {"suggestions": [], "fallback": False}

    # --- 解析已存储的建议（用于判断来源） ---
    existing_suggestions = None
    if section.image_suggestions:
        try:
            existing_suggestions = json.loads(section.image_suggestions) if isinstance(section.image_suggestions, str) else section.image_suggestions
            if not isinstance(existing_suggestions, list):
                existing_suggestions = None
        except Exception:
            existing_suggestions = None

    def _is_llm_source(sug_list: list | None) -> bool:
        if not sug_list:
            return False
        return any(s.get("_source") == "llm" for s in sug_list)

    # enhance=1 时优先复用 DB 中已存在的 LLM 结果（章节生成期 SSE 流已写入）；
    # 此入口不主动调用新的 LLM，避免在已结算的章节生成之外免费刷 LLM 请求
    if enhance and existing_suggestions and _is_llm_source(existing_suggestions):
        return {"suggestions": existing_suggestions, "fallback": False}

    # --- 启发式段落配图建议（仅在 DB 无建议时使用） ---
    from app.services.format_router import FORMAT_CONFIG
    from app.services.imagegen.image_types import recommend_tool
    suggestions = []
    paragraphs = [p for p in full_text.split("\n\n") if len(p.strip()) > 80]
    cfg = FORMAT_CONFIG.get(cf, {})
    style = cfg.get("image_style", "medical_illustration")

    for i, para in enumerate(paragraphs):
        anchor = para.strip()[:50]
        it = _infer_image_type(para)
        desc_text = para.strip()[:80] + ("…" if len(para.strip()) > 80 else "")
        rec = recommend_tool(it, style, desc_text)
        en_local = _heuristic_en_prompt(desc_text, it)
        suggestions.append({
            "anchor_text": anchor,
            "image_type": it,
            "style": style,
            "description": desc_text,
            "en_description": en_local,
            "reason": _REASON_MAP.get(it, "段落内容适合配图"),
            "priority": "medium",
            "index": i,
            "recommended_tool": rec["tool"],
            "tool_label": rec["tool_label"],
            "tool_reason": rec["reason"],
            "_source": "heuristic",
        })
    suggestions = suggestions[:5]

    # 仅在 DB 无建议时写入启发式结果，绝不覆盖已有的 LLM 结果
    # 注意：不再触发后台 _upgrade_en_prompts_background（fire-and-forget LLM 调用
    # 无法关联到 billing_session，且每次拿建议都会触发，会被免费刷量）
    if suggestions and not existing_suggestions:
        try:
            from sqlalchemy import update
            await db.execute(
                update(ArticleSection)
                .where(ArticleSection.id == section_id)
                .values(image_suggestions=suggestions)
            )
            await db.commit()
        except Exception:
            pass

    return {"suggestions": suggestions, "fallback": True}
