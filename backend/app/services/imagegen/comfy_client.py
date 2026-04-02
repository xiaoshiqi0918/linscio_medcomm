"""
ComfyUI HTTP API 客户端
- 本地：POST {base}/prompt，无鉴权
- Comfy Cloud：POST {base}/api/prompt，Header: X-API-Key
"""
from __future__ import annotations

import asyncio
import copy
import json
import uuid
from pathlib import Path
from typing import Any, Literal

import httpx

Mode = Literal["local", "cloud"]


def _api_prefix(base_url: str, mode: Mode) -> str:
    b = base_url.rstrip("/")
    if mode == "cloud":
        return f"{b}/api"
    return b


def _patch_ksampler(
    workflow: dict[str, Any],
    node_id: str,
    *,
    seed: int | None = None,
    steps: int | None = None,
    cfg: float | None = None,
    sampler_name: str | None = None,
) -> dict[str, Any]:
    w = copy.deepcopy(workflow)
    node = w.get(node_id)
    if not isinstance(node, dict):
        return workflow
    inputs = node.setdefault("inputs", {})
    if seed is not None:
        inputs["seed"] = int(seed)
    if steps is not None:
        inputs["steps"] = int(steps)
    if cfg is not None:
        inputs["cfg"] = float(cfg)
    if sampler_name and sampler_name.strip():
        inputs["sampler_name"] = sampler_name.strip()
    return w


def _inject_prompt(
    workflow: dict[str, Any],
    node_id: str,
    input_key: str,
    text: str,
) -> dict[str, Any]:
    w = copy.deepcopy(workflow)
    node = w.get(node_id)
    if not isinstance(node, dict):
        raise ValueError(f"工作流中不存在节点 {node_id!r}，请检查 COMFYUI_PROMPT_NODE_ID")
    inputs = node.setdefault("inputs", {})
    if input_key in inputs:
        inputs[input_key] = text
    elif input_key == "text" and "string" in inputs:
        inputs["string"] = text
    else:
        inputs[input_key] = text
    return w


async def submit_and_wait_image(
    *,
    positive_prompt: str,
    mode: Mode,
    base_url: str | None,
    api_key: str | None,
    workflow_path: str,
    prompt_node_id: str,
    prompt_input_key: str = "text",
    negative_prompt: str | None = None,
    negative_node_id: str | None = None,
    negative_input_key: str = "text",
    ksampler_node_id: str | None = None,
    seed: int | None = None,
    steps: int | None = None,
    cfg: float | None = None,
    sampler_name: str | None = None,
    timeout_sec: int = 300,
    poll_interval: float = 1.0,
) -> bytes:
    """
    提交工作流，轮询 history，下载第一张输出图（PNG）。
    """
    base = (base_url or "").strip()
    if not base:
        base = "https://cloud.comfy.org" if mode == "cloud" else "http://127.0.0.1:8188"
    prefix = _api_prefix(base, mode)
    path = Path(workflow_path).expanduser()
    if not path.is_file():
        raise FileNotFoundError(f"工作流文件不存在: {path}")

    workflow = json.loads(path.read_text(encoding="utf-8"))
    workflow = _inject_prompt(workflow, prompt_node_id, prompt_input_key, positive_prompt)
    neg = (negative_prompt or "").strip()
    nid = (negative_node_id or "").strip()
    if neg and nid:
        workflow = _inject_prompt(workflow, nid, negative_input_key, neg)
    kid = (ksampler_node_id or "").strip()
    if kid and (
        any(x is not None for x in (seed, steps, cfg))
        or bool((sampler_name or "").strip())
    ):
        workflow = _patch_ksampler(
            workflow,
            kid,
            seed=seed,
            steps=steps,
            cfg=cfg,
            sampler_name=(sampler_name or "").strip() or None,
        )

    client_id = str(uuid.uuid4())
    body = {"prompt": workflow, "client_id": client_id}

    headers: dict[str, str] = {"Content-Type": "application/json"}
    if mode == "cloud" and api_key:
        headers["X-API-Key"] = api_key.strip()

    timeout = httpx.Timeout(timeout_sec, connect=30.0)

    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        r = await client.post(f"{prefix}/prompt", json=body, headers=headers)
        if r.status_code >= 400:
            detail = r.text[:500] if r.text else r.status_code
            raise RuntimeError(f"ComfyUI 提交失败 HTTP {r.status_code}: {detail}")
        data = r.json()
        if data.get("node_errors"):
            raise RuntimeError(f"ComfyUI 工作流校验错误: {data['node_errors']}")
        prompt_id = data.get("prompt_id")
        if not prompt_id:
            raise RuntimeError(f"ComfyUI 未返回 prompt_id: {data}")

        hist = await _poll_history(client, prefix, prompt_id, timeout_sec, poll_interval)
        images = _collect_output_images(hist, prompt_id)
        if not images:
            raise RuntimeError("ComfyUI 完成但未找到输出图像，请检查工作流是否包含 SaveImage 或类似输出节点")

        img = images[0]
        params = {
            "filename": img["filename"],
            "subfolder": img.get("subfolder", ""),
            "type": img.get("type", "output"),
        }
        vr = await client.get(f"{prefix}/view", params=params)
        vr.raise_for_status()
        return vr.content


async def _poll_history(
    client: httpx.AsyncClient,
    prefix: str,
    prompt_id: str,
    timeout_sec: int,
    poll_interval: float,
) -> dict[str, Any]:
    loop = asyncio.get_event_loop()
    deadline = loop.time() + timeout_sec
    last_err: str | None = None
    while loop.time() < deadline:
        try:
            hr = await client.get(f"{prefix}/history/{prompt_id}")
            if hr.status_code == 200:
                j = hr.json()
                if not isinstance(j, dict):
                    await asyncio.sleep(poll_interval)
                    continue
                # 格式 A：{ prompt_id: { outputs: ... } }
                if prompt_id in j and isinstance(j[prompt_id], dict):
                    entry = j[prompt_id]
                    if entry.get("outputs"):
                        return {prompt_id: entry}
                # 格式 B：直接返回单条 { outputs: ... }
                if j.get("outputs"):
                    return {prompt_id: j}
            elif hr.status_code != 404:
                last_err = f"history HTTP {hr.status_code}"
        except Exception as e:
            last_err = str(e)
        await asyncio.sleep(poll_interval)
    raise TimeoutError(last_err or f"ComfyUI 执行超时（{timeout_sec}s），prompt_id={prompt_id}")


def _collect_output_images(history: dict[str, Any], prompt_id: str) -> list[dict[str, Any]]:
    entry = history.get(prompt_id) or {}
    out: list[dict[str, Any]] = []
    outputs = entry.get("outputs") or {}
    for _nid, node_out in outputs.items():
        if not isinstance(node_out, dict):
            continue
        for img in node_out.get("images") or []:
            if isinstance(img, dict) and img.get("filename"):
                out.append(img)
    return out
