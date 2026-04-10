"""
图像生成引擎
DALL·E 3 / 通义万相 / 文心一格 / ComfyUI（本地或 Comfy Cloud）等；Pollinations 免费降级
"""
import logging
import os
import asyncio
import hashlib
import random
import httpx
from datetime import datetime
from pathlib import Path
from typing import Optional
from urllib.parse import quote

from app.core.config import settings

_dalle_semaphore = asyncio.Semaphore(2)


def _dalle3_size(width: int, height: int) -> str:
    if height > width * 1.1:
        return "1024x1792"
    if width > height * 1.1:
        return "1792x1024"
    return "1024x1024"


def _api_prompt_with_negative(positive: str, negative: str | None) -> str:
    pos = (positive or "").strip()
    neg = (negative or "").strip()
    if not neg:
        return pos
    return f"{pos}\n\nAvoid depicting: {neg}"


def _resolve_workflow_path(raw: str) -> Path:
    """Resolve a workflow path: absolute paths used as-is, relative resolved against project root."""
    p = Path(raw).expanduser()
    if p.is_absolute():
        return p
    project_root = Path(__file__).resolve().parents[3]
    return project_root / p


def _comfy_workflow_path(overrides: dict | None) -> str:
    o = overrides or {}
    return (o.get("comfy_workflow_path") or os.environ.get("COMFYUI_WORKFLOW_JSON", "")).strip()


def _comfy_available_local(overrides: dict | None) -> bool:
    p = _comfy_workflow_path(overrides)
    if not p:
        return False
    return _resolve_workflow_path(p).is_file()


def _comfy_available_cloud(overrides: dict | None) -> bool:
    return _comfy_available_local(overrides) and bool(os.environ.get("COMFY_CLOUD_API_KEY", "").strip())


async def detect_providers() -> dict:
    """检测可用 Provider（含 ComfyUI 运行时健康检查）"""
    wenxin_key = bool(os.environ.get("ERNIE_IMAGE_API_KEY") or os.environ.get("BAIDU_API_KEY"))
    wenxin_secret = bool(os.environ.get("ERNIE_IMAGE_SECRET") or os.environ.get("BAIDU_SECRET_KEY"))
    ov = None
    local_configured = _comfy_available_local(ov)
    local_running = False
    if local_configured:
        base = os.environ.get("COMFYUI_BASE_URL", "").strip() or "http://127.0.0.1:8188"
        local_running = await _comfy_health_check(base)
    return {
        "openai": bool(os.environ.get("OPENAI_API_KEY")),
        "midjourney": bool(os.environ.get("MIDJOURNEY_PROXY_URL")),
        "wanx": bool(os.environ.get("DASHSCOPE_API_KEY")),
        "wenxin": wenxin_key and wenxin_secret,
        "siliconflow": bool(os.environ.get("SILICONFLOW_API_KEY")),
        "comfyui_local": local_configured,
        "comfyui_local_running": local_running,
        "comfyui_cloud": _comfy_available_cloud(ov),
        "pollinations": True,
    }


def _save_local(
    data: bytes,
    suffix: str = ".png",
    provider: str = "unknown",
    image_type: str = "generated",
) -> str:
    """保存到本地，路径格式 images/YYYY/MM/img_{hash}_{provider}_{type}.png"""
    now = datetime.utcnow()
    subdir = f"images/{now.year}/{now.month:02d}"
    base = Path(settings.app_data_root) / subdir
    base.mkdir(parents=True, exist_ok=True)
    h = hashlib.sha256(data).hexdigest()[:12]
    fn = f"img_{h}_{provider}_{image_type}{suffix}"
    path = base / fn
    path.write_bytes(data)
    return str(path.relative_to(settings.app_data_root))


async def _dalle3(
    prompt: str,
    style: str,
    width: int,
    height: int,
    image_type: str = "generated",
) -> list[str]:
    """DALL·E 3，每次 n=1"""
    from openai import AsyncOpenAI
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        return []
    client = AsyncOpenAI(api_key=api_key)
    async with _dalle_semaphore:
        resp = await client.images.generate(
            model="dall-e-3",
            prompt=prompt,
            n=1,
            size=_dalle3_size(width, height),
            quality="standard",
        )
    url = resp.data[0].url
    if not url:
        return []
    async with httpx.AsyncClient() as c:
        r = await c.get(url)
        r.raise_for_status()
    rel = _save_local(r.content, provider="dalle3", image_type=image_type)
    return [f"medcomm-image://{rel}"]


async def _pollinations(
    prompt: str,
    image_type: str = "generated",
) -> list[str]:
    """Pollinations.ai — 需要 API Key（enter.pollinations.ai 申请）"""
    encoded = quote(prompt)
    api_key = os.environ.get("POLLINATIONS_API_KEY", "").strip()
    url = f"https://gen.pollinations.ai/image/{encoded}?width=1024&height=1024"
    headers = {}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as c:
        r = await c.get(url, headers=headers)
        r.raise_for_status()
    rel = _save_local(r.content, provider="pollinations", image_type=image_type)
    return [f"medcomm-image://{rel}"]


def _wanx_sync(prompt: str, size_str: str, image_type: str = "generated") -> list[str]:
    """通义万相同步调用（在 executor 中运行）"""
    import dashscope
    from dashscope import ImageSynthesis
    key = os.environ.get("DASHSCOPE_API_KEY", "")
    dashscope.api_key = key
    rsp = ImageSynthesis.call(
        model="wanx2.1-t2i-turbo",
        prompt=prompt,
        n=1,
        size=size_str,
    )
    if rsp.status_code != 200 or not rsp.output or not rsp.output.results:
        return []
    url = rsp.output.results[0].url
    if not url:
        return []
    import httpx
    with httpx.Client(timeout=60.0) as c:
        r = c.get(url)
        r.raise_for_status()
    rel = _save_local(r.content, provider="wanx", image_type=image_type)
    return [f"medcomm-image://{rel}"]


async def _wanx(
    prompt: str,
    style: str,
    width: int,
    height: int,
    image_type: str = "generated",
) -> list[str]:
    """通义万相（阿里云 DashScope）文生图"""
    try:
        from dashscope import ImageSynthesis  # noqa: F401
    except ImportError:
        raise RuntimeError("请安装 dashscope: pip install dashscope")
    key = os.environ.get("DASHSCOPE_API_KEY", "")
    if not key:
        return []
    size_map = {
        (1024, 1024): "1024*1024",
        (720, 1280): "720*1280",
        (1280, 720): "1280*720",
    }
    size_str = size_map.get((width, height), "1024*1024")
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, lambda: _wanx_sync(prompt, size_str, image_type))


async def _wenxin(
    prompt: str,
    width: int,
    height: int,
    image_type: str = "generated",
) -> list[str]:
    """文心一格（百度）文生图 - 需安装 qianfan"""
    try:
        import qianfan
    except ImportError:
        return []
    key = os.environ.get("ERNIE_IMAGE_API_KEY") or os.environ.get("BAIDU_API_KEY")
    secret = os.environ.get("ERNIE_IMAGE_SECRET") or os.environ.get("BAIDU_SECRET_KEY")
    if not key or not secret:
        return []
    client = qianfan.Image()
    rsp = client.do(prompt=prompt, with_payload=False)
    if not rsp or "data" not in rsp:
        return []
    img_data = rsp.get("data", [{}])[0].get("b64_image")
    if not img_data:
        return []
    import base64
    data = base64.b64decode(img_data)
    rel = _save_local(data, provider="wenxin", image_type=image_type)
    return [f"medcomm-image://{rel}"]


async def _siliconflow(
    prompt: str,
    width: int,
    height: int,
    image_type: str = "generated",
    model: str | None = None,
) -> list[str]:
    """硅基流动文生图（OpenAI 兼容 Images API）"""
    key = os.environ.get("SILICONFLOW_API_KEY", "")
    if not key:
        return []
    image_model = model or os.environ.get("SILICONFLOW_IMAGE_MODEL", "Kwai-Kolors/Kolors")
    try:
        from openai import AsyncOpenAI
        client = AsyncOpenAI(
            api_key=key,
            base_url="https://api.siliconflow.cn/v1",
        )
        resp = await client.images.generate(
            model=image_model,
            prompt=prompt,
            n=1,
            size=f"{width}x{height}",
        )
        data = resp.data[0] if resp.data else None
        if not data:
            return []
        if getattr(data, "url", None):
            async with httpx.AsyncClient(timeout=60.0) as c:
                r = await c.get(data.url)
                r.raise_for_status()
            rel = _save_local(r.content, provider="siliconflow", image_type=image_type)
            return [f"medcomm-image://{rel}"]
        if getattr(data, "b64_json", None):
            import base64
            raw = base64.b64decode(data.b64_json)
            rel = _save_local(raw, provider="siliconflow", image_type=image_type)
            return [f"medcomm-image://{rel}"]
    except Exception:
        return []
    return []


_mj_semaphore = asyncio.Semaphore(2)


def _mj_aspect_ratio(width: int, height: int) -> str:
    """将像素尺寸映射为 Midjourney --ar 参数"""
    r = width / height
    if r > 1.6:
        return "16:9"
    if r > 1.2:
        return "4:3"
    if r < 0.625:
        return "9:16"
    if r < 0.85:
        return "3:4"
    return "1:1"


async def _midjourney(
    prompt: str,
    width: int,
    height: int,
    image_type: str = "generated",
) -> list[str]:
    """Midjourney via proxy API（兼容 midjourney-proxy / GoAPI 等常见代理格式）"""
    base_url = os.environ.get("MIDJOURNEY_PROXY_URL", "").strip().rstrip("/")
    api_secret = os.environ.get("MIDJOURNEY_API_SECRET", "").strip()
    if not base_url:
        return []

    ar = _mj_aspect_ratio(width, height)
    full_prompt = f"{prompt} --ar {ar} --v 6.1"

    headers: dict[str, str] = {"Content-Type": "application/json"}
    if api_secret:
        headers["mj-api-secret"] = api_secret

    async with _mj_semaphore:
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(
                    f"{base_url}/mj/submit/imagine",
                    headers=headers,
                    json={"prompt": full_prompt, "botType": "MID_JOURNEY"},
                )
                resp.raise_for_status()
                data = resp.json()
                code = data.get("code")
                if code not in (1, 22):
                    _log.warning("Midjourney submit failed: code=%s desc=%s", code, data.get("description"))
                    return []
                task_id = data.get("result")
                if not task_id:
                    return []
        except Exception as exc:
            _log.warning("Midjourney submit error: %s", exc)
            return []

        max_wait, interval = 300, 5
        elapsed = 0
        image_url = None

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                while elapsed < max_wait:
                    await asyncio.sleep(interval)
                    elapsed += interval
                    resp = await client.get(
                        f"{base_url}/mj/task/{task_id}/fetch",
                        headers=headers,
                    )
                    resp.raise_for_status()
                    task = resp.json()
                    status = task.get("status", "")
                    if status == "SUCCESS":
                        image_url = task.get("imageUrl")
                        break
                    elif status == "FAILURE":
                        _log.warning("Midjourney task failed: %s", task.get("failReason"))
                        return []
        except Exception as exc:
            _log.warning("Midjourney poll error: %s", exc)
            return []

    if not image_url:
        _log.warning("Midjourney task timed out after %ds", max_wait)
        return []

    try:
        async with httpx.AsyncClient(timeout=60.0) as c:
            r = await c.get(image_url)
            r.raise_for_status()
        rel = _save_local(r.content, provider="midjourney", image_type=image_type)
        return [f"medcomm-image://{rel}"]
    except Exception as exc:
        _log.warning("Midjourney download error: %s", exc)
        return []


_log = logging.getLogger("linscio.imagegen")


def _resolve_comfy_mode(
    preferred_provider: str | None,
    overrides: dict | None,
) -> str | None:
    o = overrides or {}
    explicit = (o.get("comfy_mode") or "").strip().lower()
    if explicit in ("local", "cloud"):
        return explicit
    p = (preferred_provider or "").strip().lower()
    if p == "comfyui_local":
        return "local"
    if p == "comfyui_cloud":
        return "cloud"
    if p in ("comfyui", "comfy", "auto", ""):
        m = os.environ.get("COMFYUI_MODE", "auto").strip().lower()
        if m == "cloud":
            return "cloud"
        if m == "local":
            return "local"
        return "cloud" if os.environ.get("COMFY_CLOUD_API_KEY", "").strip() else "local"
    return None


def _comfy_skip_for_mode(mode: str | None, overrides: dict | None) -> bool:
    if mode == "local":
        return not _comfy_available_local(overrides)
    if mode == "cloud":
        return not _comfy_available_cloud(overrides)
    return True


async def _comfy_health_check(base_url: str, timeout: float = 3.0) -> bool:
    """Fast ping to ComfyUI /system_stats to detect if the server is reachable."""
    try:
        async with httpx.AsyncClient(timeout=timeout) as c:
            r = await c.get(f"{base_url}/system_stats")
            return r.status_code == 200
    except Exception:
        return False


async def _comfyui(
    positive_prompt: str,
    negative_prompt: str | None,
    image_type: str,
    preferred_provider: str | None,
    overrides: dict | None,
    seed: int | None = None,
    steps: int | None = None,
    cfg_scale: float | None = None,
    sampler_name: str | None = None,
    width: int | None = None,
    height: int | None = None,
    loras: list[tuple[str, float]] | None = None,
) -> list[str]:
    mode = _resolve_comfy_mode(preferred_provider, overrides)
    if mode is None:
        return []
    o = overrides or {}
    wf_path = _comfy_workflow_path(o)
    if not wf_path:
        return []
    resolved_wf = _resolve_workflow_path(wf_path)
    if not resolved_wf.is_file():
        return []
    if mode == "cloud" and not os.environ.get("COMFY_CLOUD_API_KEY", "").strip():
        return []
    base = (o.get("comfy_base_url") or "").strip()
    if not base:
        base = os.environ.get("COMFYUI_BASE_URL", "").strip()
    if not base:
        base = "https://cloud.comfy.org" if mode == "cloud" else "http://127.0.0.1:8188"
    if mode == "local" and not await _comfy_health_check(base):
        _log.info("ComfyUI local 不可达 (%s)，跳过并降级到 API", base)
        return []
    node_id = (o.get("comfy_prompt_node_id") or os.environ.get("COMFYUI_PROMPT_NODE_ID", "6")).strip()
    input_key = (o.get("comfy_prompt_input_key") or os.environ.get("COMFYUI_PROMPT_INPUT_KEY", "text")).strip()
    neg_node = (o.get("comfy_negative_node_id") or os.environ.get("COMFYUI_NEGATIVE_NODE_ID", "")).strip() or None
    neg_key = (o.get("comfy_negative_input_key") or os.environ.get("COMFYUI_NEGATIVE_INPUT_KEY", "text")).strip() or "text"
    ksampler = (o.get("comfy_ksampler_node_id") or os.environ.get("COMFYUI_KSAMPLER_NODE_ID", "")).strip() or None
    latent_node = (o.get("comfy_latent_node_id") or os.environ.get("COMFYUI_LATENT_NODE_ID", "")).strip() or None
    api_key = os.environ.get("COMFY_CLOUD_API_KEY", "").strip() if mode == "cloud" else None
    try:
        timeout = int(os.environ.get("COMFYUI_TIMEOUT_SEC", "300"))
    except ValueError:
        timeout = 300

    from app.services.imagegen.comfy_client import submit_and_wait_image

    try:
        data = await submit_and_wait_image(
            positive_prompt=positive_prompt,
            mode=mode,
            base_url=base,
            api_key=api_key,
            workflow_path=str(resolved_wf),
            prompt_node_id=node_id,
            prompt_input_key=input_key,
            negative_prompt=negative_prompt,
            negative_node_id=neg_node,
            negative_input_key=neg_key,
            ksampler_node_id=ksampler,
            latent_node_id=latent_node,
            width=width,
            height=height,
            seed=seed,
            steps=steps,
            cfg=cfg_scale,
            sampler_name=sampler_name,
            loras=loras,
            timeout_sec=timeout,
        )
    except Exception as e:
        _log.warning("ComfyUI 生成失败: %s", e)
        return []
    rel = _save_local(data, provider=f"comfyui_{mode}", image_type=image_type)
    return [f"medcomm-image://{rel}"]


async def generate_image(
    prompt: str,
    style: str = "medical_illustration",
    width: int = 1024,
    height: int = 1024,
    image_type: str = "generated",
    preferred_provider: str | None = None,
    siliconflow_image_model: str | None = None,
    comfy_overrides: dict | None = None,
    negative_prompt: str | None = None,
    batch_count: int = 1,
    seed: int | None = None,
    steps: int | None = None,
    cfg_scale: float | None = None,
    sampler_name: str | None = None,
    skip_style_envelope: bool = False,
    loras: list[tuple[str, float]] | None = None,
) -> tuple[list[str], bool, dict]:
    """
    生成图像，返回 (URL/路径列表, is_fallback, meta)。
    meta 含 seeds: 每图使用的种子；provider: 实际使用的提供方逻辑名。
    ComfyUI 使用独立负向节点；其他 API 将负向合并进主 prompt。
    """
    if skip_style_envelope:
        base_pos = (prompt or "").strip()
    elif "professional" in prompt or "illustration" in prompt or "medical" in prompt:
        base_pos = prompt
    else:
        style_hint = {
            "medical_illustration": "professional medical illustration, clear and accurate",
            "comic": "comic strip style, educational and engaging",
            "flat_design": "flat design, clean and modern",
            "picture_book": "children's picture book style",
            "realistic": "realistic medical illustration",
            "cartoon": "friendly cartoon style",
            "data_viz": "data visualization style",
        }.get(style, "professional medical illustration")
        base_pos = f"{style_hint}. {prompt}"
    api_merged = _api_prompt_with_negative(base_pos, negative_prompt)
    it = image_type or "generated"
    meta: dict = {"seeds": [], "provider": None}

    try:
        bc = int(batch_count or 1)
    except (TypeError, ValueError):
        bc = 1
    bc = max(1, min(bc, 8))

    def _comfy_provider_skip() -> bool:
        pref = (preferred_provider or "").strip().lower()
        m = _resolve_comfy_mode(preferred_provider, comfy_overrides)
        if m is None and pref in ("auto", ""):
            m = _resolve_comfy_mode("comfyui", comfy_overrides)
        if m is None:
            return True
        return _comfy_skip_for_mode(m, comfy_overrides)

    skip_openai = not os.environ.get("OPENAI_API_KEY")
    skip_mj = not os.environ.get("MIDJOURNEY_PROXY_URL")
    skip_wanx = not os.environ.get("DASHSCOPE_API_KEY")
    skip_sf = not os.environ.get("SILICONFLOW_API_KEY")
    skip_wenxin = not (os.environ.get("ERNIE_IMAGE_API_KEY") or os.environ.get("BAIDU_API_KEY"))
    skip_comfy = _comfy_provider_skip()

    async def openai_fn(_iter_s: int) -> list[str]:
        return await _dalle3(api_merged, style, width, height, it)

    async def midjourney_fn(_iter_s: int) -> list[str]:
        return await _midjourney(api_merged, width, height, it)

    async def wanx_fn(_iter_s: int) -> list[str]:
        return await _wanx(api_merged, style, width, height, it)

    async def silicon_fn(_iter_s: int) -> list[str]:
        return await _siliconflow(api_merged, width, height, it, siliconflow_image_model)

    async def wenxin_fn(_iter_s: int) -> list[str]:
        return await _wenxin(api_merged, width, height, it)

    _comfy_pos_rewritten = None

    async def comfy_fn(iter_s: int) -> list[str]:
        nonlocal _comfy_pos_rewritten
        if _comfy_pos_rewritten is None:
            from app.services.imagegen.prompt_builder import rewrite_prompt_for_sd
            _comfy_pos_rewritten = await rewrite_prompt_for_sd(base_pos, it)
        return await _comfyui(
            _comfy_pos_rewritten,
            negative_prompt,
            it,
            preferred_provider,
            comfy_overrides,
            seed=iter_s,
            steps=steps,
            cfg_scale=cfg_scale,
            sampler_name=sampler_name,
            width=width,
            height=height,
            loras=loras,
        )

    async def poll_fn(_iter_s: int) -> list[str]:
        return await _pollinations(api_merged, it)

    ordered: list[tuple[str, object, bool]] = [
        ("comfyui", comfy_fn, skip_comfy),
        ("midjourney", midjourney_fn, skip_mj),
        ("openai", openai_fn, skip_openai),
        ("wanx", wanx_fn, skip_wanx),
        ("siliconflow", silicon_fn, skip_sf),
        ("wenxin", wenxin_fn, skip_wenxin),
    ]
    pref = (preferred_provider or "").strip().lower()
    if pref and pref not in ("auto", ""):
        sort_key = pref
        ordered = sorted(
            ordered,
            key=lambda p: 0
            if p[0] == sort_key or (sort_key.startswith("comfyui") and p[0] == "comfyui")
            else 1,
        )
    elif pref in ("auto", "") and it:
        from app.services.imagegen.image_types import is_structured_type
        if is_structured_type(it):
            _log.info("图像类型 %s 为结构化类型，优先使用 Midjourney/DALL·E 3", it)
            ordered = sorted(ordered, key=lambda p: (
                0 if p[0] == "midjourney" else 1 if p[0] == "openai" else 2 if p[0] == "comfyui" else 1
            ))

    winning_fn = None
    all_urls: list[str] = []
    is_fb = True

    for bi in range(bc):
        if seed is None or int(seed) < 0:
            iter_seed = random.randint(0, 2**31 - 1)
        else:
            iter_seed = int(seed) + bi
        meta["seeds"].append(iter_seed)

        if winning_fn is not None:
            try:
                urls = await winning_fn(iter_seed)
            except Exception:
                urls = []
            if not urls:
                break
            all_urls.extend(urls)
            continue

        found = False
        for name, fn, skip in ordered:
            if skip:
                continue
            try:
                urls = await fn(iter_seed)
            except Exception:
                urls = []
            if urls:
                winning_fn = fn
                meta["provider"] = name
                primary_names = {"comfyui", "midjourney"}
                if pref and pref not in ("auto", ""):
                    primary_names.add(pref)
                is_fb = name not in primary_names
                if is_fb:
                    meta["provider_fallback"] = name
                    _log.info("首选 provider 不可用，降级到 %s", name)
                all_urls.extend(urls)
                found = True
                break
        if found:
            continue
        try:
            urls = await poll_fn(iter_seed)
        except Exception:
            urls = []
        if not urls:
            return all_urls, True, meta
        winning_fn = poll_fn
        meta["provider"] = "pollinations"
        is_fb = True
        all_urls.extend(urls)

    return all_urls, is_fb, meta
