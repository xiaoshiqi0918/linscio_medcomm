"""图像生成 API"""
import asyncio
import uuid
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, Query
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


async def _run_task(task_id: str, **kwargs) -> None:
    """走图像生成图：build_med_prompt → safety_check → generate → postprocess → save"""
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
            _tasks[task_id]["status"] = "done"
            _tasks[task_id]["images"] = [{"path": u} for u in urls]
            _tasks[task_id]["provider_fallback"] = "pollinations" if state.get("is_fallback") else None
            _tasks[task_id]["seeds"] = state.get("used_seeds") or []
    except Exception as e:
        if task_id in _tasks and not _tasks[task_id].get("_cancelled"):
            _tasks[task_id]["status"] = "failed"
            _tasks[task_id]["error"] = str(e)


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
async def create_task(req: CreateTaskRequest):
    """创建图像生成任务，支持 content_format/image_type（条漫 style=comic, image_type=comic_panel）"""
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
async def post_generate(req: GenerateRequest):
    """生成图像（走图像生成图：prompt 增强 + safety_check + 生成 + 保存）"""
    db_v, db_s = "", None
    if req.article_id:
        db_v, db_s = await _load_article_series_fields(req.article_id)
    vc, sb = _resolve_continuity_and_seed(
        visual_continuity_prompt=req.visual_continuity_prompt,
        seed_base=req.seed_base,
        db_visual=db_v,
        db_seed=db_s,
    )
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
    if state.get("error"):
        raise HTTPException(status_code=400, detail=state["error"])
    return {
        "urls": state.get("urls", []),
        "is_fallback": state.get("is_fallback", False),
        "seeds": state.get("used_seeds") or [],
    }


@router.post("/ai-prompts")
async def post_ai_image_prompts(req: AiImagePromptsRequest):
    """AI 生成正/负向提示词（每次覆盖，由前端写入输入框）"""
    pos, neg, used_template_fallback = await ai_generate_image_prompts(
        scene_idea=req.scene_idea,
        style=req.style,
        image_type=req.image_type,
        target_audience=req.target_audience,
        content_format=req.content_format,
    )
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


@router.post("/comic/batch")
async def comic_batch(req: ComicBatchRequest, db=Depends(get_db)):
    """条漫批量生成：多格一次提交；继承文章级连贯文案与系列种子基准"""
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
        asyncio.create_task(_run_task(
            task_id,
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
        ))
        tasks_created.append({"task_id": task_id, "panel_index": p.panel_index})
    return {"tasks": tasks_created}


@router.get("/suggestions/{section_id}")
async def get_suggestions(section_id: int, db=Depends(get_db)):
    """获取章节配图建议（基于内容摘要）"""
    from app.services.format_router import FORMAT_CONFIG

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
    cont_result = await db.execute(
        select(ArticleContent).where(
            ArticleContent.section_id == section_id,
            ArticleContent.is_current == True,
        ).limit(1)
    )
    content_rec = cont_result.scalar_one_or_none()
    if not content_rec or not content_rec.content_json:
        return {"suggestions": [], "fallback": False}
    import json
    try:
        doc = json.loads(content_rec.content_json) if isinstance(content_rec.content_json, str) else content_rec.content_json
    except Exception:
        return {"suggestions": [], "fallback": False}
    text_parts = []
    for node in doc.get("content", []):
        if node.get("type") == "paragraph":
            for c in node.get("content", []):
                if c.get("type") == "text" and c.get("text"):
                    text_parts.append(c["text"])
    full_text = "\n\n".join(text_parts)
    suggestions = []
    for i, para in enumerate(full_text.split("\n\n")):
        if len(para.strip()) > 80:
            anchor = para.strip()[:50]
            cfg = FORMAT_CONFIG.get(cf, {})
            style = cfg.get("image_style", "medical_illustration")
            suggestions.append({
                "anchor_text": anchor,
                "image_type": "illustration",
                "style": style,
                "index": i,
            })
    return {"suggestions": suggestions[:5], "fallback": False}
