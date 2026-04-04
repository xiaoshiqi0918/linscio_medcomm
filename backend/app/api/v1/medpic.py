"""
MedPic 医学绘图模块 API
- POST /build-prompt           服务端提示词拼装
- POST /compose                排版叠字合成
- GET  /variants               工作流变体列表
- GET  /layouts                获取场景排版模板列表
- GET  /workflow/{variant_id}  获取 ComfyUI UI 格式工作流 JSON
- POST /reference-image        上传角色参考图（B-2）
- GET  /reference-images       参考图列表
- POST /upscale                高分辨率放大（D-2）
- POST /stitch                 长图拼接（F-*）
- POST /long-segments          长图分段提示词生成
- GET  /model-registry         模型注册表（§8.1）
- GET  /lora-registry          LoRA 注册表（§8.2）
- POST /history                保存生成记录
- GET  /history                获取生成历史
- DELETE /history/{id}         删除生成记录
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import json as _json

from fastapi import APIRouter, HTTPException, UploadFile, File, Query, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select, delete as sa_delete, func as sa_func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_session

router = APIRouter()


# ─── §8.1 基底模型注册表 ───

@dataclass
class ModelEntry:
    id: str
    name: str
    arch: str                      # "sd15" | "sdxl" | "flux"
    filename: str                  # e.g. "sd_xl_base_1.0.safetensors"
    license: str                   # e.g. "CreativeML Open RAIL++-M"
    license_commercial: bool       # 是否允许商用
    license_redistribute: bool     # 是否允许二次分发
    size_gb: float
    tiers: list[str]               # 适用档位 ["low"] / ["standard","high"]
    style_bias: str                # "realistic_illustration" | "anime" | "general"
    tested_resolutions: list[str]  # 已实测分辨率 ["1024x1024","768x1344"]
    notes: str = ""


MODEL_REGISTRY: list[ModelEntry] = [
    ModelEntry(
        id="sd15-realistic",
        name="Stable Diffusion 1.5（写实插画融合）",
        arch="sd15",
        filename="v1-5-pruned-emaonly.safetensors",
        license="CreativeML Open RAIL-M",
        license_commercial=True,
        license_redistribute=True,
        size_gb=2.0,
        tiers=["low"],
        style_bias="realistic_illustration",
        tested_resolutions=["512x512", "768x768", "768x512", "512x768"],
        notes="低配基础模型，兼顾医学插画与扁平风格",
    ),
    ModelEntry(
        id="sdxl-base",
        name="SDXL Base 1.0",
        arch="sdxl",
        filename="sd_xl_base_1.0.safetensors",
        license="CreativeML Open RAIL++-M",
        license_commercial=True,
        license_redistribute=True,
        size_gb=6.5,
        tiers=["standard", "high"],
        style_bias="realistic_illustration",
        tested_resolutions=[
            "1024x1024", "768x1024", "1024x768",
            "768x1344", "1344x768", "1024x1448", "1344x672",
        ],
        notes="标准/高配主力模型，广泛兼容所有风格 LoRA",
    ),
    ModelEntry(
        id="flux-schnell",
        name="Flux.1 schnell",
        arch="flux",
        filename="flux1-schnell-fp8.safetensors",
        license="Apache 2.0",
        license_commercial=True,
        license_redistribute=True,
        size_gb=24.0,
        tiers=["high"],
        style_bias="general",
        tested_resolutions=["1024x1024", "768x1344", "1344x768"],
        notes="高配可选升级模型，需 24GB 显存，暂未启用",
    ),
]

MODEL_BY_ID: dict[str, ModelEntry] = {m.id: m for m in MODEL_REGISTRY}
TIER_MODEL_MAP: dict[str, str] = {
    "low": "sd15-realistic",
    "standard": "sdxl-base",
    "high": "sdxl-base",
}


# ─── §8.2 LoRA 注册表 ───

@dataclass
class LoraEntry:
    id: str
    name: str
    category: str               # "style" | "subject" | "kids" | "character"
    filename: str               # e.g. "medpic_style_illustration_xl.safetensors"
    arch: str                   # "sd15" | "sdxl"
    weight_range: tuple[float, float]
    default_weight: float
    tiers: list[str]            # 适用档位
    trigger_words: str = ""     # 触发词（追加到正向提示词）
    auto_select_styles: list[str] = field(default_factory=list)   # 匹配哪些风格自动启用
    auto_select_scenes: list[str] = field(default_factory=list)   # 匹配哪些场景自动启用
    is_base_pack: bool = True   # True=基础包随附, False=进阶包
    notes: str = ""


LORA_REGISTRY: list[LoraEntry] = [
    # ── 风格 LoRA ──
    LoraEntry(
        id="medpic_style_illustration_xl",
        name="医学插画风格（XL）",
        category="style",
        filename="medpic_style_illustration_xl.safetensors",
        arch="sdxl",
        weight_range=(0.5, 0.7),
        default_weight=0.6,
        tiers=["standard", "high"],
        trigger_words="medpic illustration style",
        auto_select_styles=["medical_illustration"],
    ),
    LoraEntry(
        id="medpic_style_flat_xl",
        name="扁平信息图风格（XL）",
        category="style",
        filename="medpic_style_flat_xl.safetensors",
        arch="sdxl",
        weight_range=(0.5, 0.7),
        default_weight=0.6,
        tiers=["standard", "high"],
        trigger_words="medpic flat design style",
        auto_select_styles=["flat_design"],
    ),
    LoraEntry(
        id="medpic_style_illustration_15",
        name="医学插画风格（SD1.5）",
        category="style",
        filename="medpic_style_illustration_15.safetensors",
        arch="sd15",
        weight_range=(0.5, 0.7),
        default_weight=0.6,
        tiers=["low"],
        trigger_words="medpic illustration style",
        auto_select_styles=["medical_illustration", "flat_design"],
    ),
    # ── 题材 LoRA ──
    LoraEntry(
        id="medpic_lineart_xl",
        name="线稿/示意图框架（XL）",
        category="subject",
        filename="medpic_lineart_xl.safetensors",
        arch="sdxl",
        weight_range=(0.3, 0.5),
        default_weight=0.4,
        tiers=["standard", "high"],
        trigger_words="medpic lineart diagram",
        auto_select_styles=["flat_design"],
        auto_select_scenes=["card", "longimage", "ppt"],
    ),
    LoraEntry(
        id="medpic_anatomy_xl",
        name="解剖结构准确性（XL）",
        category="subject",
        filename="medpic_anatomy_xl.safetensors",
        arch="sdxl",
        weight_range=(0.3, 0.5),
        default_weight=0.4,
        tiers=["standard", "high"],
        trigger_words="medpic anatomical precision",
        auto_select_styles=["medical_illustration", "3d_render"],
        auto_select_scenes=["article"],
    ),
    # ── 儿向 LoRA ──
    LoraEntry(
        id="medpic_kids_xl",
        name="儿科/绘本卡通风格（XL）",
        category="kids",
        filename="medpic_kids_xl.safetensors",
        arch="sdxl",
        weight_range=(0.5, 0.7),
        default_weight=0.6,
        tiers=["standard", "high"],
        trigger_words="medpic kids friendly cartoon",
        auto_select_styles=["comic", "picture_book"],
        auto_select_scenes=["picturebook", "comic"],
        is_base_pack=False,
        notes="进阶包：儿科专用绘本卡通风格",
    ),
    # ── 角色 LoRA（模板条目，实际角色 LoRA 通过包管理动态加载）──
    LoraEntry(
        id="medpic_character_template",
        name="角色 LoRA（模板）",
        category="character",
        filename="",
        arch="sdxl",
        weight_range=(0.4, 0.7),
        default_weight=0.55,
        tiers=["standard", "high"],
        is_base_pack=False,
        notes="角色 LoRA 通过绘图扩展包动态注册",
    ),
]

LORA_BY_ID: dict[str, LoraEntry] = {l.id: l for l in LORA_REGISTRY}


def select_loras(
    arch: str,
    style: str,
    scene: str,
    tier: str,
    audience: str = "",
    lora_overrides: dict[str, float] | None = None,
) -> list[tuple[LoraEntry, float]]:
    """
    根据架构/风格/场景/档位自动选择合适的 LoRA 及权重。
    返回 [(LoraEntry, strength), ...] — 按 style → subject → kids 排序。
    lora_overrides: 用户在高级模式中手动指定的 {lora_id: strength}，None 跳过该 LoRA。
    """
    overrides = lora_overrides or {}
    candidates: list[tuple[LoraEntry, float, int]] = []  # (entry, weight, priority)

    for lora in LORA_REGISTRY:
        if lora.arch != arch:
            continue
        if tier not in lora.tiers:
            continue
        if not lora.filename:
            continue

        if lora.id in overrides:
            w = overrides[lora.id]
            if w <= 0:
                continue
            candidates.append((lora, w, _category_priority(lora.category)))
            continue

        score = 0
        if lora.auto_select_styles and style in lora.auto_select_styles:
            score += 2
        if lora.auto_select_scenes and scene in lora.auto_select_scenes:
            score += 1
        if lora.category == "kids" and audience == "children":
            score += 2

        if score > 0:
            candidates.append((lora, lora.default_weight, _category_priority(lora.category)))

    candidates.sort(key=lambda x: x[2])
    return [(e, w) for e, w, _ in candidates]


def _category_priority(cat: str) -> int:
    return {"style": 0, "subject": 1, "kids": 2, "character": 3}.get(cat, 9)


# ─── 提示词拼装 ───

QUALITY_BASE = (
    "masterpiece, best quality, highly detailed, professional, "
    "sharp focus, 8k uhd, high resolution, clean composition"
)

SAFETY_NEGATIVE = (
    "nsfw, gore, blood, graphic surgery, disturbing imagery, horror, "
    "scary medical content, low quality, blurry, jpeg artifacts, watermark, "
    "deformed, bad anatomy, gibberish text, illegible labels, oversaturated, "
    "extra limbs, mutation, ugly, worst quality, lowres, normal quality, "
    "cropped, out of frame, duplicate, morbid, mutilated, poorly drawn, "
    "text, signature, username, artist name"
)

SPECIALTY_PROMPT: dict[str, str] = {
    "心内科": "cardiology, heart anatomy, cardiovascular",
    "呼吸内科": "pulmonology, respiratory system, lung anatomy",
    "消化内科": "gastroenterology, digestive system",
    "神经内科": "neurology, brain anatomy, nervous system",
    "内分泌科": "endocrinology, metabolic system, hormonal, blood sugar, insulin, healthy diet",
    "普外科": "surgical procedure, anatomical precision",
    "骨科": "orthopedics, skeletal anatomy, musculoskeletal",
    "泌尿外科": "urology, urinary system",
    "心外科": "cardiac surgery, heart anatomy",
    "神经外科": "neurosurgery, brain anatomy",
    "妇产科": "obstetrics, gynecology, maternal health",
    "儿科": "pediatrics, child-friendly, gentle colors",
    "眼科": "ophthalmology, eye anatomy, vision care",
    "耳鼻喉科": "otolaryngology, ENT, ear nose throat",
    "口腔科": "dental, oral health, dentistry",
    "皮肤科": "dermatology, skin health, medical illustration",
    "肿瘤科": "oncology, cancer awareness, medical illustration",
    "急诊科": "emergency medicine, first aid illustration",
    "重症医学科": "critical care, ICU, intensive care",
    "康复科": "rehabilitation, physical therapy",
    "影像科": "medical imaging, diagnostic illustration",
    "检验科": "laboratory medicine, diagnostic testing",
    "病理科": "pathology, histology, microscopy",
    "药学部": "pharmaceutical, medication guide",
    "护理部": "nursing care, patient comfort",
    "中医科": "traditional chinese medicine, herbs, meridian",
    "全科医学": "general practice, family medicine",
    "精神科": "psychiatry, mental health, wellness",
    "感染科": "infectious disease, microbiology",
    "老年医学科": "geriatrics, elderly care, aging",
}

STYLE_PROMPT: dict[str, str] = {
    "medical_illustration": "professional medical illustration, realistic style, detailed, clean lines, white background, educational diagram",
    "flat_design": "flat design, minimalist, clean vector style, infographic, simple shapes, bold colors",
    "3d_render": "3D render, volumetric lighting, medical visualization, soft studio lighting",
    "comic": "cartoon style, friendly, colorful, health education",
    "picture_book": "picture book illustration, soft watercolor, warm, child-friendly, storybook art",
}

COLOR_TONE_PROMPT: dict[str, str] = {
    "warm": "warm color palette, golden tones",
    "cool": "cool color palette, blue tones, clinical",
    "neutral": "balanced color palette, professional tones",
}

AUDIENCE_PROMPT: dict[str, str] = {
    "public": "patient education, accessible, easy to understand",
    "professional": "clinical accuracy, professional medical context",
    "children": "child-friendly, cute, gentle, bright colors, no scary elements",
}

SCENE_COMPOSITION: dict[str, str] = {
    "article": "clean background, centered subject, educational illustration",
    "comic": "comic panel, single scene, speech bubble area, cartoon style",
    "card": "clean background at bottom for text, minimalist composition, knowledge card",
    "poster": "large clear area at top for title text, centered subject, poster layout",
    "picturebook": "picture book illustration, warm atmosphere, child-friendly",
    "longimage": "white space sections between content blocks, infographic segment",
    "ppt": "left side clear for text overlay, subject on right, presentation slide",
}

SCENE_DEFAULTS: dict[str, dict] = {
    "article":     {"style": "medical_illustration", "aspect": "1:1"},
    "comic":       {"style": "comic",                "aspect": "1:1"},
    "card":        {"style": "flat_design",           "aspect": "1:1"},
    "poster":      {"style": "medical_illustration",  "aspect": "9:16"},
    "picturebook": {"style": "picture_book",          "aspect": "3:4"},
    "longimage":   {"style": "flat_design",           "aspect": "1:1"},
    "ppt":         {"style": "medical_illustration",  "aspect": "16:9"},
}


# ─── 工作流变体目录（§5.2） ───

class WorkflowVariant:
    __slots__ = (
        "id", "scene", "name", "description", "style", "aspects",
        "composition", "tier_exclude", "special",
        "latent_size", "output_size", "process",
        "supports_character",
    )

    def __init__(
        self,
        id: str,
        scene: str,
        name: str,
        description: str,
        style: str,
        aspects: list[str],
        composition: str,
        tier_exclude: list[str] | None = None,
        special: str | None = None,
        latent_size: tuple[int, int] | None = None,
        output_size: tuple[int, int] | None = None,
        process: str = "direct",
        supports_character: bool = False,
    ):
        self.id = id
        self.scene = scene
        self.name = name
        self.description = description
        self.style = style
        self.aspects = aspects
        self.composition = composition
        self.tier_exclude = tier_exclude or []
        self.special = special
        self.latent_size = latent_size
        self.output_size = output_size
        self.process = process
        self.supports_character = supports_character or special == "character_consistency"


WORKFLOW_VARIANTS: list[WorkflowVariant] = [
    # ── A：科普文章插图（直出） ──
    WorkflowVariant(
        id="A-1", scene="article", name="写实医学插画",
        description="适合外科、影像、病理等专业性强的科室",
        style="medical_illustration", aspects=["1:1", "4:3"],
        composition="clean background, centered subject, anatomical precision, educational medical illustration",
        latent_size=(1024, 1024), output_size=(1024, 1024), process="direct",
    ),
    WorkflowVariant(
        id="A-2", scene="article", name="扁平示意图",
        description="适合内科、儿科、科普向内容，清晰易读",
        style="flat_design", aspects=["1:1", "4:3"],
        composition="flat design diagram, clean vector style, labeled parts, infographic layout, medical education",
        latent_size=(1024, 1024), output_size=(1024, 1024), process="direct",
    ),
    WorkflowVariant(
        id="A-3", scene="article", name="3D 渲染示意",
        description="适合解剖结构、器官说明、手术流程示意",
        style="3d_render", aspects=["1:1", "4:3"],
        composition="3D medical visualization, anatomical cross-section, volumetric rendering, organ structure",
        latent_size=(1024, 1024), output_size=(1024, 1024), process="direct",
    ),

    # ── B：条漫科普 ──
    WorkflowVariant(
        id="B-1", scene="comic", name="单格独立图",
        description="无角色连贯性要求，单张场景图",
        style="comic", aspects=["1:1"],
        composition="single comic panel, self-contained scene, cartoon medical illustration, speech bubble area",
        latent_size=(1024, 1024), output_size=(1080, 1080), process="upscale",
    ),
    WorkflowVariant(
        id="B-2", scene="comic", name="多格连续叙事",
        description="需角色一致性，分段生成后拼接（低配不支持）",
        style="comic", aspects=["1:1"],
        composition="comic strip panel, consistent character design, sequential narrative, storytelling",
        tier_exclude=["low"], special="character_consistency",
        latent_size=(768, 768), output_size=None, process="segmented",
    ),
    WorkflowVariant(
        id="B-3", scene="comic", name="信息图叙事",
        description="以信息图形式呈现知识点，无需角色",
        style="flat_design", aspects=["1:1"],
        composition="infographic narrative, step-by-step visual guide, numbered sections, knowledge flow",
        latent_size=(1024, 1024), output_size=(1080, 1080), process="upscale",
    ),

    # ── C：知识卡片（放大） ──
    WorkflowVariant(
        id="C-1", scene="card", name="方形卡片",
        description="适配小红书/朋友圈/公告栏",
        style="flat_design", aspects=["1:1"],
        composition="square knowledge card, clean lower area for text, minimalist, social media ready",
        latent_size=(1024, 1024), output_size=(1080, 1080), process="upscale",
    ),
    WorkflowVariant(
        id="C-2", scene="card", name="竖版卡片",
        description="适配微信推文竖版配图",
        style="flat_design", aspects=["3:4"],
        composition="vertical card layout, upper image lower text area, mobile-friendly, WeChat style",
        latent_size=(768, 1024), output_size=(1080, 1440), process="upscale",
    ),
    WorkflowVariant(
        id="C-3", scene="card", name="横版卡片",
        description="适配公众号内文配图/PPT内嵌",
        style="flat_design", aspects=["16:9"],
        composition="horizontal card, left visual right text area, widescreen composition, banner style",
        latent_size=(1344, 768), output_size=(1920, 1080), process="upscale",
    ),

    # ── D：科普海报 ──
    WorkflowVariant(
        id="D-1", scene="poster", name="线上手机海报",
        description="用于微信、朋友圈、公众号推广",
        style="medical_illustration", aspects=["9:16"],
        composition="mobile poster, large title area at top, centered subject, call-to-action area at bottom",
        latent_size=(768, 1344), output_size=(1080, 1920), process="upscale",
    ),
    WorkflowVariant(
        id="D-2", scene="poster", name="线下印刷海报",
        description="高分辨率输出，院内张贴（低配不建议）",
        style="medical_illustration", aspects=["3:4"],
        composition="print-quality poster, high detail, clean margins, large title area at top, professional hospital poster layout",
        tier_exclude=["low"], special="high_dpi",
        latent_size=(1024, 1448), output_size=None, process="upscale_hd",
    ),
    WorkflowVariant(
        id="D-3", scene="poster", name="横版宣传图",
        description="用于官网Banner、大屏展示",
        style="medical_illustration", aspects=["16:9"],
        composition="wide banner, hero image, horizontal promotion layout, website banner style",
        latent_size=(1344, 768), output_size=(1920, 1080), process="upscale",
    ),

    # ── E：科普绘本（直出） ──
    WorkflowVariant(
        id="E-1", scene="picturebook", name="封面页",
        description="竖版封面，风格鲜明，可选角色一致性",
        style="picture_book", aspects=["3:4"],
        composition="picture book cover, bold title area, whimsical character, warm inviting atmosphere",
        latent_size=(768, 1024), output_size=(768, 1024), process="direct",
        supports_character=True,
    ),
    WorkflowVariant(
        id="E-2", scene="picturebook", name="内页（含文字区）",
        description="图像区+留白文字区，横版排布，可选角色一致性",
        style="picture_book", aspects=["4:3"],
        composition="picture book interior spread, left side illustration right side blank for text, soft background",
        latent_size=(1024, 768), output_size=(1024, 768), process="direct",
        supports_character=True,
    ),
    WorkflowVariant(
        id="E-3", scene="picturebook", name="跨页大图",
        description="宽幅场景图，高情绪感染力，可选角色一致性",
        style="picture_book", aspects=["2:1"],
        composition="panoramic picture book spread, wide scene, emotional landscape, immersive storybook illustration",
        latent_size=(1344, 672), output_size=(1344, 672), process="direct",
        supports_character=True,
    ),

    # ── F：竖版长图（分段拼接） ──
    WorkflowVariant(
        id="F-1", scene="longimage", name="信息流长图",
        description="适配小红书/微博长图，色彩丰富",
        style="flat_design", aspects=["1:1"],
        composition="infographic segment, colorful data block, social media long-form segment, vibrant",
        special="segmented",
        latent_size=(1024, 1024), output_size=None, process="segmented",
    ),
    WorkflowVariant(
        id="F-2", scene="longimage", name="公众号长图",
        description="适配微信公众号，需分段切片上传",
        style="flat_design", aspects=["1:1"],
        composition="WeChat article segment, clean white sections between content, text-friendly layout",
        special="segmented",
        latent_size=(1024, 1024), output_size=None, process="segmented",
    ),
    WorkflowVariant(
        id="F-3", scene="longimage", name="知识图谱型",
        description="结构化知识展示，偏信息图风格",
        style="flat_design", aspects=["1:1"],
        composition="knowledge graph segment, structured layout, connecting lines, hierarchical information",
        special="segmented",
        latent_size=(1024, 1024), output_size=None, process="segmented",
    ),

    # ── G：PPT 展示图 ──
    WorkflowVariant(
        id="G-1", scene="ppt", name="16:9 单主体图",
        description="主体突出，适合全屏 PPT 背景图或插图",
        style="medical_illustration", aspects=["16:9"],
        composition="single subject centered, presentation slide background, clean space for overlaid text",
        latent_size=(1344, 768), output_size=(1920, 1080), process="upscale",
    ),
    WorkflowVariant(
        id="G-2", scene="ppt", name="16:9 信息图",
        description="含多元素布局，直接作为数据/流程 PPT 页使用",
        style="flat_design", aspects=["16:9"],
        composition="infographic slide, multi-element layout, clear text overlay area, process flow diagram, data visualization style",
        latent_size=(1344, 768), output_size=(1920, 1080), process="upscale",
    ),
    WorkflowVariant(
        id="G-3", scene="ppt", name="4:3 兼容版",
        description="老版 PPT 或某些投影设备兼容格式",
        style="medical_illustration", aspects=["4:3"],
        composition="4:3 presentation slide, traditional format, compatible layout, centered composition",
        latent_size=(1024, 768), output_size=(1024, 768), process="direct",
    ),
]

VARIANT_MAP: dict[str, WorkflowVariant] = {v.id: v for v in WORKFLOW_VARIANTS}
SCENE_VARIANT_MAP: dict[str, list[WorkflowVariant]] = {}
for _v in WORKFLOW_VARIANTS:
    SCENE_VARIANT_MAP.setdefault(_v.scene, []).append(_v)

TIER_CONFIG: dict[str, dict] = {
    "low":      {"steps": 30, "cfg": 7.5, "sampler": "euler",     "scheduler": "normal", "scale": 0.5, "workflow": "sd15"},
    "standard": {"steps": 28, "cfg": 7.0, "sampler": "euler",     "scheduler": "normal", "scale": 1.0,  "workflow": "sdxl"},
    "high":     {"steps": 28, "cfg": 7.0, "sampler": "dpmpp_2m",  "scheduler": "karras", "scale": 1.0,  "workflow": "sdxl"},
}

ASPECT_BASE_SIZE: dict[str, tuple[int, int]] = {
    "1:1":  (1024, 1024),
    "4:3":  (1024, 768),
    "3:4":  (768, 1024),
    "16:9": (1344, 768),
    "9:16": (768, 1344),
    "2:1":  (1344, 672),
}


# ─── §7.4 推荐种子库 ───
# 每个「场景 × 风格」组合维护一组调优种子，保证稳定出图质量。
# 随模型包版本迭代更新（v1.0 初始种子集）。

SEED_LIBRARY_VERSION = "1.0"

RECOMMENDED_SEEDS: dict[str, list[int]] = {
    "article:medical_illustration":  [42, 1337, 2024, 8888, 12345],
    "article:flat_design":           [100, 256, 512, 1024, 2048],
    "article:3d_render":             [77, 333, 999, 1500, 3000],
    "comic:comic":                   [55, 404, 808, 1111, 5555],
    "comic:flat_design":             [128, 384, 768, 1536, 3072],
    "card:flat_design":              [60, 180, 360, 720, 1440],
    "poster:medical_illustration":   [88, 168, 888, 1688, 8168],
    "picturebook:picture_book":      [7, 14, 21, 28, 35],
    "longimage:flat_design":         [200, 400, 600, 800, 1000],
    "ppt:medical_illustration":      [16, 32, 64, 96, 160],
    "ppt:flat_design":               [48, 144, 288, 576, 1152],
}


def get_recommended_seed(scene: str, style: str, index: int = 0) -> int | None:
    """从推荐种子库中获取种子。返回 None 表示库中无匹配。"""
    key = f"{scene}:{style}"
    seeds = RECOMMENDED_SEEDS.get(key)
    if not seeds:
        return None
    return seeds[index % len(seeds)]


def _round_to_8(val: float) -> int:
    """Round to nearest multiple of 8 (ComfyUI latent space requirement)."""
    return max(8, round(val / 8) * 8)


class LoraOverrideItem(BaseModel):
    id: str
    strength: float


class BuildPromptRequest(BaseModel):
    scene: str
    topic: str
    variant: str = ""
    specialty: str = ""
    target_audience: str = "public"
    style: str = ""
    color_tone: str = "neutral"
    subject: str = ""
    extra_prompt: str = ""
    hardware_tier: str = "standard"
    aspect: str = ""
    reference_image: str = ""
    ipadapter_weight: float = 0.7
    character_preset: str = ""
    segment_index: int | None = None
    segment_count: int | None = None
    seed_mode: str = "recommended"
    lora_overrides: list[LoraOverrideItem] | None = None


class LoraUsedItem(BaseModel):
    id: str
    name: str
    category: str
    filename: str
    strength: float


class BuildPromptResponse(BaseModel):
    positive_prompt: str
    negative_prompt: str
    width: int
    height: int
    steps: int
    cfg_scale: float
    sampler_name: str
    scheduler: str
    workflow_path: str
    special: str | None = None
    reference_image: str | None = None
    output_width: int | None = None
    output_height: int | None = None
    process_mode: str = "direct"
    recommended_seed: int | None = None
    seed_library_version: str = SEED_LIBRARY_VERSION
    loras: list[LoraUsedItem] = []
    model_id: str = ""
    ipadapter_weight: float | None = None


@router.post("/build-prompt", response_model=BuildPromptResponse)
async def build_prompt(req: BuildPromptRequest):
    scene_def = SCENE_DEFAULTS.get(req.scene)
    if not scene_def:
        raise HTTPException(400, f"未知场景: {req.scene}")

    tier = TIER_CONFIG.get(req.hardware_tier, TIER_CONFIG["standard"])

    variant = VARIANT_MAP.get(req.variant) if req.variant else None
    if variant and req.hardware_tier in variant.tier_exclude:
        raise HTTPException(
            400,
            f"工作流 {variant.id}（{variant.name}）不支持当前硬件档位，请升级配置或选择其他工作流",
        )

    style = req.style or (variant.style if variant else scene_def["style"])
    aspect = req.aspect or (variant.aspects[0] if variant else scene_def["aspect"])
    composition = variant.composition if variant else SCENE_COMPOSITION.get(req.scene, "")

    # §7.2 提示词拼装顺序：画质底词 → 风格词 → 科普场景通用词 → 用户主体描述 → 科室映射词 → 色调构图词
    parts: list[str] = [QUALITY_BASE]
    parts.append(STYLE_PROMPT.get(style, STYLE_PROMPT["medical_illustration"]))
    parts.append(composition)

    if req.topic.strip():
        parts.append(req.topic.strip())
    if req.subject.strip():
        parts.append(req.subject.strip())

    sp = SPECIALTY_PROMPT.get(req.specialty)
    if sp:
        parts.append(sp)

    parts.append(AUDIENCE_PROMPT.get(req.target_audience, ""))
    parts.append(COLOR_TONE_PROMPT.get(req.color_tone, ""))
    parts.append("health education")

    if req.character_preset:
        preset_char = PRESET_BY_ID.get(req.character_preset)
        if preset_char and preset_char.prompt_tags:
            parts.append(preset_char.prompt_tags)

    if req.extra_prompt.strip():
        parts.append(req.extra_prompt.strip())

    positive = ", ".join(p for p in parts if p)

    neg_parts = [SAFETY_NEGATIVE]
    if req.target_audience == "children":
        neg_parts.append("realistic blood, needles, sharp objects, crying child")
    negative = ", ".join(neg_parts)

    if variant and variant.latent_size:
        base_w, base_h = variant.latent_size
    else:
        base_w, base_h = ASPECT_BASE_SIZE.get(aspect, (1024, 1024))

    scale = tier["scale"]
    w = _round_to_8(base_w * scale)
    h = _round_to_8(base_h * scale)

    special = variant.special if variant else None
    process_mode = variant.process if variant else "direct"
    ref_img: str | None = None

    out_w: int | None = None
    out_h: int | None = None
    if variant and variant.output_size:
        out_w, out_h = variant.output_size

    use_ipadapter = (
        tier["workflow"] == "sdxl"
        and req.reference_image
        and variant is not None
        and variant.supports_character
    )
    if use_ipadapter:
        wf = "workflows/comfyui/medcomm_t2i_sdxl_ipadapter.api.json"
        ref_img = req.reference_image
    else:
        wf = f"workflows/comfyui/medcomm_t2i_{tier['workflow']}.api.json"

    if special == "segmented" and req.segment_index is not None and req.segment_count:
        from app.services.medpic.longimage import generate_segment_prompts
        seg_prompts = generate_segment_prompts(
            req.topic, req.segment_count, composition,
        )
        idx = min(req.segment_index, len(seg_prompts) - 1)
        positive = f"{positive}, {seg_prompts[idx]}"

    rec_seed: int | None = None
    if req.seed_mode == "recommended":
        rec_seed = get_recommended_seed(req.scene, style)

    # §8.2 LoRA 自动选择
    arch = tier["workflow"]  # "sd15" | "sdxl"
    lora_override_map: dict[str, float] | None = None
    if req.lora_overrides:
        lora_override_map = {item.id: item.strength for item in req.lora_overrides}

    selected_loras = select_loras(
        arch=arch,
        style=style,
        scene=req.scene,
        tier=req.hardware_tier,
        audience=req.target_audience,
        lora_overrides=lora_override_map,
    )

    lora_items: list[LoraUsedItem] = []
    for lora_entry, strength in selected_loras:
        lora_items.append(LoraUsedItem(
            id=lora_entry.id,
            name=lora_entry.name,
            category=lora_entry.category,
            filename=lora_entry.filename,
            strength=strength,
        ))
        if lora_entry.trigger_words:
            positive = f"{positive}, {lora_entry.trigger_words}"

    model_id = TIER_MODEL_MAP.get(req.hardware_tier, "sdxl-base")

    ipa_weight: float | None = None
    if use_ipadapter:
        ipa_weight = max(0.1, min(1.0, req.ipadapter_weight))

    return BuildPromptResponse(
        positive_prompt=positive,
        negative_prompt=negative,
        width=w, height=h,
        steps=tier["steps"],
        cfg_scale=tier["cfg"],
        sampler_name=tier["sampler"],
        scheduler=tier["scheduler"],
        workflow_path=wf,
        special=special,
        reference_image=ref_img,
        output_width=out_w,
        output_height=out_h,
        process_mode=process_mode,
        ipadapter_weight=ipa_weight,
        recommended_seed=rec_seed,
        seed_library_version=SEED_LIBRARY_VERSION,
        loras=lora_items,
        model_id=model_id,
    )


# ─── AI 智能提示词 ───

class AIPromptRequest(BaseModel):
    description: str
    specialty: str = ""
    context_hint: str = ""
    stream: bool = False


class AIPromptRefineRequest(BaseModel):
    current_positive: str
    current_negative: str
    current_params: dict = {}
    instruction: str
    stream: bool = False


@router.post("/ai-prompt")
async def ai_generate_prompt(req: AIPromptRequest):
    """LLM 生成正/反向提示词 + 自动推荐参数。"""
    from app.services.medpic.prompt_agent import generate_prompt, generate_prompt_stream

    if not req.description.strip():
        raise HTTPException(400, "描述不能为空")

    if req.stream:
        async def event_stream():
            try:
                full = ""
                async for chunk in generate_prompt_stream(
                    req.description, req.specialty, req.context_hint,
                ):
                    full += chunk
                    yield f"data: {_json.dumps({'type': 'delta', 'text': chunk}, ensure_ascii=False)}\n\n"
                try:
                    from app.services.medpic.prompt_agent import _parse_response
                    parsed = _parse_response(full)
                    yield f"data: {_json.dumps({'type': 'done', 'result': parsed}, ensure_ascii=False)}\n\n"
                except Exception:
                    yield f"data: {_json.dumps({'type': 'done', 'raw': full}, ensure_ascii=False)}\n\n"
            except Exception as e:
                yield f"data: {_json.dumps({'type': 'error', 'message': str(e)}, ensure_ascii=False)}\n\n"

        return StreamingResponse(
            event_stream(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    try:
        result = await generate_prompt(req.description, req.specialty, req.context_hint)
        return result
    except Exception as e:
        raise HTTPException(500, f"提示词生成失败: {e}")


@router.post("/ai-prompt/refine")
async def ai_refine_prompt(req: AIPromptRefineRequest):
    """多轮优化：基于当前提示词 + 用户指令调整。"""
    from app.services.medpic.prompt_agent import refine_prompt, refine_prompt_stream

    if not req.instruction.strip():
        raise HTTPException(400, "调整指令不能为空")

    if req.stream:
        async def event_stream():
            try:
                full = ""
                async for chunk in refine_prompt_stream(
                    req.current_positive, req.current_negative,
                    req.current_params, req.instruction,
                ):
                    full += chunk
                    yield f"data: {_json.dumps({'type': 'delta', 'text': chunk}, ensure_ascii=False)}\n\n"
                try:
                    from app.services.medpic.prompt_agent import _parse_response
                    parsed = _parse_response(full)
                    yield f"data: {_json.dumps({'type': 'done', 'result': parsed}, ensure_ascii=False)}\n\n"
                except Exception:
                    yield f"data: {_json.dumps({'type': 'done', 'raw': full}, ensure_ascii=False)}\n\n"
            except Exception as e:
                yield f"data: {_json.dumps({'type': 'error', 'message': str(e)}, ensure_ascii=False)}\n\n"

        return StreamingResponse(
            event_stream(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    try:
        result = await refine_prompt(
            req.current_positive, req.current_negative,
            req.current_params, req.instruction,
        )
        return result
    except Exception as e:
        raise HTTPException(500, f"提示词优化失败: {e}")


# ─── 种子库查询 ───

@router.get("/seed-library")
async def seed_library(scene: str = "", style: str = ""):
    """查询推荐种子库。可按 scene 和/或 style 筛选。"""
    result = []
    for key, seeds in RECOMMENDED_SEEDS.items():
        s, st = key.split(":", 1)
        if scene and s != scene:
            continue
        if style and st != style:
            continue
        result.append({"scene": s, "style": st, "seeds": seeds})
    return {"version": SEED_LIBRARY_VERSION, "entries": result}


# ─── §8.1 模型注册表查询 ───

@router.get("/model-registry")
async def model_registry(tier: str = ""):
    """查询基底模型注册表。可按档位筛选。"""
    result = []
    for m in MODEL_REGISTRY:
        if tier and tier not in m.tiers:
            continue
        result.append({
            "id": m.id,
            "name": m.name,
            "arch": m.arch,
            "filename": m.filename,
            "license": m.license,
            "license_commercial": m.license_commercial,
            "license_redistribute": m.license_redistribute,
            "size_gb": m.size_gb,
            "tiers": m.tiers,
            "style_bias": m.style_bias,
            "tested_resolutions": m.tested_resolutions,
            "notes": m.notes,
        })
    return {"models": result, "tier_model_map": TIER_MODEL_MAP}


# ─── §8.2 LoRA 注册表查询 ───

@router.get("/lora-registry")
async def lora_registry(
    arch: str = "",
    category: str = "",
    tier: str = "",
):
    """查询 LoRA 注册表。可按 arch/category/tier 筛选。"""
    result = []
    for lr in LORA_REGISTRY:
        if arch and lr.arch != arch:
            continue
        if category and lr.category != category:
            continue
        if tier and tier not in lr.tiers:
            continue
        if not lr.filename:
            continue
        result.append({
            "id": lr.id,
            "name": lr.name,
            "category": lr.category,
            "filename": lr.filename,
            "arch": lr.arch,
            "weight_range": list(lr.weight_range),
            "default_weight": lr.default_weight,
            "tiers": lr.tiers,
            "trigger_words": lr.trigger_words,
            "auto_select_styles": lr.auto_select_styles,
            "auto_select_scenes": lr.auto_select_scenes,
            "is_base_pack": lr.is_base_pack,
            "notes": lr.notes,
        })
    return {"loras": result}


# ─── 排版叠字合成 ───

class ComposeRequest(BaseModel):
    image_path: str
    scene: str
    texts: dict[str, str]


class ComposeResponse(BaseModel):
    composed_path: str
    serve_url: str


@router.post("/compose", response_model=ComposeResponse)
async def compose(req: ComposeRequest):
    image_path = req.image_path
    if image_path.startswith("medcomm-image://"):
        image_path = image_path[len("medcomm-image://"):]

    if ".." in image_path or image_path.startswith("/"):
        raise HTTPException(400, "非法路径")

    if not req.texts or not any(v.strip() for v in req.texts.values()):
        raise HTTPException(400, "请至少提供一项文字内容")

    from app.services.typography.engine import compose_image

    try:
        rel = compose_image(
            base_image_path=image_path,
            scene_id=req.scene,
            texts=req.texts,
        )
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))
    except ValueError as e:
        raise HTTPException(400, str(e))

    return ComposeResponse(
        composed_path=f"medcomm-image://{rel}",
        serve_url=f"/api/v1/imagegen/serve?path={rel}",
    )


# ─── 工作流变体列表 ───

@router.get("/variants")
async def get_variants(scene: str | None = None, hardware_tier: str = "standard"):
    variants = WORKFLOW_VARIANTS
    if scene:
        variants = SCENE_VARIANT_MAP.get(scene, [])
    out = []
    for v in variants:
        available = hardware_tier not in v.tier_exclude
        out.append({
            "id": v.id,
            "scene": v.scene,
            "name": v.name,
            "description": v.description,
            "style": v.style,
            "aspects": v.aspects,
            "available": available,
            "tier_exclude": v.tier_exclude,
            "special": v.special,
            "latent_size": list(v.latent_size) if v.latent_size else None,
            "output_size": list(v.output_size) if v.output_size else None,
            "process": v.process,
            "supports_character": v.supports_character,
        })
    return {"variants": out}


# ─── 后处理缩放（§6.1 latent→output） ───

class FinalizeRequest(BaseModel):
    image_path: str
    target_width: int
    target_height: int
    hardware_tier: str = "standard"


@router.post("/finalize")
async def finalize(req: FinalizeRequest):
    """将生成底图从 latent 尺寸缩放到最终输出尺寸。低配自动尝试 ESRGAN 超分。"""
    path = req.image_path
    if path.startswith("medcomm-image://"):
        path = path[len("medcomm-image://"):]
    if ".." in path or path.startswith("/"):
        raise HTTPException(400, "非法路径")

    from app.services.medpic.resize import finalize_image
    try:
        result = await finalize_image(
            path, req.target_width, req.target_height, req.hardware_tier,
        )
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))
    except Exception as e:
        raise HTTPException(500, f"后处理失败: {e}")

    return result


# ─── §9.3 预置角色库 ───

@dataclass
class PresetCharacter:
    id: str
    name: str
    description: str
    reference_filename: str
    prompt_tags: str
    scenes: list[str]


PRESET_CHARACTERS: list[PresetCharacter] = [
    PresetCharacter(
        id="doctor_male",
        name="中年男性医生",
        description="白大褂，专业形象，适合通用科普",
        reference_filename="preset_doctor_male.png",
        prompt_tags="male doctor, white coat, professional, middle-aged, stethoscope",
        scenes=["article", "comic", "card", "poster", "ppt"],
    ),
    PresetCharacter(
        id="nurse_female",
        name="年轻女性护士",
        description="护士服，亲和形象，适合护理宣教",
        reference_filename="preset_nurse_female.png",
        prompt_tags="female nurse, scrubs, friendly smile, young, caring",
        scenes=["article", "comic", "card", "poster"],
    ),
    PresetCharacter(
        id="doctor_kids",
        name="卡通儿科医生",
        description="卡通风格，儿友好，适合儿科/绘本",
        reference_filename="preset_doctor_kids.png",
        prompt_tags="cartoon doctor, child-friendly, cute, colorful, pediatrician",
        scenes=["comic", "picturebook"],
    ),
    PresetCharacter(
        id="child_patient",
        name="卡通儿童患者",
        description="7–10 岁儿童形象，适合儿科/绘本",
        reference_filename="preset_child_patient.png",
        prompt_tags="cartoon child, 8 years old, brave, cute, patient gown",
        scenes=["comic", "picturebook"],
    ),
    PresetCharacter(
        id="elderly_patient",
        name="老年患者",
        description="慢病科普场景，适合慢病管理",
        reference_filename="preset_elderly_patient.png",
        prompt_tags="elderly patient, grandparent, warm expression, health management",
        scenes=["article", "comic", "card", "poster"],
    ),
]

PRESET_BY_ID: dict[str, PresetCharacter] = {c.id: c for c in PRESET_CHARACTERS}


def _preset_dir() -> Path:
    d = Path(settings.app_data_root) / "medpic" / "presets"
    d.mkdir(parents=True, exist_ok=True)
    return d


@router.get("/preset-characters")
async def get_preset_characters(scene: str = ""):
    """
    返回预置角色库列表。
    参考图文件需由管理员预先放置到 {app_data_root}/medpic/presets/ 目录。
    """
    d = _preset_dir()
    result = []
    for pc in PRESET_CHARACTERS:
        if scene and scene not in pc.scenes:
            continue
        ref_file = d / pc.reference_filename
        has_file = ref_file.is_file()
        rel = f"medpic/presets/{pc.reference_filename}" if has_file else ""
        result.append({
            "id": pc.id,
            "name": pc.name,
            "description": pc.description,
            "reference_path": rel,
            "thumbnail_url": f"/api/v1/imagegen/serve?path={rel}" if rel else "",
            "prompt_tags": pc.prompt_tags,
            "scenes": pc.scenes,
            "available": has_file,
        })
    return {"characters": result}


# ─── 角色一致性（§9.2 IP-Adapter）───

@router.post("/reference-image")
async def upload_reference_image(file: UploadFile = File(...)):
    """上传角色参考图，用于 B-2 IP-Adapter 工作流。"""
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(400, "请上传图片文件")

    data = await file.read()
    if len(data) > 10 * 1024 * 1024:
        raise HTTPException(400, "图片不超过 10MB")

    from app.services.medpic.character import save_reference_image
    rel = save_reference_image(data, file.filename or "")
    return {
        "path": rel,
        "serve_url": f"/api/v1/imagegen/serve?path={rel}",
    }


@router.post("/reference-from-generated")
async def reference_from_generated(image_path: str = ""):
    """将已生成的图片设为角色参考图。"""
    if not image_path:
        raise HTTPException(400, "请提供图片路径")
    path = image_path
    if path.startswith("medcomm-image://"):
        path = path[len("medcomm-image://"):]
    if ".." in path or path.startswith("/"):
        raise HTTPException(400, "非法路径")

    from app.services.medpic.character import save_reference_from_generated
    try:
        rel = save_reference_from_generated(path)
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))

    return {
        "path": rel,
        "serve_url": f"/api/v1/imagegen/serve?path={rel}",
    }


@router.get("/reference-images")
async def list_reference_images():
    """列出已保存的角色参考图。"""
    from app.services.medpic.character import list_references
    return {"items": list_references()}


# ─── 高分辨率放大（D-2）───

class UpscaleRequest(BaseModel):
    image_path: str
    print_size: str = "A3"
    aspect: str = "3:4"


@router.post("/upscale")
async def upscale(req: UpscaleRequest):
    """将生成的底图放大到印刷级分辨率。"""
    path = req.image_path
    if path.startswith("medcomm-image://"):
        path = path[len("medcomm-image://"):]
    if ".." in path or path.startswith("/"):
        raise HTTPException(400, "非法路径")

    from app.services.medpic.upscale import upscale_image
    try:
        result = await upscale_image(path, req.print_size, req.aspect)
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))
    except Exception as e:
        raise HTTPException(500, f"放大失败: {e}")

    return result


# ─── 长图拼接（F-*）───

class StitchRequest(BaseModel):
    segment_paths: list[str]
    variant_id: str = "F-1"
    output_width: int = 1080


@router.post("/stitch")
async def stitch(req: StitchRequest):
    """将多段图片拼接成长图，F-2 自动进行微信切片。"""
    cleaned = []
    for p in req.segment_paths:
        pp = p
        if pp.startswith("medcomm-image://"):
            pp = pp[len("medcomm-image://"):]
        if ".." in pp or pp.startswith("/"):
            raise HTTPException(400, f"非法路径: {p}")
        cleaned.append(pp)

    if not cleaned:
        raise HTTPException(400, "至少需要一段图像")

    from app.services.medpic.longimage import generate_long_image
    try:
        result = await generate_long_image(cleaned, req.variant_id, req.output_width)
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))
    except ValueError as e:
        raise HTTPException(400, str(e))

    return result


class SegmentPromptsRequest(BaseModel):
    topic: str
    segment_count: int = 4
    variant_id: str = "F-1"


@router.post("/long-segments")
async def long_segment_prompts(req: SegmentPromptsRequest):
    """为长图各段落生成递进式提示词后缀。"""
    if req.segment_count < 1 or req.segment_count > 10:
        raise HTTPException(400, "段落数范围: 1-10")

    variant = VARIANT_MAP.get(req.variant_id)
    composition = variant.composition if variant else ""

    from app.services.medpic.longimage import generate_segment_prompts
    prompts = generate_segment_prompts(req.topic, req.segment_count, composition)
    return {"segment_prompts": prompts, "count": len(prompts)}


# ─── 排版模板列表 ───

@router.get("/layouts")
async def list_layouts():
    from app.services.typography.templates import list_layouts as _list
    return {"layouts": _list()}


# ─── ComfyUI 工作流下发 ───

SCENE_WORKFLOW_MAP: dict[str, str] = {
    "article": "article_basic.json",
    "comic": "comic_basic.json",
    "card": "card_basic.json",
    "poster": "poster_basic.json",
    "picturebook": "picturebook_basic.json",
    "longimage": "longimage_basic.json",
    "ppt": "ppt_basic.json",
}


@router.get("/workflow/{variant_id}")
async def get_workflow(variant_id: str):
    """返回 variant 对应的 ComfyUI UI 格式工作流 JSON，供前端 webview 注入。"""
    import json

    variant = VARIANT_MAP.get(variant_id)
    if not variant:
        raise HTTPException(status_code=404, detail=f"Variant {variant_id} not found")

    filename = SCENE_WORKFLOW_MAP.get(variant.scene)
    if not filename:
        raise HTTPException(status_code=404, detail=f"No workflow for scene {variant.scene}")

    workflows_dir = Path(__file__).resolve().parents[4] / "workflows" / "comfyui" / "scenes"
    workflow_path = workflows_dir / filename
    if not workflow_path.exists():
        raise HTTPException(status_code=404, detail=f"Workflow file not found: {filename}")

    with open(workflow_path, "r", encoding="utf-8") as f:
        workflow = json.load(f)

    # Patch workflow with variant-specific parameters
    for node in workflow.get("nodes", []):
        node_type = node.get("type", "")
        widgets = node.get("widgets_values", [])
        if node_type == "EmptyLatentImage" and variant.latent_size:
            if len(widgets) >= 2:
                widgets[0] = variant.latent_size[0]
                widgets[1] = variant.latent_size[1]
        if node_type == "SaveImage" and widgets:
            widgets[0] = f"MedPic-{variant_id}"

    return {"workflow": workflow, "variant_id": variant_id, "format": "ui"}


class ComfyUIPromptRequest(BaseModel):
    scene: str
    topic: str
    variant: str = ""
    specialty: str = ""
    target_audience: str = "public"
    style: str = ""
    color_tone: str = "neutral"
    subject: str = ""
    extra_prompt: str = ""
    hardware_tier: str = "standard"
    aspect: str = ""
    reference_image: str = ""
    ipadapter_weight: float = 0.7
    character_preset: str = ""
    segment_index: int | None = None
    segment_count: int | None = None
    seed_mode: str = "recommended"
    seed: int | None = None
    lora_overrides: list[LoraOverrideItem] | None = None


@router.post("/comfyui-prompt")
async def build_comfyui_prompt(req: ComfyUIPromptRequest):
    """Build a ComfyUI API-format prompt ready to submit to /prompt endpoint."""
    import json, copy, random

    build_req = BuildPromptRequest(
        scene=req.scene, topic=req.topic, variant=req.variant,
        specialty=req.specialty, target_audience=req.target_audience,
        style=req.style, color_tone=req.color_tone, subject=req.subject,
        extra_prompt=req.extra_prompt, hardware_tier=req.hardware_tier,
        aspect=req.aspect, reference_image=req.reference_image,
        ipadapter_weight=req.ipadapter_weight, character_preset=req.character_preset,
        segment_index=req.segment_index, segment_count=req.segment_count,
        seed_mode=req.seed_mode, lora_overrides=req.lora_overrides,
    )
    pp = await build_prompt(build_req)

    wf_path = Path(__file__).resolve().parents[4] / pp.workflow_path
    if not wf_path.exists():
        raise HTTPException(404, f"API workflow not found: {pp.workflow_path}")
    with open(wf_path, "r", encoding="utf-8") as f:
        workflow = json.load(f)

    workflow = copy.deepcopy(workflow)
    seed = req.seed if req.seed is not None else (pp.recommended_seed or random.randint(0, 2**32 - 1))

    neg_clip_ids: set[str] = set()
    pos_clip_ids: set[str] = set()
    for nid, nd in workflow.items():
        if nd.get("class_type") in ("KSampler", "KSamplerAdvanced"):
            pos_ref = nd.get("inputs", {}).get("positive")
            neg_ref = nd.get("inputs", {}).get("negative")
            if isinstance(pos_ref, list):
                pos_clip_ids.add(str(pos_ref[0]))
            if isinstance(neg_ref, list):
                neg_clip_ids.add(str(neg_ref[0]))

    for node_id, node in workflow.items():
        ct = node.get("class_type", "")
        inputs = node.get("inputs", {})
        if ct == "CLIPTextEncode" and "text" in inputs:
            if node_id in neg_clip_ids:
                inputs["text"] = pp.negative_prompt
            elif node_id in pos_clip_ids:
                inputs["text"] = pp.positive_prompt
        elif ct == "EmptyLatentImage":
            inputs["width"] = pp.width
            inputs["height"] = pp.height
        elif ct == "KSampler":
            inputs["seed"] = seed
            inputs["steps"] = pp.steps
            inputs["cfg"] = pp.cfg_scale
            inputs["sampler_name"] = pp.sampler_name
            inputs["scheduler"] = pp.scheduler
        elif ct == "SaveImage":
            variant_tag = req.variant or req.scene
            inputs["filename_prefix"] = f"MedPic-{variant_tag}"

    return {
        "prompt": workflow,
        "client_id": "medpic",
        "params_used": {
            "positive_prompt": pp.positive_prompt,
            "negative_prompt": pp.negative_prompt,
            "width": pp.width,
            "height": pp.height,
            "steps": pp.steps,
            "cfg_scale": pp.cfg_scale,
            "seed": seed,
            "model_id": pp.model_id,
            "loras": [l.model_dump() for l in pp.loras],
        },
    }


# ─── 生成历史 ───

class SaveHistoryRequest(BaseModel):
    variant_id: str | None = None
    scene: str
    style: str = ""
    hardware_tier: str = "standard"
    topic: str = ""
    specialty: str | None = None
    positive_prompt: str = ""
    negative_prompt: str | None = None
    seed: int | None = None
    seed_mode: str | None = None
    model_id: str | None = None
    loras: list | None = None
    width: int | None = None
    height: int | None = None
    output_width: int | None = None
    output_height: int | None = None
    base_image_path: str
    composed_image_path: str | None = None
    upscaled_image_path: str | None = None
    ipadapter_weight: float | None = None
    character_preset: str | None = None
    reference_image_path: str | None = None


@router.post("/history")
async def save_history(req: SaveHistoryRequest, db: AsyncSession = Depends(get_session)):
    from app.models.medpic_generation import MedPicGeneration

    record = MedPicGeneration(
        variant_id=req.variant_id,
        scene=req.scene,
        style=req.style,
        hardware_tier=req.hardware_tier,
        topic=req.topic,
        specialty=req.specialty,
        positive_prompt=req.positive_prompt,
        negative_prompt=req.negative_prompt,
        seed=req.seed,
        seed_mode=req.seed_mode,
        model_id=req.model_id,
        loras=req.loras,
        width=req.width,
        height=req.height,
        output_width=req.output_width,
        output_height=req.output_height,
        base_image_path=req.base_image_path,
        composed_image_path=req.composed_image_path,
        upscaled_image_path=req.upscaled_image_path,
        ipadapter_weight=req.ipadapter_weight,
        character_preset=req.character_preset,
        reference_image_path=req.reference_image_path,
    )
    db.add(record)
    await db.commit()
    await db.refresh(record)
    return {"id": record.id, "created_at": record.created_at.isoformat() if record.created_at else None}


@router.get("/history")
async def list_history(
    scene: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_session),
):
    from app.models.medpic_generation import MedPicGeneration

    q = select(MedPicGeneration).order_by(MedPicGeneration.created_at.desc())
    if scene:
        q = q.where(MedPicGeneration.scene == scene)
    q = q.offset(offset).limit(limit)
    result = await db.execute(q)
    rows = result.scalars().all()

    count_q = select(sa_func.count(MedPicGeneration.id))
    if scene:
        count_q = count_q.where(MedPicGeneration.scene == scene)
    total = (await db.execute(count_q)).scalar() or 0

    items = []
    for r in rows:
        serve_path = r.composed_image_path or r.base_image_path
        items.append({
            "id": r.id,
            "variant_id": r.variant_id,
            "scene": r.scene,
            "style": r.style,
            "topic": r.topic,
            "specialty": r.specialty,
            "seed": r.seed,
            "base_image_path": r.base_image_path,
            "composed_image_path": r.composed_image_path,
            "upscaled_image_path": r.upscaled_image_path,
            "serve_url": f"/api/v1/imagegen/serve?path={serve_path}" if serve_path else None,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        })
    return {"items": items, "total": total}


@router.delete("/history/{record_id}")
async def delete_history(record_id: int, db: AsyncSession = Depends(get_session)):
    from app.models.medpic_generation import MedPicGeneration

    result = await db.execute(select(MedPicGeneration).where(MedPicGeneration.id == record_id))
    record = result.scalar_one_or_none()
    if not record:
        raise HTTPException(404, "记录不存在")
    await db.execute(sa_delete(MedPicGeneration).where(MedPicGeneration.id == record_id))
    await db.commit()
    return {"ok": True}


@router.patch("/history/{record_id}")
async def update_history(record_id: int, data: dict, db: AsyncSession = Depends(get_session)):
    """更新记录（主要用于补充 composed_image_path / upscaled_image_path）"""
    from app.models.medpic_generation import MedPicGeneration

    result = await db.execute(select(MedPicGeneration).where(MedPicGeneration.id == record_id))
    record = result.scalar_one_or_none()
    if not record:
        raise HTTPException(404, "记录不存在")

    allowed = {"composed_image_path", "upscaled_image_path"}
    for key, val in data.items():
        if key in allowed and val is not None:
            setattr(record, key, val)
    await db.commit()
    return {"ok": True}
