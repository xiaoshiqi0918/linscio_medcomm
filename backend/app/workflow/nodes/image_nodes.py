"""
图像生成图节点
build_med_prompt → safety_check → generate_images → postprocess → save_images
"""
from app.workflow.states import ImageGenState

STYLE_HINT = {
    "medical_illustration": "医学插画风格，清晰准确",
    "comic": "科普漫画风格，易懂有趣",
    "flat_design": "扁平化设计，简洁现代",
    "picture_book": "绘本风格，适合儿童",
}

# 安全过滤：含以下词则拒绝（医学插图场景放宽）
SAFETY_BLOCK_WORDS = {"暴力", "血腥", "色情", "恐怖"}

_MAX_COMBINED_PROMPT_LEN = 4000


def _apply_visual_continuity_positive(positive: str, continuity: str) -> str:
    """将文章级锁定文案置于正向提示词前，便于各格/各图共用同一视觉约束。"""
    c = (continuity or "").strip()
    if not c:
        return positive
    prefix = f"[Series visual continuity — apply throughout] {c}\n\n"
    return prefix + (positive or "").strip()


async def build_med_prompt_node(state: ImageGenState) -> ImageGenState:
    """构建医学图像提示词；用户正向非空时跳过自动构建；负向非空则完全覆盖默认医学负向"""
    style_raw = state.get("style", "medical_illustration")
    cf = state.get("content_format", "article")
    from app.services.imagegen.image_types import get_style_for_format, get_image_type_for_format
    from app.services.imagegen.prompt_builder import build_med_prompt, get_default_medical_negative

    style_f = get_style_for_format(cf, style_raw)
    image_type_f = get_image_type_for_format(cf, state.get("image_type"))

    up = (state.get("user_positive_prompt") or "").strip()
    un = (state.get("user_negative_prompt") or "").strip()

    vlock = (state.get("visual_continuity_prompt") or "").strip()

    if up:
        negative = un if un else get_default_medical_negative(style_f, image_type_f)
        pos = _apply_visual_continuity_positive(up, vlock)
        return {**state, "prompt": pos, "negative_prompt": negative, "error": None}

    desc = (state.get("scene_desc") or "").strip()
    if not desc:
        return {**state, "error": "请填写场景描述，或直接填写正向提示词"}

    try:
        from app.core.database import AsyncSessionLocal
        from app.models.image_prompt_template import ImagePromptTemplate
        from sqlalchemy import select
        async with AsyncSessionLocal() as db:
            r = await db.execute(
                select(ImagePromptTemplate).where(
                    ImagePromptTemplate.content_format == cf,
                    ImagePromptTemplate.style == style_raw,
                    ImagePromptTemplate.is_active == True,
                ).limit(1)
            )
            t = r.scalars().first()
            if t and t.prompt_template:
                full_prompt = _apply_visual_continuity_positive(
                    t.prompt_template.replace("{scene}", desc), vlock
                )
                negative = un if un else get_default_medical_negative(style_f, image_type_f)
                return {**state, "prompt": full_prompt, "negative_prompt": negative, "error": None}
    except Exception:
        pass

    try:
        result = await build_med_prompt(
            user_desc=desc,
            image_type=image_type_f,
            style=style_f,
            specialty=state.get("specialty", ""),
            target_audience=state.get("target_audience", "public"),
            translate_chinese=True,
        )
        positive, built_neg, rejection = result if len(result) >= 3 else (*result, None)
        if rejection:
            return {**state, "error": rejection}
        negative = un if un else (built_neg or "")
        positive = _apply_visual_continuity_positive(positive, vlock)
        return {**state, "prompt": positive, "negative_prompt": negative, "error": None}
    except Exception:
        hint = STYLE_HINT.get(style_f, "医学插画")
        fallback = _apply_visual_continuity_positive(f"{hint}。{desc}", vlock)
        negative = un if un else get_default_medical_negative(style_f, image_type_f)
        return {**state, "prompt": fallback, "negative_prompt": negative, "error": None}


def safety_check_node(state: ImageGenState) -> ImageGenState:
    """安全检查：过滤敏感内容（正+负）"""
    if state.get("error"):
        return state
    prompt = state.get("prompt", "")
    neg = state.get("negative_prompt", "")
    combined = f"{prompt}\n{neg}"
    for w in SAFETY_BLOCK_WORDS:
        if w in combined:
            return {**state, "error": "提示词含敏感词，已拒绝生成"}
    if len(combined) > _MAX_COMBINED_PROMPT_LEN:
        return {**state, "error": "提示词过长"}
    return {**state}


def _optional_int(v) -> int | None:
    if v is None:
        return None
    try:
        i = int(v)
        return i if i > 0 else None
    except (TypeError, ValueError):
        return None


def _optional_float(v) -> float | None:
    if v is None:
        return None
    try:
        f = float(v)
        return f if f > 0 else None
    except (TypeError, ValueError):
        return None


async def generate_images_node(state: ImageGenState) -> ImageGenState:
    """调用生成引擎"""
    from app.services.imagegen.engine import generate_image
    from app.services.imagegen.image_types import get_style_for_format, get_image_type_for_format

    if state.get("error"):
        return state
    prompt = state.get("prompt", "")
    cf = state.get("content_format", "article")
    style = get_style_for_format(cf, state.get("style"))
    image_type = get_image_type_for_format(cf, state.get("image_type"))
    skip_env = bool((state.get("user_positive_prompt") or "").strip())

    w = int(state.get("width") or 1024)
    h = int(state.get("height") or 1024)

    comfy_overrides: dict = {}
    for k in (
        "comfy_workflow_path",
        "comfy_mode",
        "comfy_base_url",
        "comfy_prompt_node_id",
        "comfy_prompt_input_key",
        "comfy_negative_node_id",
        "comfy_negative_input_key",
        "comfy_ksampler_node_id",
    ):
        if state.get(k):
            comfy_overrides[k] = state[k]

    neg = (state.get("negative_prompt") or "").strip() or None
    try:
        bc = int(state.get("batch_count") or 1)
    except (TypeError, ValueError):
        bc = 1

    seed_raw = state.get("seed")
    seed_param: int | None
    if seed_raw is not None:
        try:
            seed_param = int(seed_raw)
        except (TypeError, ValueError):
            seed_param = None
    else:
        sb = state.get("seed_base")
        if sb is not None:
            try:
                base = int(sb)
                pi = state.get("panel_index")
                off = int(pi) if pi is not None else 0
                seed_param = base + off
            except (TypeError, ValueError):
                seed_param = None
        else:
            seed_param = None

    steps = _optional_int(state.get("steps"))
    cfg_scale = _optional_float(state.get("cfg_scale"))
    sn = (state.get("sampler_name") or "").strip() or None

    raw_loras = state.get("loras")
    loras_param: list[tuple[str, float]] | None = None
    if raw_loras and isinstance(raw_loras, list):
        loras_param = [(str(pair[0]), float(pair[1])) for pair in raw_loras if len(pair) >= 2]

    try:
        urls, is_fallback, meta = await generate_image(
            prompt=prompt,
            style=style,
            width=w,
            height=h,
            image_type=image_type,
            preferred_provider=state.get("preferred_provider"),
            siliconflow_image_model=state.get("siliconflow_image_model"),
            comfy_overrides=comfy_overrides or None,
            negative_prompt=neg,
            batch_count=bc,
            seed=seed_param,
            steps=steps,
            cfg_scale=cfg_scale,
            sampler_name=sn,
            skip_style_envelope=skip_env,
            loras=loras_param,
        )
        used = meta.get("seeds") if isinstance(meta, dict) else []
        return {
            **state,
            "urls": urls,
            "is_fallback": is_fallback,
            "used_seeds": used if isinstance(used, list) else [],
        }
    except Exception as e:
        return {**state, "error": str(e), "urls": [], "used_seeds": []}


def postprocess_node(state: ImageGenState) -> ImageGenState:
    """后处理：占位，可扩展尺寸/格式转换"""
    return state


async def save_images_node(state: ImageGenState) -> ImageGenState:
    """可选：将生成记录写入 GeneratedImage 表"""
    urls = state.get("urls") or []
    if not urls:
        return state
    try:
        from app.core.database import AsyncSessionLocal
        from app.models.image import GeneratedImage
        from app.services.imagegen.image_types import get_image_type_for_format

        it = get_image_type_for_format(state.get("content_format", "article"), state.get("image_type"))
        pos = state.get("prompt", "")
        neg = (state.get("negative_prompt") or "").strip()
        prompt_store = pos if not neg else f"{pos}\n---NEG---\n{neg}"
        async with AsyncSessionLocal() as db:
            for i, path in enumerate(urls):
                if path.startswith("medcomm-image://"):
                    rel = path.replace("medcomm-image://", "")
                    rec = GeneratedImage(
                        user_id=1,
                        file_path=rel,
                        prompt=prompt_store[:4000],
                        provider="engine",
                        style=state.get("style", "medical_illustration"),
                        content_format=state.get("content_format"),
                        image_type=it,
                    )
                    db.add(rec)
            await db.commit()
    except Exception:
        pass
    return state
