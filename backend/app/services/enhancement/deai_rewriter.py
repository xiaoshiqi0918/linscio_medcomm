"""
去AI化改写服务：对已生成的文本进行多轮改写，降低AIGC检测特征值。

基于 AIGC 检测器的四类核心信号进行反向工程：
  - 困惑度（Perplexity）：文本对语言模型的"意外程度"
  - 突发性（Burstiness）：句长与复杂度的波动幅度
  - 模式特征（Pattern Features）：高频模板词、N-gram 指纹
  - 分布一致性（Stylistic Consistency）：全文语态/语域的同质化

三层改写架构：
  表层（句法）：技法1句式重构 + 技法3添加主语 → 干扰突发性与句法分析
  中层（词汇）：技法2破解模板 + 技法6困惑度提升 → 移除指纹、提升不可预测性
  深层（语义）：技法4概念具象 + 技法5论证补全 + 技法7风格断裂 → 信息密度、非线性论证、打破一致性
"""
import re
import logging
from typing import Any

logger = logging.getLogger(__name__)

# ────────────────────────────────────────────
# System Prompt
# ────────────────────────────────────────────

_DEAI_SYSTEM_PROMPT = """\
你是一位给健康媒体写专栏的临床医生。你的稿件带文献引用[N]，语域是半正式科普——不是论文，也不是聊天。

改写任务的规则：
- 保留全部事实、数据和引用标注[N]，不增不减医学内容
- 语域保持一致：既然有[N]引用，就不要出现口语词（"其实吧""折腾人啊""咱们"）
- 每句话都要承载信息，不写修辞性铺垫和情绪化渲染
- 可以加入临床判断和个人观察，但用的是专栏作者的口吻，不是朋友聊天的口吻"""

# ────────────────────────────────────────────
# 第1轮：全文级7技法改写 Prompt
# ────────────────────────────────────────────

_DEAI_REWRITE_PROMPT = """\
下面是一篇带文献引用的医学科普稿件。请用你自己的表达方式重新写一遍。

硬性规则：
1. 事实和数据一个不能少、不能改、不能编
2. 字数跟原文差不多（0.8~1.2倍），段落数基本不变
3. 引用[N]精简：只保留在关键数据和核心结论上（读者会问"凭什么？"的地方）。每段角标≤2-3个。
   常识性陈述（"化验有误差""饮食影响血糖"）、定义、逻辑推理——去掉角标，不需要引用
   如果原文某段有5个以上[N]，必须减少到2-3个，只保留最关键的

信息递进：
- 每句话必须比上一句推进新信息。如果两句话是同一个意思的不同表述，合并或砍掉一句
- 压缩省出来的字数用来给具体内容：举例、给数据、给分类

句式节奏（最重要——直接决定是否被判为AI）：
- 不追求均匀的长短句交替。正常写作有时连续3-4句中等长度，然后突然一句很短的判断（如"这就是问题所在。"），再来一句长的展开
- 追求的是不规则的节奏，不是机械交替
- 一句完整的话说完再打句号，不要把一句话拆成几个短句各打句号（不要几个字就一个句号）
- 禁止连续3句结构相同（如连续三句都是"A可能由B导致"式的陈述判断句）

段落衔接（极重要——连接词密集是AI最大特征）：
- 段落之间不要用连接词（"然而""因此""此外""与此同时""不仅如此"）过渡
- 段落衔接靠话题本身的逻辑关系：上一段说完A，下一段直接切入B，读者自己能接上
- 如果要转折，直接说新的事实，不要用"然而"铺垫
- 段内也尽量少用逻辑连接词，靠信息本身推进

风格统一：
- 全文保持同一个语域：如果是半正式科普风，就不要突然蹦出特别口语化的比喻（"卡了个BUG"）然后又回到学术表达（"竞争性地取代目标分子"）
- 比喻和解释要在同一个语域里

叙事结构：
- 打破叙事模板：不是每个知识点都要"结论→解释→数据→案例"的相同节奏
- 有的可以先给一个让读者意外的事实再解释原因，有的直接给数据，有的用一个临床故事带出要点

标点：
- 需要解释时用冒号引出（如"原因很简单：……"），不要用破折号
- 减少破折号的使用频率（全文不超过2-3个）
- 一句话说完整再打句号，不要碎成很多短句

去公文化：
- 禁止名词化组合："聚焦于""进行了探讨""存在的技术偏差""具有重要意义"
- 改为动词主导的自然句
- 句子要有明确的人做主语，不要用无主语的被动结构堆砌

直接输出改写后的全文。

---
{content}
---"""

# ────────────────────────────────────────────
# 第2轮：段落级定向改写 Prompt
# ────────────────────────────────────────────

_STYLE_PROFILES = [
    {
        "name": "临床经验切入",
        "instruction": "以临床观察为主线改写。可以用'临床上更常见的是''实际操作中'等表达引入个人经验视角，但保持半正式语域。",
    },
    {
        "name": "数据驱动",
        "instruction": "以具体数据和文献证据为主线改写。优先呈现数字、比例、时间范围，句式偏平实陈述，信息密度高，少用形容词。",
    },
    {
        "name": "机制解释",
        "instruction": "以因果机制为主线改写。注重'为什么会这样'的解释链条，句子可以长一些来完整呈现因果关系，技术术语可以保留但附简明解释。",
    },
    {
        "name": "对比辨析",
        "instruction": "以区分概念为主线改写。把容易混淆的概念拿出来对比——什么是什么、什么不是什么、区别在哪里。用对比结构让信息更清晰。",
    },
    {
        "name": "实操导向",
        "instruction": "以'读者能怎么做'为主线改写。侧重可操作的建议和判断标准，减少背景铺垫，直接说'遇到X情况，应该Y'。",
    },
]

_DEAI_OPENING_PROMPT = """\
下面这段是文章的开头，请改写。保留全部事实和引用标注[N]，字数跟原文差不多。

当前的问题：
{problem_description}

改写要求：
- 开头需要一个"读者入口"——场景、疑问、常见误解或反常识点，让读者先代入再接收信息
- 入口之后再给核心信息，不要第一句就抛结论
- 入口简短（1句），不能变成大段铺垫或情绪渲染
- 第一句话要完整（不要几个字就打句号），说一个完整的场景或疑问
- 禁止综述式开头："近年来""随着""众所周知"
- 开头段不要使用任何逻辑连接词（"然而""因此""此外"等）
- 每句话必须推进信息——如果两句话说的是同一件事的不同表述，砍掉一句
- 关键概念首次出现时必须界定，不能只给比喻不给术语
- [N]引用精简：开头段角标≤1个（甚至可以没有）
- 标点：解释用冒号引出，少用破折号，一句话说完整再打句号

直接输出段落文本。

---
{paragraph}
---"""

_DEAI_ENDING_PROMPT = """\
下面这段是文章的结尾，请改写。保留全部事实和引用标注[N]，字数跟原文差不多。

当前的问题：
{problem_description}

改写要求：
- 禁止总结回顾（"综上""总之""总而言之"）
- 禁止情感升华和口号（"守护健康""携手前行"）
- 结尾应该是具体的行动建议或就医信号——说完就停
- 保持半正式科普语域，与全文一致

直接输出段落文本。

---
{paragraph}
---"""

_DEAI_PARAGRAPH_PROMPT = """\
下面这段请改写。保留全部事实和引用标注[N]，字数跟原文差不多。

当前的问题：
{problem_description}

改写侧重点：{style_instruction}

通用要求：
- 每句话必须推进新信息——如果两句话是同一个意思的不同表述，合并或砍掉一句
- 省略主语的句子补上明确的行为主体
- 避免名词化公文表达（"聚焦于""进行了探讨""存在的偏差"），改为动词主导的自然句
- [N]引用精简：每段角标≤2-3个，只保留关键数据和核心结论
- 模板词直接删掉（"值得注意""综上""不是A而是B"）
- 不用逻辑连接词开头（删掉段首的"然而""因此""此外""与此同时"，直接说事实）
- 段内也尽量少用逻辑连接词，靠信息推进而非连接词衔接
- 连续的句子不能结构相同——变换句式
- 标点修正：解释用冒号引出，减少破折号使用，一句话说完整再打句号

直接输出改写后的段落文本，不要输出解释。

---
{paragraph}
---"""


# ────────────────────────────────────────────
# 核心改写函数
# ────────────────────────────────────────────

DEAI_TEMPERATURE = 1.15


async def _call_llm(
    messages: list[dict[str, str]],
    article_id: int | None = None,
    article_default_model: str | None = None,
) -> str | None:
    """统一的 LLM 调用，带错误处理。使用略高温度提升 token 选择多样性以对抗困惑度检测。"""
    from app.services.llm.openai_client import chat_completion, call_llm_with_fallback
    from app.services.llm.manager import resolve_model_for_task, TaskTier
    from app.core.config import is_saas

    try:
        if is_saas():
            return await call_llm_with_fallback(
                "deai_rewrite_round2", messages,
                article_id=article_id,
                stream=False,
                temperature=DEAI_TEMPERATURE,
            )
        else:
            model = await resolve_model_for_task(
                task=TaskTier.BALANCED,
                article_id=article_id,
                article_default_model=article_default_model,
            )
            return await chat_completion(
                messages, model=model, stream=False, temperature=DEAI_TEMPERATURE,
            )
    except Exception as e:
        logger.warning(f"去AI化改写：LLM 调用异常 {e}")
        return None


def _build_fact_guard_config():
    """从 settings 构建 FactGuardConfig。错误时返回 None（fact_guard 关闭）。"""
    try:
        from app.core.config import settings
        from app.services.enhancement.fact_guard import FactGuardConfig
        if not settings.enable_fact_guard:
            return None
        return FactGuardConfig(
            enable_master=True,
            enable_drugs=settings.enable_fact_guard_drugs,
            fail_open_on_error=settings.fact_guard_fail_open,
            hard_block=settings.fact_guard_hard_block,
            full_scan=settings.fact_guard_full_scan,
        )
    except Exception:
        return None


def _validate_rewrite(
    original: str,
    rewritten: str | None,
    label: str = "",
    cap_chars: int | None = None,
    fact_guard_summary: Any = None,
) -> str | None:
    """校验改写结果的合理性，不合理则返回 None。

    校验顺序：
      1. 长度（过短即丢弃）
      2. 引用编号至少保留一个
      3. 字数硬上限（cap_chars 优先，回退比例校验）
      4. fact_guard：medical 事实一致性（强 gate 失败即丢弃；弱 gate 由 hard_block 控制）

    fact_guard_summary: 可选 FactGuardSummary 实例，用于把每次检查记入累计统计。
    """
    tag = f"[{label}] " if label else ""
    if not rewritten or len(rewritten.strip()) < 50:
        logger.warning(f"{tag}改写返回过短，丢弃")
        return None

    original_refs = set(re.findall(r"\[(\d+)\]", original))
    rewritten_refs = set(re.findall(r"\[(\d+)\]", rewritten))
    if original_refs and not rewritten_refs:
        logger.warning(f"{tag}改写后丢失全部引用标注，丢弃")
        return None

    orig_len = len(original.strip())
    new_len = len(rewritten.strip())

    if cap_chars and cap_chars > 0:
        # 上限：min(原文 × 1.1, cap × 1.2)；但若原文已远小于 cap，仍允许扩到 cap
        upper_chars = min(int(orig_len * 1.1), int(cap_chars * 1.2))
        upper_chars = max(upper_chars, cap_chars)
        # 下限：取 cap × 0.4 与 原文 × 0.4 的较大者，至少 50 字
        lower_chars = max(50, int(cap_chars * 0.4), int(orig_len * 0.4))
        if new_len < lower_chars or new_len > upper_chars:
            logger.warning(
                f"{tag}改写后字数 {new_len} 超出区间 [{lower_chars}, {upper_chars}]"
                f"（原文 {orig_len}，本节 cap {cap_chars}），丢弃"
            )
            return None
    else:
        length_ratio = new_len / orig_len
        max_ratio = 3.0 if orig_len < 300 else 2.2 if orig_len < 800 else 1.8
        if length_ratio < 0.4 or length_ratio > max_ratio:
            logger.warning(f"{tag}长度比例异常 ({length_ratio:.2f}, 上限{max_ratio})，丢弃")
            return None

    # P0-1 / fact_guard 强 gate
    fg_cfg = _build_fact_guard_config()
    if fg_cfg is not None:
        try:
            from app.services.enhancement.fact_guard import (
                validate_facts_consistency,
                GateResult,
            )
            fg_result = validate_facts_consistency(original, rewritten, fg_cfg)
            if fact_guard_summary is not None:
                fact_guard_summary.record(fg_result)
            if fg_result.result == GateResult.REJECT_STRONG:
                logger.warning(
                    f"{tag}fact_guard REJECT_STRONG: failed={fg_result.failed_dimensions}，回退原文"
                )
                return None
            if fg_result.result == GateResult.REJECT_WEAK and fg_cfg.hard_block:
                logger.warning(
                    f"{tag}fact_guard REJECT_WEAK: failed={fg_result.failed_dimensions}，回退原文"
                )
                return None
            if fg_result.result == GateResult.PASS_BY_FAIL_OPEN:
                logger.warning(f"{tag}fact_guard PASS_BY_FAIL_OPEN: {fg_result.error_msg}")
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"{tag}fact_guard 调用异常 {exc}，按 fail_open 放行")

    return rewritten.strip()


def _build_deai_system_prompt(platform: str = "wechat", target_audience: str = "public") -> str:
    """Build the de-AI system prompt with style-aware register guidance."""
    from app.agents.prompts.audiences import resolve_writing_style
    from app.agents.prompts.fact_preservation_rules import REWRITE_FACT_BLOCK
    style = resolve_writing_style(platform, target_audience)
    base = (
        f"你是一位给健康媒体写专栏的临床医生。当前文章风格是「{style['name']}」。\n"
        f"语域：{style['register']}\n\n"
        f"改写任务的规则：\n"
        f"- 保留全部事实、数据和引用标注[N]，不增不减医学内容\n"
        f"- 语域保持一致：{style['forbidden']}\n"
        f"- 每句话都要承载信息，不写修辞性铺垫和情绪化渲染\n"
        f"- 情感色彩：{style['emotion']}\n"
        f"- 典型表达（参考）：{style['typical']}"
    )
    return f"{base}\n\n{REWRITE_FACT_BLOCK}"


def _resolve_deai_system_prompt(platform: str = "wechat", target_audience: str = "public") -> str:
    """若 prompt-example/prompts/deai/system_override.txt 非空则整段替换，否则用风格感知的动态 system。

    不论走 override 还是动态 system，末尾都追加 REWRITE_FACT_BLOCK 信息保真禁令
    （P0-2 / R3：禁令必须始终注入，不允许 override 文件覆盖）。
    """
    from app.agents.prompts.loader import load_deai_system_override
    from app.agents.prompts.fact_preservation_rules import REWRITE_FACT_BLOCK
    override = load_deai_system_override()
    if override:
        return f"{override}\n\n{REWRITE_FACT_BLOCK}"
    return _build_deai_system_prompt(platform, target_audience)


# ────────────────────────────────────────────
# 多轮改写：第 2 轮 user prompt 头部提示（P0-2 / R1）
# ────────────────────────────────────────────
#
# R1 决策：第 2 轮不给上一轮改写结果，让 LLM 把当前段落当作原文做"句式微调"。
# 不在 prompt 里塞"这是已经改过一轮的"，避免 LLM 在第 1 轮基础上做累积改动。
# 但需要明示"第 2 轮重点是句式微调"，否则 LLM 会做完整改动量，导致改动过激。

_R2_HEAD_HINT = """\
【第 2 轮微调】
你看到的就是原文段落。本轮重点是段落内部的句式微调和连接词替换：
- 不做大幅重写，不调整段落结构
- 优先打磨节奏（长短句交替、避免连续 3 句同结构）和段首连接词
- 信息保真禁令请严格遵守（见 system message）

"""


def _deai_rewrite_template() -> str:
    from app.agents.prompts.loader import load_deai_rewrite_full_template
    return load_deai_rewrite_full_template() or _DEAI_REWRITE_PROMPT


def _deai_opening_template() -> str:
    from app.agents.prompts.loader import load_deai_opening_template
    return load_deai_opening_template() or _DEAI_OPENING_PROMPT


def _deai_ending_template() -> str:
    from app.agents.prompts.loader import load_deai_ending_template
    return load_deai_ending_template() or _DEAI_ENDING_PROMPT


def _deai_paragraph_template() -> str:
    from app.agents.prompts.loader import load_deai_paragraph_template
    return load_deai_paragraph_template() or _DEAI_PARAGRAPH_PROMPT


def _compute_section_cap(
    content_format: str,
    section_type: str,
    target_word_count: int | None = None,
    platform: str = "wechat",
    skip_sections: list[str] | None = None,
) -> int | None:
    """计算本节字数硬上限。

    优先级：
      1. task_prompts._SECTION_MAX_WC 显式定义（article / contest_article 已配）
      2. 兜底：从 _SECTION_WORD_RATIOS 按比例算 = 节预算 × 1.3（30% 缓冲）
         覆盖 story / debunk / qa_article / research_read 等有 ratio 表的形式
      3. 都没有则返回 None（改写器 validator 回退到老的比例校验）
    """
    try:
        from app.agents.prompts.task_prompts import (
            _SECTION_MAX_WC,
            _SECTION_WORD_RATIOS,
            _PLATFORM_DEFAULT_WORD_COUNT,
        )

        explicit = _SECTION_MAX_WC.get(content_format, {}).get(section_type)
        if explicit:
            return explicit

        ratios = _SECTION_WORD_RATIOS.get(content_format, {})
        if not ratios or section_type not in ratios:
            return None

        # 跳过章节后按比例重分配（与 task_prompts._section_word_target 同口径）
        skip = set(skip_sections or [])
        active_ratios = {k: v for k, v in ratios.items() if k not in skip and v > 0}
        s_act = sum(active_ratios.values())
        if section_type not in active_ratios or s_act <= 0:
            return None

        total = target_word_count or _PLATFORM_DEFAULT_WORD_COUNT.get(platform, 1500)
        target_chars = int(total * active_ratios[section_type] / s_act)
        # 30% 缓冲；最低 80 字保护，避免对极短章节（如 research_read.one_liner）
        # validator 把所有合理改写都丢弃
        return max(80, int(target_chars * 1.3))
    except Exception:
        return None


def _compute_section_word_target(
    content_format: str,
    section_type: str,
    target_word_count: int | None,
    platform: str,
    skip_sections: list[str] | None,
) -> str:
    """复用 task_prompts 的章节字数指引（如 '80-130字'），未注册的形式返回空串。"""
    try:
        from app.agents.prompts.task_prompts import _section_word_target
        return _section_word_target({
            "content_format": content_format,
            "section_type": section_type,
            "target_word_count": target_word_count,
            "platform": platform,
            "skip_sections": skip_sections or [],
        }) or ""
    except Exception:
        return ""


def _build_full_section_cap_hint(
    cap_chars: int | None,
    word_target_str: str,
) -> str:
    """构造第 1 轮全文级改写时追加在 user message 头部的字数硬约束提示。"""
    if not cap_chars:
        return ""
    target = f"目标 {word_target_str}，" if word_target_str else ""
    return (
        f"【本节字数硬约束】{target}绝对上限 {cap_chars} 字（含标点和引用标注）。"
        f"超出会被系统丢弃改写结果；写完即止，不要靠铺陈或重复凑字数。"
    )


def _build_para_cap_hint(para_cap: int | None) -> str:
    """构造第 2 轮逐段改写时追加在 user message 头部的段落级字数提示。"""
    if not para_cap:
        return ""
    return (
        f"【本段字数约束】目标 ~{int(para_cap * 0.8)} 字，硬上限 {int(para_cap * 1.2)} 字。"
        f"超出会被系统丢弃改写结果；保持与原段相近的规模，不要展开新论据。"
    )


async def rewrite_to_reduce_ai(
    content: str,
    section_type: str = "",
    model_hint: str | None = None,
    article_id: int | None = None,
    article_default_model: str | None = None,
    platform: str = "wechat",
    target_audience: str = "public",
    content_format: str = "article",
    target_word_count: int | None = None,
    skip_sections: list[str] | None = None,
) -> tuple[str, bool]:
    """
    对已生成的内容进行去AI化改写（单轮，兼容旧调用）。

    Returns:
        (rewritten_content, was_rewritten)
    """
    if not content or len(content.strip()) < 100:
        return content, False

    cap_chars = _compute_section_cap(
        content_format, section_type,
        target_word_count=target_word_count,
        platform=platform,
        skip_sections=skip_sections,
    )
    word_target_str = _compute_section_word_target(
        content_format, section_type, target_word_count, platform, skip_sections,
    )
    cap_hint = _build_full_section_cap_hint(cap_chars, word_target_str)

    sys_prompt = _resolve_deai_system_prompt(platform, target_audience)
    user_content = _deai_rewrite_template().format(content=content)
    if cap_hint:
        user_content = f"{cap_hint}\n\n{user_content}"

    messages = [
        {"role": "system", "content": sys_prompt},
        {"role": "user", "content": user_content},
    ]

    raw = await _call_llm(messages, article_id, article_default_model)
    result = _validate_rewrite(content, raw, "单轮改写", cap_chars=cap_chars)
    if result is None:
        return content, False

    logger.info(
        f"去AI化改写完成：原文{len(content)}字 → 改写{len(result)}字 "
        f"(比例{len(result) / len(content):.2f})"
    )
    return result, True


def _create_fact_guard_summary():
    """安全创建 FactGuardSummary（fact_guard 模块不可用时返回 None）。"""
    try:
        from app.services.enhancement.fact_guard import FactGuardSummary
        return FactGuardSummary()
    except Exception:
        return None


async def rewrite_multi_pass(
    content: str,
    section_type: str = "",
    article_id: int | None = None,
    article_default_model: str | None = None,
    on_progress: Any = None,
    platform: str = "wechat",
    target_audience: str = "public",
    content_format: str = "article",
    target_word_count: int | None = None,
    skip_sections: list[str] | None = None,
) -> tuple[str, bool, dict[str, Any]]:
    """
    多轮去AI化改写：
      第1轮：全文级三层七技法改写
      第2轮：段落级定向改写（仅改写仍有高风险的段落）

    Args:
        on_progress: 可选回调 async callable(message: str) 用于汇报进度
        content_format / target_word_count / skip_sections: 用于查 task_prompts._SECTION_MAX_WC，
            把本节字数硬上限同时注入 prompt 与 validator，避免改写阶段把字数推爆

    Returns:
        (final_content, was_rewritten, stats)
    """
    if not content or len(content.strip()) < 100:
        return content, False, {"rounds": 0}

    cap_chars = _compute_section_cap(
        content_format, section_type,
        target_word_count=target_word_count,
        platform=platform,
        skip_sections=skip_sections,
    )
    word_target_str = _compute_section_word_target(
        content_format, section_type, target_word_count, platform, skip_sections,
    )
    full_cap_hint = _build_full_section_cap_hint(cap_chars, word_target_str)

    stats: dict[str, Any] = {
        "rounds": 0,
        "pass1_applied": False,
        "pass2_applied": False,
        "section_cap": cap_chars,
    }
    fg_summary = _create_fact_guard_summary()
    sys_prompt = _resolve_deai_system_prompt(platform, target_audience)

    # ── 第1轮：全文级改写 ──
    if on_progress:
        try:
            await on_progress("正在执行第1轮改写（全文改写）...")
        except Exception:
            pass

    user_content_p1 = _deai_rewrite_template().format(content=content)
    if full_cap_hint:
        user_content_p1 = f"{full_cap_hint}\n\n{user_content_p1}"

    messages_p1 = [
        {"role": "system", "content": sys_prompt},
        {"role": "user", "content": user_content_p1},
    ]

    raw_p1 = await _call_llm(messages_p1, article_id, article_default_model)
    result_p1 = _validate_rewrite(
        content, raw_p1, "第1轮",
        cap_chars=cap_chars,
        fact_guard_summary=fg_summary,
    )

    if result_p1 is None:
        logger.warning("第1轮全文改写失败，跳过进入第2轮逐段改写")
        current = content
    else:
        current = result_p1
        stats["rounds"] = 1
        stats["pass1_applied"] = True
        stats["pass1_len_before"] = len(content)
        stats["pass1_len_after"] = len(current)
        logger.info(
            f"第1轮改写完成：{len(content)}字 → {len(current)}字 "
            f"(比例{len(current) / len(content):.2f})"
        )

    # ── 第2轮：逐段独立风格改写（每段不同 prompt，避免风格漂移）──
    from app.services.verification.pipeline import detect_ai_patterns_by_paragraph

    paragraphs = detect_ai_patterns_by_paragraph(current)
    total_paras = len(paragraphs)
    risky = [p for p in paragraphs if p["risk_level"] in ("high", "medium")]

    # 开头/结尾段强制加入改写列表（这两处最暴露 AI）
    # 例外：本节预算极小（cap < 200，如 contest_article 的 conclusion=80/misconception=130）时，
    # 强制改写极易触发"读者入口/行动建议"等扩写指令而冲爆字数，改为仅按风险检测自然加入
    force_endpoints = not (cap_chars and cap_chars < 200)
    first_idx = 0
    last_idx = total_paras - 1 if total_paras > 0 else 0
    risky_indices = {p["index"] for p in risky}
    if force_endpoints:
        for p in paragraphs:
            if p["index"] in (first_idx, last_idx) and p["index"] not in risky_indices:
                risky.append(p)
                risky_indices.add(p["index"])

    if not risky:
        logger.info("无需改写的段落，跳过第2轮")
        return current, stats.get("pass1_applied", False), stats

    if on_progress:
        try:
            await on_progress(f"正在执行第2轮改写（{len(risky)}个段落逐段独立风格改写）...")
        except Exception:
            pass

    # 段级 cap：按节 cap 均摊到段落数，留 1.5× 余量给段长不均，最低 60 字
    para_cap = None
    if cap_chars and total_paras > 0:
        para_cap = max(60, int(cap_chars / max(total_paras, 1) * 1.5))
    para_cap_hint = _build_para_cap_hint(para_cap)

    stats["pass2_risky_count"] = len(risky)
    pass2_replaced = 0

    for enum_i, p in enumerate(risky):
        original_para = p.get("full_text") or p.get("text", "")
        if not original_para or len(original_para.strip()) < 20:
            continue

        problem_lines = []
        for issue in p.get("issues", []):
            problem_lines.append(f"- [{issue['severity']}] {issue['type']}: {issue.get('matched', '')}")
        for sug in p.get("suggestions", []):
            problem_lines.append(f"- 建议: {sug}")

        problem_desc = "\n".join(problem_lines) if problem_lines else "该段落被 AIGC 检测器标记为高风险，请大幅改写句式和用词。"

        # 根据段落位置选择 prompt：开头/结尾使用专用 prompt，中间段落轮换风格
        para_idx = p["index"]
        if para_idx == first_idx:
            user_prompt = _deai_opening_template().format(
                problem_description=problem_desc,
                paragraph=original_para,
            )
            style_label = "开头段专用"
        elif para_idx == last_idx:
            user_prompt = _deai_ending_template().format(
                problem_description=problem_desc,
                paragraph=original_para,
            )
            style_label = "结尾段专用"
        else:
            style = _STYLE_PROFILES[enum_i % len(_STYLE_PROFILES)]
            user_prompt = _deai_paragraph_template().format(
                problem_description=problem_desc,
                style_instruction=style["instruction"],
                paragraph=original_para,
            )
            style_label = style["name"]

        # 头部依次叠加：R1 第 2 轮微调提示 → 段级字数约束 → 模板正文
        user_prompt = f"{_R2_HEAD_HINT}{user_prompt}"
        if para_cap_hint:
            user_prompt = f"{para_cap_hint}\n\n{user_prompt}"

        logger.info(f"第2轮段落{para_idx}：使用「{style_label}」改写")

        messages_p2 = [
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": user_prompt},
        ]

        raw_p2 = await _call_llm(messages_p2, article_id, article_default_model)
        if not raw_p2 or len(raw_p2.strip()) < 10:
            continue

        rewritten_para = raw_p2.strip()
        new_para_chars = len(rewritten_para)
        orig_para_chars = len(original_para)

        if para_cap:
            # 段落级硬上下限：与节 cap 对齐，原文越接近 cap 越不允许扩张
            para_upper = min(int(orig_para_chars * 1.3), int(para_cap * 1.2))
            para_upper = max(para_upper, para_cap)
            para_lower = max(20, int(orig_para_chars * 0.3))
            if new_para_chars < para_lower or new_para_chars > para_upper:
                logger.warning(
                    f"第2轮段落{para_idx}改写字数 {new_para_chars} 超出区间 "
                    f"[{para_lower}, {para_upper}]（原段 {orig_para_chars}，段 cap {para_cap}），跳过"
                )
                continue
        else:
            para_ratio = new_para_chars / orig_para_chars if orig_para_chars else 1.0
            if para_ratio < 0.3 or para_ratio > 2.5:
                logger.warning(f"第2轮段落{para_idx}改写长度异常(比例{para_ratio:.2f})，跳过")
                continue

        original_para_refs = set(re.findall(r"\[(\d+)\]", original_para))
        rewritten_para_refs = set(re.findall(r"\[(\d+)\]", rewritten_para))
        if original_para_refs and not rewritten_para_refs:
            logger.warning(f"第2轮段落{para_idx}改写丢失引用，跳过")
            continue

        # P0-1 / fact_guard 段级强 gate
        fg_cfg_p2 = _build_fact_guard_config()
        if fg_cfg_p2 is not None:
            try:
                from app.services.enhancement.fact_guard import (
                    validate_facts_consistency,
                    GateResult,
                )
                fg_result_p2 = validate_facts_consistency(
                    original_para, rewritten_para, fg_cfg_p2,
                )
                if fg_summary is not None:
                    fg_summary.record(fg_result_p2)
                if fg_result_p2.result == GateResult.REJECT_STRONG:
                    logger.warning(
                        f"第2轮段落{para_idx} fact_guard REJECT_STRONG: "
                        f"failed={fg_result_p2.failed_dimensions}，跳过"
                    )
                    continue
                if (fg_result_p2.result == GateResult.REJECT_WEAK
                        and fg_cfg_p2.hard_block):
                    logger.warning(
                        f"第2轮段落{para_idx} fact_guard REJECT_WEAK: "
                        f"failed={fg_result_p2.failed_dimensions}，跳过"
                    )
                    continue
            except Exception as exc:  # noqa: BLE001
                logger.warning(f"第2轮段落{para_idx} fact_guard 异常 {exc}，按 fail_open 放行")

        _start = 0
        while True:
            idx = current.find(original_para, _start)
            if idx == -1:
                break
            current = current[:idx] + rewritten_para + current[idx + len(original_para):]
            _start = idx + len(rewritten_para)
            pass2_replaced += 1

    stats["pass2_applied"] = pass2_replaced > 0
    stats["pass2_replaced"] = pass2_replaced
    if pass2_replaced > 0:
        stats["rounds"] = max(stats.get("rounds", 0), 2)

    logger.info(f"第2轮完成：逐段改写了 {pass2_replaced}/{len(risky)} 个段落")

    # 把 fact_guard 累计统计塞回 stats，给 generator 写入 report
    if fg_summary is not None:
        stats["fact_guard"] = fg_summary.to_dict()

    was_rewritten = stats.get("pass1_applied", False) or pass2_replaced > 0
    return current, was_rewritten, stats
