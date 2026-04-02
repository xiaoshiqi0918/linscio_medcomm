"""
图像生成专属提示词构建器
将用户描述 / AI 生成的 scene_desc 转化为高质量的英文图像生成提示词
（DALL·E 3 英文效果显著优于中文）
优先从 prompt-example/prompts/imagegen/ 加载
"""
import json
import logging
import re
from typing import Any, Optional

logger = logging.getLogger(__name__)

from app.agents.prompts.loader import (
    load_imagegen_style_system,
    load_imagegen_quality_suffix,
    load_imagegen_safety_negative,
    load_imagegen_translate_system,
    load_imagegen_type_templates,
)

_DEFAULT_STYLE_SYSTEM = {
    "medical_illustration": (
        "professional medical illustration, clean educational style, "
        "accurate anatomy, labeled diagram, bright clear colors, "
        "white background, no photorealism, no distressing content"
    ),
    "flat_design": (
        "flat design illustration, modern minimalist style, "
        "bold colors, simple shapes, infographic style, "
        "white or light background, professional medical context"
    ),
    "realistic": (
        "realistic medical illustration, clinical accuracy, "
        "clean professional style, appropriate for patient education, "
        "no graphic or distressing imagery, educational purpose"
    ),
    "cartoon": (
        "friendly cartoon illustration, warm colors, approachable style, "
        "suitable for children and general public, no scary elements, "
        "positive and encouraging mood, simple backgrounds"
    ),
    "data_viz": (
        "clean data visualization, infographic style, "
        "clear charts and graphs, professional color scheme, "
        "medical/health context, readable labels, white background"
    ),
    "comic": (
        "comic strip panel illustration, manga-inspired clean lines, "
        "expressive characters, warm color palette, "
        "medical education context, Chinese style manga, "
        "no violent or distressing content"
    ),
    "picture_book": (
        "children's picture book illustration, warm and friendly style, "
        "bright cheerful colors, cute characters, simple backgrounds, "
        "age-appropriate, encouraging and positive mood, "
        "no scary or frightening elements whatsoever"
    ),
}

STYLE_SYSTEM_PROMPTS = load_imagegen_style_system() or _DEFAULT_STYLE_SYSTEM

_DEFAULT_QUALITY_SUFFIX = (
    "high quality, detailed, professional, "
    "suitable for medical education and patient communication"
)

QUALITY_SUFFIX = load_imagegen_quality_suffix() or _DEFAULT_QUALITY_SUFFIX

# 医学科普默认安全负向：压制创伤/手术写实、不当与恐怖元素、隐私与伪科学误导、乱码水印与低质画面；
# 不排斥示意性解剖、标注图、扁平/插画类器械与流程（与正向「illustration / diagram」配合）。
_DEFAULT_SAFETY_NEGATIVE = (
    "blood, gore, open wounds, realistic trauma and emergency scene, surgery in progress, "
    "exposed viscera or organ photography, autopsy, morgue, graphic pathology or infection realism, "
    "needles or injections in horror or threatening framing, "
    "sexual content, pornographic, child exploitation, fetish medical imagery, "
    "self-harm, suicide method depiction, glorified substance abuse, "
    "horror, jumpscare, extreme body horror, shock-value deformity, "
    "misleading miracle cure, fake medical credentials, pseudoscience device hype, "
    "identifiable patient faces, readable PHI or medical record text, "
    "celebrity likeness, political propaganda, hate symbols, "
    "deliberately misleading anatomy for misinformation, "
    "garbled illegible overlaid text, illegible tiny text spam, watermarks, stock-site logos, "
    "URL or QR code overlays, social media UI overlay, meme caption clutter, "
    "cluttered illegible layout, heavy motion blur, severe jpeg artifacts, low resolution"
)

SAFETY_NEGATIVE = load_imagegen_safety_negative() or _DEFAULT_SAFETY_NEGATIVE

_DEFAULT_IMAGE_TYPE_TEMPLATES = {
    "anatomy": {
        "en_template": (
            "{content} anatomy diagram, "
            "labeled with key parts, educational illustration, "
            "clear and accurate anatomical representation"
        ),
        "negative": "inaccurate anatomy, cartoon distortion of medical accuracy",
    },
    "pathology": {
        "en_template": (
            "medical illustration showing {content} in a clear educational style, "
            "arrows showing process flow, labeled diagram, "
            "no graphic pathological imagery"
        ),
        "negative": "graphic pathology, realistic disease photography, distressing medical imagery",
    },
    "flowchart": {
        "en_template": (
            "medical flowchart showing {content}, "
            "step-by-step diagram with arrows, "
            "clean boxes and connecting lines, "
            "each step clearly labeled in English, "
            "professional infographic style"
        ),
        "negative": "cluttered, too many elements, unclear flow",
    },
    "infographic": {
        "en_template": (
            "health infographic about {content}, "
            "data visualization with icons and simple charts, "
            "clear sections and hierarchy, "
            "professional color-coded layout"
        ),
        "negative": "cluttered text, poor readability, confusing layout",
    },
    "comparison": {
        "en_template": (
            "side-by-side comparison illustration: {content}, "
            "clear visual contrast, labeled, "
            "educational medical style"
        ),
        "negative": "graphic disease imagery, distressing comparison",
    },
    "symptom": {
        "en_template": (
            "gentle educational illustration showing {content}, "
            "depicted in a sensitive and non-graphic way, "
            "using abstract or diagrammatic representation, "
            "suitable for patient education, no realistic imagery"
        ),
        "negative": "graphic symptoms, realistic medical photography, distressing imagery, blood",
    },
    "prevention": {
        "en_template": (
            "health promotion illustration showing {content}, "
            "positive and encouraging visual, "
            "friendly educational style"
        ),
        "negative": "negative imagery, scary consequences, punishment themes",
    },
    "comic_panel": {
        "en_template": (
            "{content}, "
            "comic strip panel style, manga-inspired clean lines, "
            "expressive characters, "
            "medical/health context, Chinese manga aesthetic, "
            "panel composition with clear focal point"
        ),
        "negative": "Western cartoon style, violent content, scary medical imagery",
    },
    "picture_book_page": {
        "en_template": (
            "{content}, "
            "children's picture book style, warm cheerful colors, "
            "cute friendly characters, simple background, "
            "age-appropriate for 3-12 years, "
            "encouraging and positive mood, no scary elements"
        ),
        "negative": "scary, frightening, dark themes, complex backgrounds, adult content",
    },
    "storyboard_frame": {
        "en_template": (
            "{content}, "
            "animation storyboard frame, "
            "medical education animation style, "
            "clean lines, clear focal point"
        ),
        "negative": "photorealistic, complex textures, unclear focal point",
    },
    "card_illustration": {
        "en_template": (
            "{content}, "
            "flat design medical illustration, bright colors, "
            "white background, professional infographic style"
        ),
        "negative": "cluttered, scary, complex",
    },
    "poster": {
        "en_template": (
            "{content}, "
            "medical poster style, professional, clear hierarchy, "
            "suitable for patient education display"
        ),
        "negative": "cluttered, unprofessional",
    },
}

IMAGE_TYPE_TEMPLATES = load_imagegen_type_templates() or _DEFAULT_IMAGE_TYPE_TEMPLATES


def _compose_med_negative(style: str, image_type: str) -> str:
    """build_med_prompt 步骤 7 / get_default_medical_negative 共用。
    不使用笼统的 text overlay，避免压制正当的解剖标注与流程 callout；乱字/水印/UI 垃圾在安全串中已写明。"""
    negative = SAFETY_NEGATIVE
    if style != "realistic":
        negative += ", photorealistic, photograph"
    template = IMAGE_TYPE_TEMPLATES.get(image_type)
    if template and template.get("negative"):
        negative += f", {template['negative']}"
    return negative


_DEFAULT_TRANSLATE_SYSTEM = (
    "You are a translator. Translate the given medical/health content description to English. "
    "Output ONLY the English translation, no explanations. Keep it concise (20-50 words) for image generation prompts."
)
TRANSLATE_SYSTEM = load_imagegen_translate_system() or _DEFAULT_TRANSLATE_SYSTEM


def _has_chinese(text: str) -> bool:
    """检测是否包含中文字符"""
    return bool(re.search(r"[\u4e00-\u9fff]", text))


async def _translate_to_english(text: str) -> str:
    """调用 LLM 将中文描述翻译为英文"""
    try:
        from app.services.llm.openai_client import chat_completion

        resp = await chat_completion(
            messages=[
                {"role": "system", "content": TRANSLATE_SYSTEM},
                {"role": "user", "content": text},
            ],
            stream=False,
        )
        return (resp or "").strip() or text
    except Exception:
        return text


def _standardize_medical_terms(text: str, specialty: str) -> str:
    """医学术语标准化（占位，可接入术语库）"""
    return text


# v2.0：受众安全修饰（正向引导）
AUDIENCE_SAFE_MODIFIERS = {
    "public": "accessible and non-threatening, suitable for general public",
    "patient": "reassuring and supportive visual tone, patient-friendly",
    "student": "detailed and accurate educational illustration, clinical precision",
    "professional": "high accuracy medical illustration, professional clinical quality",
    "children": (
        "child-safe imagery only, warm friendly characters, "
        "bright cheerful colors, absolutely no adult medical content, "
        "no blood no needles no scary elements whatsoever"
    ),
}

# v2.0：图像类型专属安全引导
MEDICAL_SAFE_GUIDES = {
    "anatomy": (
        "educational medical illustration, diagrammatic style, "
        "clean labeled diagram suitable for patient education, "
        "no realistic tissue textures, no blood or body fluids shown"
    ),
    "pathology": (
        "schematic diagram showing disease process, "
        "abstract and symbolic representation, "
        "suitable for health education, no graphic pathology"
    ),
    "symptom": (
        "gentle educational illustration of health condition, "
        "depicted symbolically, non-distressing, "
        "appropriate for patient education, no realistic pain depiction"
    ),
    "surgery": None,  # 完全禁止，拒绝生成
    "comic_panel": (
        "clean comic panel style, expressive but non-threatening characters, "
        "appropriate for health education, no scary medical content"
    ),
    "picture_book_page": (
        "children's picture book style, warm cheerful colors, "
        "cute and friendly characters, simple safe backgrounds, "
        "absolutely no scary frightening elements"
    ),
    "flowchart": "clean medical flowchart, professional infographic, educational",
    "infographic": "health information graphic, clean data visualization, easy to understand",
    "prevention": "positive health promotion, showing healthy behaviors, empowering",
    "comparison": "side-by-side educational comparison, clear visual distinction, no graphic disease",
    "poster": "professional health awareness poster, appropriate for public display",
    "card_illustration": "clean knowledge card illustration, simple iconic style",
    "storyboard_frame": "animation storyboard frame, clear focal point, educational style",
}


def _get_audience_modifier(target_audience: str) -> str:
    return AUDIENCE_SAFE_MODIFIERS.get(
        target_audience, "clear and educational"
    )


async def build_med_prompt(
    user_desc: str,
    image_type: str,
    style: str,
    specialty: str = "",
    target_audience: str = "public",
    translate_chinese: bool = True,
) -> tuple[str, str, str | None]:
    """
    构建医学图像生成提示词
    返回 (positive_prompt, negative_prompt, rejection_reason)
    rejection_reason 不为 None 时调用方应拒绝生成
    """
    # v2.0：surgery 类型完全禁止
    if image_type == "surgery":
        return "", "", "手术场景图像在医学科普中存在误导风险，请选择其他图像类型"

    base_desc = user_desc.strip()
    if not base_desc:
        return "", "", None

    # 步骤1：若输入含中文且需翻译，翻译为英文
    if translate_chinese and _has_chinese(base_desc):
        base_desc = await _translate_to_english(base_desc)

    # 步骤2：医学术语标准化
    base_desc = _standardize_medical_terms(base_desc, specialty)

    # 步骤3：按 image_type 应用模板（若有）
    template = IMAGE_TYPE_TEMPLATES.get(image_type)
    if template:
        content = base_desc
        tpl = template["en_template"]
        if "{content}" in tpl:
            content = base_desc
        elif "{scene_desc}" in tpl:
            content = base_desc
        elif "{illustration_desc}" in tpl:
            content = base_desc
        else:
            content = base_desc
        try:
            base_desc = tpl.format(
                content=content,
                scene_desc=content,
                illustration_desc=content,
            )
        except KeyError:
            base_desc = tpl.replace("{content}", content)

    # 步骤4：受众安全修饰 + 图像类型安全引导
    audience_modifier = _get_audience_modifier(target_audience)
    safe_guide = MEDICAL_SAFE_GUIDES.get(image_type, "")

    # 步骤5：风格系统提示
    style_prompt = STYLE_SYSTEM_PROMPTS.get(
        style, STYLE_SYSTEM_PROMPTS["flat_design"]
    )

    # 步骤6：组合正向提示词（base + safe_guide + audience + style + quality）
    parts = [base_desc, audience_modifier]
    if safe_guide:
        parts.insert(1, safe_guide)
    positive = ", ".join(filter(None, parts)) + f", {style_prompt}, {QUALITY_SUFFIX}"

    # 步骤7：负向提示词
    negative = _compose_med_negative(style, image_type)

    return positive, negative, None


def build_med_prompt_sync(
    user_desc: str,
    image_type: str,
    style: str,
    specialty: str = "",
    target_audience: str = "public",
) -> tuple[str, str]:
    """
    同步版本：不进行中文翻译，直接组合（适用于已是英文的 scene_desc）
    """
    base_desc = user_desc.strip()
    if not base_desc:
        return "", ""

    base_desc = _standardize_medical_terms(base_desc, specialty)

    template = IMAGE_TYPE_TEMPLATES.get(image_type)
    if template:
        tpl = template["en_template"]
        try:
            base_desc = tpl.format(
                content=base_desc,
                scene_desc=base_desc,
                illustration_desc=base_desc,
            )
        except KeyError:
            base_desc = tpl.replace("{content}", base_desc)

    audience_modifier = _get_audience_modifier(target_audience)
    style_prompt = STYLE_SYSTEM_PROMPTS.get(
        style, STYLE_SYSTEM_PROMPTS["flat_design"]
    )
    positive = f"{base_desc}, {audience_modifier}, {style_prompt}, {QUALITY_SUFFIX}"

    negative = _compose_med_negative(style, image_type)

    return positive, negative


def get_default_medical_negative(style: str, image_type: str) -> str:
    """
    未填写负向提示词时使用：医学安全 + 类型模板负向（与 build_med_prompt 步骤 7 一致）。
    用户填写负向时由调用方完全覆盖，不与此合并。
    """
    return _compose_med_negative(style, image_type)


AI_IMAGE_PROMPT_SYSTEM = """You write English image-generation prompts for HEALTH and MEDICAL POPULAR SCIENCE (education, outreach, patient communication)—not for clinical diagnosis or treatment decisions.

The user's message includes Style id, Image type id, Content format, Audience, and a scene idea (may be Chinese, including TCM or China public-health idioms). Read those ids and adapt tone, composition, and negatives accordingly.

=== Language and culture (scene idea) ===
- Translate the user's intent into English tags inside the JSON values; do not copy long Chinese sentences into JSON unless a proper noun must stay (then keep minimal).
- If the idea involves Traditional Chinese Medicine (TCM)—meridians, qi/blood, cupping, acupuncture points, herbal formulas—treat it as legitimate health education. Prefer respectful, neutral clinical-education metaphors (diagrammatic meridian maps, gentle icons). Avoid exoticizing or Orientalist staging (no "mystical East" clichés, no costume drama unless the user explicitly asks for a period setting).

=== OUTPUT CONTRACT (strict) ===
- Return exactly one raw JSON object. Prefer a single line; if you must wrap, still produce valid JSON only—no prose outside the object.
- Keys must be exactly: "positive" and "negative" (lowercase). No extra keys.
- Both values must be non-empty English strings, mainly comma-separated tags and short phrases.
- If uncertain about content, still output valid JSON with conservative safe prompts—never reply with an explanation instead of JSON.
- Use normal UTF-8 characters inside strings; do not over-escape Unicode beyond JSON requirements.

=== Priority when rules conflict ===
Order: (1) Non-negotiable safety → (2) Audience rules → (3) Image type id hints → (4) Style id bias.
- When type id is pathology or symptom, ALWAYS reinforce anti-horror, anti-shock, anti-photographic-gore cues in negative—even if style is comic, cartoon, or picture_book. You may still keep comic/manga in positive; do not cancel stylization—only layer extra safety negatives (e.g. body horror, jumpscare framing, grotesque lesion macro, horror lighting).

=== Non-negotiable safety (all styles and types) ===
- Never imply that an image alone can diagnose or replace a clinician.
- Do not depict or glamorize: sexual or exploitative content, CSAM, hate symbols, political propaganda, real celebrity likeness, readable PHI or medical-record text.
- No graphic gore, open wounds, realistic emergency trauma, active surgery, autopsy/morgue, or photographic graphic pathology. For pathology/symptom types, use schematic, cross-section, icon, or gently stylized teaching visuals—not horror or shock.
- No instructions or glorification of self-harm, suicide, or substance abuse. No misleading "miracle cure" or fake credential imagery.

=== Unknown ids (fallback) ===
- If Style id is missing or unrecognized, behave like medical_illustration for layout and safety.
- If Image type id is missing or unrecognized, behave like a blend of anatomy + infographic: clear structure, schematic clarity, educational hierarchy.

=== Style id → positive prompt bias ===
- medical_illustration: Clean labeled-diagram feel, accurate proportions, educational clarity, bright readable composition.
- flat_design / data_viz: Simple shapes, strong hierarchy, infographic or chart-friendly layout; minimal texture.
- realistic: Target look = medical journal cover illustration or serious health-magazine editorial art—believable anatomy, professional controlled lighting, dignified presentation, clean clinical or studio context. NOT: ER documentary, surgical close-up blood, crime-scene lighting, shaky smartphone clinic selfie, ring-light influencer medical aesthetic, or photojournalism trauma.
- cartoon: Friendly rounded forms, approachable palette, clear health-education intent.
- comic: Comic or manga-influenced line art, expressive characters and gestures for empathy or narrative; dynamic poses and panel-friendly framing OK. Encourage the chosen look in positive (clean ink lines, screentone or flat colors, Chinese-comic-friendly readability where appropriate).
- picture_book: Soft picture-book paint or colored pencil look, warm palette, simple backgrounds; whimsical but on-topic for health education.

=== Style id → negative prompt (subordinate to priority above) ===
- comic / cartoon / picture_book: Do NOT negate the intended stylization (avoid listing as negatives: anime, manga, comic, cartoon, chibi, cel shading, bold outlines) unless the user idea demands a different look. Exception: pathology/symptom types still add the extra anti-horror / anti-grotesque negatives from Priority rules.
- medical_illustration / flat_design / data_viz: Mild anti-snapshot cues are OK (e.g. smartphone photo, vacation snapshot) unless Style id is realistic and the user wants editorial realism.
- realistic: Do not negate "medical illustration", "editorial", or "professional studio lighting". Do negate documentary trauma, ER vérité, flash-on-gore, and tacky clinic selfie tropes when useful.

=== Text, labels, and overlays in negative ===
- Negate: watermarks, stock-site logos, URL or QR overlays, social-media UI, meme caption clutter, illegible tiny text spam, gibberish typography.
- Do NOT negate concepts that help education: clean anatomical labels, short English callouts, single-word pointers, simple diagram annotations—describe these in positive when type is anatomy, flowchart, infographic, comparison, pathology (diagrammatic), or poster. Avoid the generic phrase "text overlay" as a blind negative; be specific about clutter and junk text instead.

=== Image type id hints ===
- anatomy, flowchart, infographic, comparison, card_illustration: Structure and clarity first; schematic over sensational.
- pathology, symptom: Abstract or diagrammatic disease process; arrows, stages, icons; no photographic lesion close-ups; reinforce non-horror negatives per Priority.
- prevention, poster: Positive, empowering, clear focal motif; suitable for public display.
- comic_panel / storyboard_frame: If the idea implies multiple panels or beats, pick the SINGLE most important story moment for one image. You may add light layout cues ("split panel", "inset close-up", "motion line") only when they clarify one beat—do not narrate a whole sequence in one prompt.
- picture_book_page: Full-bleed or gentle margin, age-appropriate mood; no scary anthropomorphic organs or needle monsters.

=== Audience ===
- children: Positive bias—friendly mascot or animal helpers if it fits the idea, pastel or warm saturated palette, rounded shapes, very simple background, storybook warmth, one clear focal subject, gentle expressions. Negative—explicitly block frightening medical horror, adult themes, threatening syringe-as-weapon framing, and dark gritty grading.
- professional / student: Denser detail and finer anatomical structure in positive allowed; safety rules unchanged.
- public / patient: Clear, calm, reassuring; avoid alarmist visual language unless the user idea requires contrast (still stay non-graphic).

=== General ===
- Positive encodes the user's idea plus style-appropriate art direction.
- Negative complements positive: block artifacts, junk UI, and safety risks without cancelling the chosen art style, except where type pathology/symptom requires extra anti-horror layering.
"""


def _parse_ai_prompt_llm_json(raw: str) -> dict[str, Any] | None:
    """解析模型返回的 JSON；容忍前言后语与 ``` 代码块。"""
    text = (raw or "").strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1]
        if text.rstrip().endswith("```"):
            text = text.rsplit("```", 1)[0].strip()
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        pass
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        return None
    try:
        data = json.loads(text[start : end + 1])
        return data if isinstance(data, dict) else None
    except json.JSONDecodeError:
        return None


async def ai_generate_image_prompts(
    scene_idea: str,
    style: str = "medical_illustration",
    image_type: str = "anatomy",
    target_audience: str = "public",
    content_format: str = "article",
) -> tuple[str, str, bool]:
    """
    AI 生成正/负向提示词（每次调用覆盖，由前端写入输入框）。
    返回 (positive, negative, used_template_fallback)。
    LLM 失败或解析失败时回退 build_med_prompt；完全失败时 ("", "", False).
    """
    idea = (scene_idea or "").strip()
    if not idea:
        return "", "", False

    try:
        from app.services.llm.openai_client import chat_completion

        user = (
            f"Style id: {style}\nImage type id: {image_type}\n"
            f"Content format: {content_format}\nAudience: {target_audience}\n\n"
            f"User idea (may be Chinese):\n{idea}"
        )
        raw = await chat_completion(
            messages=[
                {"role": "system", "content": AI_IMAGE_PROMPT_SYSTEM},
                {"role": "user", "content": user},
            ],
            stream=False,
        )
        data = _parse_ai_prompt_llm_json(raw or "")
        if data:
            pos = (data.get("positive") or "").strip()
            neg = (data.get("negative") or "").strip()
            if pos:
                if not neg:
                    neg = get_default_medical_negative(style, image_type)
                return pos, neg, False
    except Exception as e:
        logger.warning("ai_generate_image_prompts LLM step failed: %s", e)

    pos, neg, rejection = await build_med_prompt(
        idea,
        image_type,
        style,
        specialty="",
        target_audience=target_audience,
    )
    if rejection or not pos:
        return "", "", False
    if not neg:
        neg = get_default_medical_negative(style, image_type)
    return pos, neg, True


SUGGEST_IMAGES_PROMPT = """请分析以下医学科普内容，推荐最合适的配图位置和内容。

【科普内容】
{verified_content}

【文章信息】
主题：{topic}
专科：{specialty}
目标受众：{target_audience}
科普形式：{content_format}

【配图推荐规则】
1. 只在以下情况推荐配图：
   - 文字描述了复杂的解剖结构或生理过程（图能说明白，文字说不清楚）
   - 需要展示健康vs疾病的对比
   - 流程/步骤需要视觉化辅助
   - 数据/统计信息适合图表展示

2. 不推荐配图的情况：
   - 纯叙事段落（故事/案例）
   - 已经很简洁的文字段落
   - 情绪性段落（共情内容不需要图）

3. 每篇文章最多推荐3处配图

【输出格式（严格遵守，必须为合法 JSON）】

[
  {{
    "anchor_text": "该段落的前20个字（用于前端定位段落位置）",
    "image_type": "anatomy|pathology|flowchart|infographic|comparison|symptom|prevention",
    "style": "medical_illustration|flat_design|realistic|cartoon|data_viz",
    "description": "图像内容描述（中文，30-50字，说明图要展示什么）",
    "en_description": "图像内容描述（英文，20-40词，供图像生成直接使用）",
    "reason": "为什么这里需要配图（≤20字）",
    "priority": "high|medium（high=这里没有图会明显影响理解）"
  }}
]

如果没有适合配图的位置，返回空数组：[]

请直接输出 JSON，不要有任何其他文字。
"""
