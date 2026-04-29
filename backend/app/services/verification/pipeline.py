"""
防编造验证流水线
按形式选择性执行：skip_verify（图示类）/ skip_level（脚本类+图示类）
支持 use_llm_verification 启用 LLM 深度核查（或环境变量 USE_LLM_VERIFICATION=1）
"""
import json
import os
import re
from typing import Any


async def run_verification(
    content: str,
    article_id: int | None,
    rag_context: list[dict],
    target_audience: str,
    skip_verify: bool = False,
    skip_level: bool = False,
    use_llm_verification: bool | None = None,
) -> tuple[str, dict[str, Any]]:
    """
    返回 (verified_content, report)
    report: { claims, data_warnings, absolute_terms, reading_level }
    use_llm_verification: 为 None 时从环境变量 USE_LLM_VERIFICATION 读取
    """
    if use_llm_verification is None:
        use_llm_verification = os.environ.get("USE_LLM_VERIFICATION", "").lower() in ("1", "true", "yes")
    report: dict[str, Any] = {}

    # 医学声明核实（skip_verify 时跳过）
    if not skip_verify:
        if use_llm_verification:
            content, report["claims"] = await _verify_claims_llm(content, rag_context)
        else:
            content, report["claims"] = await _verify_claims(content, rag_context, article_id)
    else:
        report["claims"] = {"skipped": True, "reason": "图示类形式，跳过声明核实"}

    # 数据占位符 + 绝对化表述（所有形式均执行）
    if use_llm_verification:
        verified_list = ""
        if report.get("claims") and isinstance(report["claims"], dict):
            claims_list = report["claims"].get("claims", [])
            if isinstance(claims_list, list):
                verified_list = "; ".join(
                    c.get("claim_text", c.get("text", str(c)))[:60]
                    for c in claims_list
                    if c.get("verification_status") == "verified"
                )[:300]
        content, report["data_warnings"], report["absolute_terms"] = await _verify_fact_llm(
            content, verified_data_list=verified_list
        )
    else:
        content, report["data_warnings"] = await _verify_data_placeholders(content)
        content, report["absolute_terms"] = await _detect_absolute_terms(content)

    # 阅读难度（skip_level 时跳过）
    if not skip_level:
        if use_llm_verification:
            report["reading_level"] = await _check_reading_level_llm(content, target_audience)
        else:
            report["reading_level"] = await _check_reading_level(content, target_audience)
    else:
        report["reading_level"] = {"skipped": True, "reason": "脚本类/图示类形式，跳过阅读难度检查"}

    return content, report


def _extract_claim_candidates(content: str) -> list[dict]:
    """提取疑似医学声明句子（含数据/研究/根据等关键词）"""
    import re
    # 按句分割
    sentences = re.split(r'[。！？\n]', content)
    candidates = []
    claim_markers = ["研究表明", "根据", "数据显示", "发病率", "患病率", "有效率", "治愈率", "约", "%", "研究显示", "临床显示"]
    for s in sentences:
        s = s.strip()
        if len(s) < 10:
            continue
        if any(m in s for m in claim_markers):
            candidates.append({"text": s[:120], "status": "pending"})
    return candidates[:10]  # 最多10条


def _rag_supports_claim(claim_text: str, rag_context: list) -> bool:
    return _best_evidence_for_claim(claim_text, rag_context) is not None


def _best_evidence_for_claim(claim_text: str, rag_context: list) -> dict | None:
    """从 RAG 条目中选与声明重叠最多的一条，供个人核对（非合规审计）。"""
    if not rag_context:
        return None
    clean = "".join(c for c in claim_text if "\u4e00" <= c <= "\u9fff" or c.isalnum())[:80]
    if len(clean) < 4:
        return None
    best_ch = None
    best_hits = 0
    step = 2 if len(clean) > 24 else 1
    for ch in rag_context:
        body = str(ch.get("content", ""))[:1400]
        hits = 0
        for i in range(0, max(1, len(clean) - 3), step):
            frag = clean[i : i + 4]
            if len(frag) >= 4 and frag in body:
                hits += 1
        if hits > best_hits:
            best_hits = hits
            best_ch = ch
    if best_hits < 1 or not best_ch:
        return None
    snip = (best_ch.get("content") or "")[:280].replace("\n", " ").strip()
    if len(snip) > 220:
        snip = snip[:217] + "…"
    out: dict = {
        "evidence_snippet": snip,
        "evidence_source": str(best_ch.get("source", "unknown")),
        "chunk_id": best_ch.get("chunk_id"),
    }
    pid = best_ch.get("paper_id")
    if pid is not None:
        try:
            out["paper_id"] = int(pid)
        except (TypeError, ValueError):
            pass
    return out


async def _verify_claims(content: str, rag_context: list, article_id: int | None) -> tuple[str, dict]:
    """
    医学声明核实：提取疑似声明，与 RAG 上下文匹配
    返回 (content, { verified: [], pending: [], summary } )
    """
    candidates = _extract_claim_candidates(content)
    verified = []
    pending = []
    for c in candidates:
        text = c["text"]
        ev = _best_evidence_for_claim(text, rag_context)
        if ev:
            preview = text[:80] + "…" if len(text) > 80 else text
            row = {"text": preview, "match_text": text, **ev}
            verified.append(row)
        else:
            preview = text[:80] + "…" if len(text) > 80 else text
            pending.append({"text": preview, "match_text": text, "message": "待补充权威来源"})
    return content, {
        "verified": verified,
        "pending": pending,
        "verified_count": len(verified),
        "pending_count": len(pending),
    }


async def _verify_data_placeholders(content: str) -> tuple[str, list]:
    """检测 [DATA:] 和 [[待补充:...]] 占位符"""
    import re
    warnings = []
    for m in re.finditer(r"\[DATA:[^\]]*\]", content):
        warnings.append({"text": m.group(), "message": "需补充权威数据"})
    for m in re.finditer(r"\[\[待补充[：:][^\]]*\]\]", content):
        warnings.append({"text": m.group(), "message": "需补充文献支持"})
    return content, warnings


async def _detect_absolute_terms(content: str) -> tuple[str, list]:
    """检测绝对化表述（与提示词设计方案 v1 规则三对齐）"""
    absolute_words = [
        "一定会", "必然", "绝对", "百分百", "百分之百", "永远", "肯定",
        "完全治愈", "完全可以根治", "永久有效", "从不", "完全可以",
    ]
    issues = []
    for w in absolute_words:
        if w in content:
            issues.append({"text": w, "suggestion": "改用「可能」「有助于」「研究显示」「在多数情况下」等"})
    return content, issues


def _format_rag_context(rag_context: list[dict]) -> str:
    """将 RAG 上下文格式化为可读文本"""
    if not rag_context:
        return "（无参考资料）"
    parts = []
    for i, c in enumerate(rag_context[:5], 1):
        text = c.get("content", "") or c.get("text", "") or str(c)
        if isinstance(text, str) and len(text) > 500:
            text = text[:500] + "..."
        parts.append(f"[参考{i}]\n{text}")
    return "\n\n".join(parts)


async def _verify_claims_llm(content: str, rag_context: list[dict]) -> tuple[str, dict]:
    """医学声明核实（LLM）"""
    from app.agents.prompts.verification import CLAIM_VERIFY_PROMPT
    from app.services.llm.openai_client import chat_completion, call_llm_with_fallback
    from app.services.llm.manager import TaskTier
    from app.core.config import is_saas

    rag_str = _format_rag_context(rag_context)
    prompt = CLAIM_VERIFY_PROMPT.format(content=content[:4000], rag_context=rag_str)
    try:
        msgs = [{"role": "user", "content": prompt}]
        if is_saas():
            resp = await call_llm_with_fallback("verification", msgs, stream=False)
        else:
            resp = await chat_completion(messages=msgs, stream=False, task=TaskTier.BALANCED)
        raw = (resp or "").strip()
        m = re.search(r"\{[\s\S]*\}", raw)
        if m:
            obj = json.loads(m.group())
            claims = obj.get("claims", [])
            verified = [c for c in claims if c.get("verification_status") == "verified"]
            pending = [c for c in claims if c.get("verification_status") != "verified"]
            verified_rows = []
            for c in verified:
                ct = (c.get("claim_text") or "").strip()
                if not ct:
                    continue
                preview = ct[:80] + ("…" if len(ct) > 80 else "")
                ev = _best_evidence_for_claim(ct, rag_context) or {}
                verified_rows.append({"text": preview, "match_text": ct, **ev})
            pending_rows = []
            for c in pending:
                ct = (c.get("claim_text") or "").strip()
                if not ct:
                    continue
                preview = ct[:80] + ("…" if len(ct) > 80 else "")
                pending_rows.append(
                    {
                        "text": preview,
                        "match_text": ct,
                        "message": c.get("note", "待补充权威来源"),
                    }
                )
            return content, {
                "claims": claims,
                "overall_assessment": obj.get("overall_assessment", "needs_review"),
                "review_priority": obj.get("review_priority", []),
                "verified": verified_rows,
                "pending": pending_rows,
                "verified_count": len(verified_rows),
                "pending_count": len(pending_rows),
                "source": "llm",
            }
    except Exception:
        pass
    content2, fallback_report = await _verify_claims(content, rag_context, None)
    return content2, fallback_report


async def _verify_fact_llm(
    content: str, verified_data_list: str = "",
) -> tuple[str, list, list]:
    """数据占位符 + 绝对化表述检测（LLM）"""
    from app.agents.prompts.verification import FACT_VERIFY_PROMPT
    from app.services.llm.openai_client import chat_completion, call_llm_with_fallback
    from app.services.llm.manager import TaskTier
    from app.core.config import is_saas

    prompt = FACT_VERIFY_PROMPT.format(
        content=content[:4000],
        verified_data_list=verified_data_list or "（无，本次未传入已核实数据）",
    )
    try:
        msgs = [{"role": "user", "content": prompt}]
        if is_saas():
            resp = await call_llm_with_fallback("verification", msgs, stream=False)
        else:
            resp = await chat_completion(messages=msgs, stream=False, task=TaskTier.BALANCED)
        raw = (resp or "").strip()
        m = re.search(r"\{[\s\S]*\}", raw)
        if m:
            obj = json.loads(m.group())
            data_warnings = obj.get("data_warnings", [])
            absolute_terms = obj.get("absolute_terms", [])
            dw = [{"text": w.get("original_text", ""), "message": w.get("suggestion", "需补充权威数据")} for w in data_warnings]
            at = [{"text": t.get("problematic_word", ""), "suggestion": t.get("suggested_replacement", "")} for t in absolute_terms]
            return content, dw, at
    except Exception:
        pass
    _, dw = await _verify_data_placeholders(content)
    _, at = await _detect_absolute_terms(content)
    return content, dw, at


async def _check_reading_level_llm(content: str, target_audience: str) -> dict:
    """阅读难度检查（LLM）"""
    from app.agents.prompts.verification import (
        READING_LEVEL_PROMPT,
        AUDIENCE_LEVEL_SPECS,
        DEFAULT_LEVEL_SPEC,
    )
    from app.agents.prompts.audiences import AUDIENCE_PROFILES
    from app.services.llm.openai_client import chat_completion, call_llm_with_fallback
    from app.services.llm.manager import TaskTier
    from app.core.config import is_saas

    audience = AUDIENCE_PROFILES.get(target_audience, AUDIENCE_PROFILES["public"])
    spec = AUDIENCE_LEVEL_SPECS.get(target_audience, DEFAULT_LEVEL_SPEC)
    audience_standard = f"{audience['desc']}；词汇：{audience['vocabulary']}；句长：{audience['sentence']}"
    prompt = READING_LEVEL_PROMPT.format(
        target_audience=target_audience,
        audience_standard=audience_standard,
        content=content[:3000],
        max_term_density=spec["max_term_density"],
        max_sentence_len=spec["max_sentence_len"],
    )
    try:
        msgs = [{"role": "user", "content": prompt}]
        if is_saas():
            resp = await call_llm_with_fallback("verification", msgs, stream=False)
        else:
            resp = await chat_completion(messages=msgs, stream=False, task=TaskTier.BALANCED)
        raw = (resp or "").strip()
        m = re.search(r"\{[\s\S]*\}", raw)
        if m:
            obj = json.loads(m.group())
            issues = obj.get("issues", [])
            return {
                "passed": obj.get("passed", len(issues) == 0),
                "audience": target_audience,
                "target_audience": target_audience,
                "stats": obj.get("stats", {}),
                "issues": [{"type": "general", "message": i} if isinstance(i, str) else i for i in issues],
                "suggestions": obj.get("suggestions", []),
                "source": "llm",
            }
    except Exception:
        pass
    return await _check_reading_level(content, target_audience)


async def _check_reading_level(content: str, target_audience: str) -> dict:
    """阅读难度检查 - jieba 分词估算术语密度"""
    try:
        import jieba
        words = list(jieba.cut(content))
        total = len(words)
        if total == 0:
            return {"passed": True, "audience": target_audience, "issues": [], "term_density": 0}
        # 简单启发：长词(>=4字)占比高则偏专业
        long_words = sum(1 for w in words if len(w) >= 4)
        density = long_words / total
        issues = []
        if target_audience == "public" and density > 0.15:
            issues.append({"type": "term_density", "message": f"专业术语占比约 {density:.0%}，建议简化以适配公众"})
        elif target_audience == "patient" and density > 0.25:
            issues.append({"type": "term_density", "message": f"专业术语占比约 {density:.0%}，建议增加通俗解释"})
        return {
            "passed": len(issues) == 0,
            "audience": target_audience,
            "issues": issues,
            "term_density": round(density, 3),
            "word_count": total,
        }
    except ImportError:
        return {"passed": True, "audience": target_audience, "issues": []}


async def run_export_check(content: str) -> dict[str, Any]:
    """
    导出前检查：仅检测数据占位符与绝对化表述
    返回 { can_export, data_warnings, absolute_terms, message }
    """
    _, data_warnings = await _verify_data_placeholders(content)
    _, absolute_terms = await _detect_absolute_terms(content)
    has_warnings = len(data_warnings) > 0 or len(absolute_terms) > 0
    msg = ""
    if data_warnings:
        msg += f"存在 {len(data_warnings)} 处数据/文献占位符需补充；"
    if absolute_terms:
        msg += f"存在 {len(absolute_terms)} 处绝对化表述建议修改。"
    return {
        "can_export": not has_warnings,
        "data_warnings": data_warnings,
        "absolute_terms": absolute_terms,
        "message": msg.strip() or None,
    }


def _strip_markdown(text: str) -> str:
    """剥离 Markdown 格式标记，保留纯文本用于模式检测"""
    import re
    text = re.sub(r"#{1,6}\s*", "", text)
    text = re.sub(r"\*{1,3}([^*]+)\*{1,3}", r"\1", text)
    text = re.sub(r"_{1,3}([^_]+)_{1,3}", r"\1", text)
    text = re.sub(r"^>\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\s*[-*+]\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\s*\d+\.\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    return text


def detect_ai_patterns(content: str) -> dict[str, Any]:
    """
    检测高频 AI 写作模式，返回各类别匹配详情及整体评分。
    评分 0-100，100 表示无明显 AI 味，低于 60 建议人工润色。
    """
    import re

    clean = _strip_markdown(content)

    results: dict[str, list[str]] = {
        "share_call": [],
        "list_cliche": [],
        "mechanical_transition": [],
        "excessive_modifier": [],
        "ai_ending": [],
        "ai_connector": [],
        "metaphor_density": [],
        "formulaic_rhetoric": [],
    }

    _SHARE_CALL_PATTERNS = [
        r"转发给.{0,6}人", r"分享给.{0,6}人", r"收藏备用", r"赶紧转给",
        r"一起.{0,4}行动吧", r"赶紧行动起来", r"快分享", r"快收藏",
        r"分享给家人", r"转给.{0,4}需要的人",
    ]
    for pat in _SHARE_CALL_PATTERNS:
        for m in re.finditer(pat, clean):
            results["share_call"].append(m.group())

    _LIST_CLICHE_PATTERNS = [
        r"记住这[几三四五六七八九十\d]+[点件个条招步]",
        r"做好这[几三四五六七八九十\d]+[点件个条招步]",
        r"牢记这[几三四五六七八九十\d]+[点件个条招步]",
        r"掌握这[几三四五六七八九十\d]+[点件个条招步]",
        r"做到这[几三四五六七八九十\d]+[点件个条招步]",
        r"这[几三四五六七八九十\d]+[点件个条招步].{0,4}(很重要|必须|一定|更清晰|更轻松)",
    ]
    for pat in _LIST_CLICHE_PATTERNS:
        for m in re.finditer(pat, clean):
            results["list_cliche"].append(m.group())

    _MECHANICAL_TRANSITIONS = [
        "下面我们来看", "下面我们来介绍", "接下来讲讲", "接下来我们来说说",
        "接下来让我们", "下面我们就来", "首先我们来了解",
        "那么到底", "话不多说", "废话不多说",
        "那么，如何", "那么，为什么", "那么，究竟",
    ]
    for phrase in _MECHANICAL_TRANSITIONS:
        if phrase in clean:
            results["mechanical_transition"].append(phrase)

    _MODIFIER_PATTERNS = [
        r"(非常|十分|极其|特别|格外|尤其|相当).{0,2}(重要|关键|必要|有效|显著)",
        r"(至关重要|举足轻重|不可或缺|意义重大|不容忽视)",
        r"具有统计学意义的显著",
        r"深刻影响",
    ]
    for pat in _MODIFIER_PATTERNS:
        for m in re.finditer(pat, clean):
            results["excessive_modifier"].append(m.group())

    _AI_ENDING_PATTERNS = [
        r"总之[，,]", r"综上所述[，,]", r"总而言之[，,]",
        r"总结一下[，,：:].{0,60}",
        r"最后[，,]希望",
        r"让我们一起.{0,10}[！!。.]",
        r"愿每一?位.{0,15}[！!。.]",
        r"健康之路.{0,10}[！!。.]",
        r"一步步.{0,20}(端上|走向|迈向|实现)",
        r"让科学.{0,10}(帮助|守护|引领)",
        r"共同.{0,6}(绘制|描绘).{0,6}(蓝图|画卷)",
        r"(守护|呵护).{0,4}(彼此|健康|生命)",
    ]
    for pat in _AI_ENDING_PATTERNS:
        for m in re.finditer(pat, clean, re.MULTILINE):
            results["ai_ending"].append(m.group()[:60])

    _AI_CONNECTOR_PATTERNS = [
        r"简单说[，,]",
        r"换句话说[，,]",
        r"也就是说[，,]",
        r"不仅如此[，,]",
        r"值得一提的是[，,]",
        r"更重要的是[，,]",
        r"需要注意的是[，,]",
        r"需要了解的是[，,]",
    ]
    for pat in _AI_CONNECTOR_PATTERNS:
        for m in re.finditer(pat, clean):
            results["ai_connector"].append(m.group())
    if len(results["ai_connector"]) <= 1:
        results["ai_connector"] = []

    _METAPHOR_MARKERS = [
        r"就像", r"好比", r"好似", r"想象成", r"可以比作",
        r"就好比", r"如同", r"犹如", r"好像.{0,4}一样",
        r"像.{1,6}一样", r"比喻成",
    ]
    for pat in _METAPHOR_MARKERS:
        for m in re.finditer(pat, clean):
            results["metaphor_density"].append(m.group())
    if len(results["metaphor_density"]) <= 3:
        results["metaphor_density"] = []

    _FORMULAIC_PATTERNS = [
        r"不是.{2,15}[，,]\s*而是.{2,15}[。！]",
        r"并肩.{0,6}(作战|前行|同行)",
        r"(清醒|从容|坦然).{0,4}(和|与).{0,4}(清醒|从容|坦然|勇气|智慧)",
        r"(你|我们|每一?位).{0,10}(并肩|携手|一起).{0,10}(前行|前进|走下去|面对)",
        r"让.{0,8}(帮助|守护|引领).{0,8}(我们|彼此|每一个人)",
        r"共同.{0,6}(绘制|描绘|书写).{0,6}(蓝图|篇章|画卷)",
        r"(健康|生命|科学).{0,4}(之路|之旅|路上)",
        r"(信息透明|双向沟通|医患合作).{0,4}(的|之).{0,6}(合作|沟通|桥梁)",
    ]
    for pat in _FORMULAIC_PATTERNS:
        for m in re.finditer(pat, clean):
            results["formulaic_rhetoric"].append(m.group()[:60])

    total_issues = sum(len(v) for v in results.values())

    score = 100
    penalty_weights = {
        "share_call": 12,
        "list_cliche": 8,
        "mechanical_transition": 6,
        "excessive_modifier": 4,
        "ai_ending": 10,
        "ai_connector": 3,
        "metaphor_density": 3,
        "formulaic_rhetoric": 8,
    }
    for category, items in results.items():
        score -= len(items) * penalty_weights.get(category, 5)
    score = max(0, score)

    warnings: list[str] = []
    if results["share_call"]:
        example = results["share_call"][0]
        warnings.append(f'检测到 {len(results["share_call"])} 处分享号召语（如「{example}」），建议删除或改写')
    if results["list_cliche"]:
        example = results["list_cliche"][0]
        warnings.append(f'检测到 {len(results["list_cliche"])} 处清单式套话（如「{example}」），建议调整表述')
    if results["mechanical_transition"]:
        warnings.append(f'检测到 {len(results["mechanical_transition"])} 处机械过渡语，建议用自然衔接替换')
    if results["excessive_modifier"]:
        examples = "、".join(results["excessive_modifier"][:3])
        warnings.append(f'检测到 {len(results["excessive_modifier"])} 处多重修饰/学术腔（{examples}），建议精简')
    if results["ai_ending"]:
        example = results["ai_ending"][0]
        warnings.append(f'检测到 {len(results["ai_ending"])} 处 AI 套路结尾（如「{example}」），建议改写')
    if results["ai_connector"]:
        warnings.append(f'检测到 {len(results["ai_connector"])} 处高频 AI 连接词密集使用，建议减少')
    if results["metaphor_density"]:
        warnings.append(f'检测到 {len(results["metaphor_density"])} 处比喻/类比（超过 3 处），比喻密度过高，建议精简至 2-3 处')
    if results["formulaic_rhetoric"]:
        example = results["formulaic_rhetoric"][0]
        warnings.append(f'检测到 {len(results["formulaic_rhetoric"])} 处套路化修辞（如「{example}」），建议改写')

    return {
        "score": score,
        "total_issues": total_issues,
        "details": {k: v for k, v in results.items() if v},
        "warnings": warnings,
        "needs_polish": score < 60,
    }


def detect_ai_patterns_by_paragraph(content: str) -> list[dict[str, Any]]:
    """
    段落级AI特征检测（增强版）。将内容按段落拆分，多维度检测每段的AI生成特征。

    检测维度：
      1. 模式匹配（40+ 条规则）
      2. 句长统计（Burstiness）
      3. 词汇多样性（TTR）
      4. 连接词/过渡词密度
      5. 段首句式重复度（段间比较）
      6. 名词短语堆叠
      7. 标点均匀度

    返回列表，每个元素包含：
      - text: 段落原文（截断）
      - full_text: 段落原文（完整）
      - index: 段落序号（0-based）
      - risk_level: "high" / "medium" / "low"
      - issues: 命中的具体问题列表
      - suggestions: 改写建议列表
      - sentence_stats: 句长统计信息
    """
    import re
    import statistics

    clean = _strip_markdown(content)
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", clean) if p.strip() and len(p.strip()) > 10]

    if not paragraphs:
        return []

    # ── 模式库：40+ 条规则 ──

    _ISSUE_PATTERNS: list[tuple[str, str, str, str]] = [
        # --- 原有规则（优化） ---
        (r"不是.{2,15}[，,]\s*而是.{2,15}", "formulaic_rhetoric", "high", "删除「不是A」部分，直接说B"),
        (r"(值得注意的是|需要指出的是|值得一提的是|更为重要的是|更值得注意的是)[，,]?", "false_emphasis", "high", "删除该前缀，直接陈述内容"),
        (r"(首先|其次|最后|再次)[，,]", "triple_parallel", "medium", "改用非对称表达或项目符号列表"),
        (r"(一是|二是|三是)[，,]", "triple_parallel", "high", "改用两项或四项，或拆成独立短句"),
        (r"一方面.{5,50}另一方面", "symmetric_structure", "medium", "改为两段独立陈述，打破对称"),
        (r"(这篇文章想和你聊聊|让我们一起来看看|接下来让我们|让我带你了解)", "tour_guide", "high", "删除，直接进入内容"),
        (r"(守护|并肩|携手|搭档|密码|迷雾|蓝图|赋能|助力)", "ai_buzzword", "medium", "用具体描述替代空洞比喻"),
        (r"(总之|综上所述|总而言之|由此可见|因此可知)[，,]", "summary_cliche", "high", "删除，段落信息写完即停"),
        (r"保持.{0,10}(开放|清醒|积极).{0,10}(沟通|认知|心态)", "emotional_ending", "high", "改为具体行动建议"),
        (r"(你和医生|医患).{0,10}(搭档|伙伴|合作伙伴|最佳拍档)", "emotional_ending", "high", "删除，用就医提示替代"),
        (r"(请记住|请牢记)[，,].{0,30}(专业评估|专业医生|医疗建议)", "safety_filler", "medium", "精简为文末1句免责声明"),

        # --- 解释腔 ---
        (r"(简单来说|通俗地讲|形象地说|通俗来讲|简单地说)[，,]", "explainer_tone", "medium", "删除解释前缀，直接陈述"),
        (r"(换言之|用一句话概括|一言以蔽之)[，,]", "explainer_tone", "medium", "删除该短语，直接说结论"),
        (r"(可以这样理解|可以把它理解为|不妨这样想)[，,:：]", "explainer_tone", "medium", "删除引导，直接给出解释"),

        # --- AI 段落开头 ---
        (r"^(当谈到|说到|关于|提到|在.{2,8}方面).{2,20}[，,时]", "ai_opener", "medium", "改写段首，避免AI式泛泛引入"),
        (r"^(随着.{2,15}的.{2,8})[，,]", "ai_opener", "medium", "删除「随着...」开头，直接进入话题"),
        (r"^(众所周知|如前所述|正如.{2,10}所说)[，,]", "ai_opener", "medium", "删除套话开头"),

        # --- 因果套路 ---
        (r"(正因如此|正因为如此|正是因为这样)[，,]", "causal_cliche", "medium", "改用更具体的因果表述或删除"),
        (r"(这也是为什么|这就是为什么|这就是.{2,8}的原因)", "causal_cliche", "medium", "直接说结论，不用回指"),
        (r"(这意味着|这表明|这说明)[，,]", "causal_cliche", "medium", "删除指示代词开头，具体说明"),

        # --- 递进套路 ---
        (r"(不仅如此|不仅仅是这样)[，,]", "progression_cliche", "medium", "改用具体内容衔接"),
        (r"(更为关键的是|更为重要的是|更关键的是)[，,]", "progression_cliche", "medium", "删除前缀，直接陈述"),
        (r"(与此同时|在此基础上|在此之外)[，,]", "progression_cliche", "medium", "用时间状语或事实衔接替代"),
        (r"(除此之外|除了上述|在上述.{2,6}之外)[，,]", "progression_cliche", "medium", "改写或删除"),

        # --- 总结/概括套路 ---
        (r"(换句话说|也就是说|从这个角度来看|从某种意义上说)[，,]", "summary_pattern", "medium", "删除该短语，直接表达"),
        (r"(归根结底|说到底|追根溯源)[，,]", "summary_pattern", "medium", "直接给出结论"),
        (r"(不难发现|不难看出|可以看到|由此不难理解)[，,]", "summary_pattern", "medium", "删除，直接陈述发现"),

        # --- 安全/提醒套话 ---
        (r"(需要提醒的是|这里要强调|这里需要注意|必须指出|有一点需要注意)[，,的]", "safety_reminder", "medium", "删除提醒前缀，直接说内容"),
        (r"(需要注意的是|需要了解的是|需要强调的是|需要明确的是)[，,]", "safety_reminder", "medium", "删除前缀，直接陈述"),

        # --- 比喻引导 ---
        (r"(就像|好比|好似|如同|犹如).{2,20}一样", "metaphor_intro", "medium", "减少比喻使用，直接说明"),
        (r"(打个比方|可以比作|想象成|可以把.{2,10}比作)", "metaphor_intro", "medium", "删除比喻引导，用白话解释"),

        # --- 段首连接词（AI最典型特征） ---
        (r"^(然而|不过|但是|因此|此外|同时|另外|与此同时|除此之外|不仅如此|更重要的是|事实上|实际上)[，,]", "connector_opener", "high", "删除段首连接词，直接陈述事实"),

        # --- 设问自答 ---
        (r"(那么[，,]?.{2,15}(呢|吗)[？?])", "rhetorical_question", "medium", "减少设问句式，直接陈述"),
        (r"(.{2,15}到底是什么[？?])", "rhetorical_question", "medium", "改为陈述句直接给出定义"),
        (r"(为什么会这样[？?]|这又是怎么回事[？?])", "rhetorical_question", "medium", "改为陈述句"),

        # --- 精确/完美的过渡 ---
        (r"(然而|不过|但是)[，,].{0,5}(事实上|实际上|实际情况是)", "over_smooth_transition", "medium", "转折过于教科书式，简化为直接说"),
        (r"(虽然.{5,30}但是.{5,30})", "over_smooth_transition", "medium", "虽然-但是结构过于整齐，拆分或换表达"),

        # --- 排比/对称修辞 ---
        (r"既.{2,15}[，,]又.{2,15}[，,]还.{2,15}", "parallel_rhetoric", "medium", "三项排比过于工整，打破对称"),
        (r"(无论是.{2,15}还是.{2,15}都)", "parallel_rhetoric", "medium", "改用非对称表达"),

        # --- AI 味的精确概括 ---
        (r"(起着.{2,10}的作用|扮演着.{2,10}的角色|发挥着.{2,10}的作用)", "academic_tone", "medium", "简化为直接动词"),
        (r"(具有.{2,10}的(特点|特征|优势|功能|作用))", "academic_tone", "medium", "简化表达，如「具有X特点」改为直接描述"),
    ]

    # ── 连接词库（用于密度检测）──
    _CONNECTORS = [
        "然而", "不过", "但是", "因此", "此外", "同时", "另外",
        "事实上", "实际上", "其实", "当然", "毕竟", "总的来说",
        "换句话说", "也就是说", "简单来说", "具体来说", "总体而言",
        "与此同时", "除此之外", "不仅如此", "更重要的是", "值得注意的是",
        "相比之下", "相反", "尽管如此", "即便如此", "无论如何",
        "由此可见", "正因如此", "在这种情况下", "从这个角度",
    ]

    # ── 段首句式指纹（段间比较）──
    opening_fingerprints: list[str] = []
    for para in paragraphs:
        first_sent = re.split(r'[。！？!?，,]', para)[0].strip()
        fp = first_sent[:6] if len(first_sent) >= 6 else first_sent
        opening_fingerprints.append(fp)

    fp_counts: dict[str, int] = {}
    for fp in opening_fingerprints:
        if fp:
            fp_counts[fp] = fp_counts.get(fp, 0) + 1

    # ── 逐段检测 ──
    results = []

    for idx, para in enumerate(paragraphs):
        issues: list[dict[str, str]] = []
        suggestions: list[str] = []

        def _add(issue_type: str, severity: str, matched: str, suggestion: str) -> None:
            issues.append({"type": issue_type, "severity": severity, "matched": matched[:60]})
            if suggestion not in suggestions:
                suggestions.append(suggestion)

        # ─ 1. 模式匹配 ─
        for pattern, issue_type, severity, suggestion in _ISSUE_PATTERNS:
            for m in re.finditer(pattern, para):
                _add(issue_type, severity, m.group(), suggestion)

        # 设问自答的全文频率限制：统计该段的设问数量
        rhetorical_in_para = sum(1 for i in issues if i["type"] == "rhetorical_question")
        if rhetorical_in_para >= 2:
            for i in issues:
                if i["type"] == "rhetorical_question":
                    i["severity"] = "high"

        # ─ 2. 句长统计（Burstiness）─ 阈值调低
        sentences = [s.strip() for s in re.split(r'[。！？!?]', para) if s.strip() and len(s.strip()) > 1]
        sentence_lengths = [len(s) for s in sentences]

        sentence_stats: dict[str, Any] = {}
        if len(sentence_lengths) >= 2:
            mean_len = statistics.mean(sentence_lengths)
            stdev_len = statistics.stdev(sentence_lengths)
            min_len = min(sentence_lengths)
            max_len = max(sentence_lengths)
            sentence_stats = {
                "count": len(sentence_lengths),
                "mean": round(mean_len, 1),
                "stdev": round(stdev_len, 1),
                "min": min_len,
                "max": max_len,
                "range": max_len - min_len,
            }

            if stdev_len < 3.5 and len(sentence_lengths) >= 3:
                _add("low_burstiness", "high",
                     f"句长标准差={stdev_len:.1f}",
                     f"句长过于均匀（标准差{stdev_len:.1f}），插入极短句或合并短句以增加波动")
            elif stdev_len < 6.0 and len(sentence_lengths) >= 3:
                _add("low_burstiness", "medium",
                     f"句长标准差={stdev_len:.1f}",
                     f"句长较均匀（标准差{stdev_len:.1f}），建议增加长短句交替")

            threshold_short = 6 if len(sentence_lengths) >= 4 else 10
            if min_len > threshold_short and len(sentence_lengths) >= 3:
                _add("no_short_sentence", "medium",
                     f"最短句{min_len}字",
                     "缺少极短句（<=6字），建议加入断句增加节奏感")

            if max_len - min_len < 12 and len(sentence_lengths) >= 3:
                _add("narrow_range", "medium",
                     f"句长范围={max_len - min_len}字",
                     "最长句与最短句差距过小，建议拉开句长差异")

            consecutive_similar = 0
            for i in range(len(sentence_lengths) - 1):
                if abs(sentence_lengths[i] - sentence_lengths[i + 1]) < 5:
                    consecutive_similar += 1
            if consecutive_similar >= 1:
                _add("consecutive_similar_length", "medium",
                     f"{consecutive_similar + 1}句连续长度相近",
                     "有连续句子长度相近，建议交替使用长短句")

        # ─ 2b. 标点密度检测 ─
        period_count = len(re.findall(r'[。.]', para))
        para_len_no_space = len(re.sub(r'\s', '', para))
        if para_len_no_space >= 30 and period_count >= 4:
            period_density = para_len_no_space / period_count if period_count else 999
            if period_density < 10:
                _add("excessive_period", "high",
                     f"平均{period_density:.0f}字/句号（{period_count}个句号/{para_len_no_space}字）",
                     "句号过于密集（几个字就打一个句号），建议把碎句合并为完整的陈述")
            elif period_density < 15:
                _add("excessive_period", "medium",
                     f"平均{period_density:.0f}字/句号",
                     "句号偏密集，建议减少短句碎片化断句")

        dash_count = para.count('——') + para.count('—')
        if dash_count >= 3:
            _add("excessive_dash", "medium",
                 f"{dash_count}处破折号",
                 "破折号使用过多，建议用冒号或直接陈述替代部分破折号")

        # ─ 2c. 段首句过短检测 ─
        if sentences:
            first_sent_len = len(sentences[0].strip())
            if 1 <= first_sent_len <= 8:
                _add("short_first_sentence", "medium",
                     f"段首句仅{first_sent_len}字",
                     "段落首句过短（仅几个字就打句号），建议扩展为完整陈述")

        # ─ 3. 词汇多样性 (TTR) ─
        cjk_tokens = re.findall(r'[\u4e00-\u9fff]+', para)
        chars = list("".join(cjk_tokens))
        if len(chars) >= 20:
            bigrams = [chars[i] + chars[i + 1] for i in range(len(chars) - 1)]
            unique_bigrams = set(bigrams)
            ttr = len(unique_bigrams) / len(bigrams) if bigrams else 1.0
            if ttr < 0.45:
                _add("low_vocabulary_diversity", "high",
                     f"词汇多样性={ttr:.2f}",
                     "词汇重复度过高，建议使用更多样化的表述")
            elif ttr < 0.55:
                _add("low_vocabulary_diversity", "medium",
                     f"词汇多样性={ttr:.2f}",
                     "词汇多样性偏低，建议替换重复用词")

        # ─ 4. 连接词/过渡词密度 ─
        para_char_count = len(re.sub(r'\s', '', para))
        if para_char_count >= 30:
            connector_count = 0
            matched_connectors: list[str] = []
            for conn in _CONNECTORS:
                cnt = para.count(conn)
                if cnt > 0:
                    connector_count += cnt
                    matched_connectors.append(conn)
            density = connector_count / para_char_count
            if density > 0.05:
                _add("high_connector_density", "high",
                     f"密度={density:.3f}({connector_count}个/{para_char_count}字)",
                     f"过渡词过密（{', '.join(matched_connectors[:4])}...），删除部分连接词")
            elif density > 0.03:
                _add("high_connector_density", "medium",
                     f"密度={density:.3f}({connector_count}个/{para_char_count}字)",
                     f"过渡词偏密（{', '.join(matched_connectors[:3])}），减少使用")

            # 段首连接词额外加权：如果段落第一个词就是连接词，升级为high
            para_stripped = para.lstrip()
            for conn in _CONNECTORS:
                if para_stripped.startswith(conn):
                    already_flagged = any(i["type"] == "connector_opener" for i in issues)
                    if not already_flagged:
                        _add("connector_opener", "high",
                             f"段首「{conn}」",
                             f"段落以连接词「{conn}」开头是典型AI写法，删除后直接陈述")
                    break

        # ─ 5. 段首句式重复度（段间比较）─
        fp = opening_fingerprints[idx] if idx < len(opening_fingerprints) else ""
        if fp and fp_counts.get(fp, 0) >= 3:
            _add("repetitive_opening", "medium",
                 f"段首「{fp}...」出现{fp_counts[fp]}次",
                 "多个段落以相同句式开头，建议变换段首结构")

        # ─ 6. 名词短语堆叠（连续"的"）─
        stacking_matches = re.findall(r'[\u4e00-\u9fff]{1,6}的[\u4e00-\u9fff]{1,6}的[\u4e00-\u9fff]{1,6}的[\u4e00-\u9fff]{1,6}', para)
        if len(stacking_matches) >= 2:
            _add("noun_phrase_stacking", "medium",
                 f"{len(stacking_matches)}处多层定语堆叠",
                 "连续「X的Y的Z的W」定语堆叠，建议拆分为短句")
        elif len(stacking_matches) == 1:
            deeper = re.findall(r'[\u4e00-\u9fff]{1,6}的[\u4e00-\u9fff]{1,6}的[\u4e00-\u9fff]{1,6}的[\u4e00-\u9fff]{1,6}的[\u4e00-\u9fff]{1,6}', para)
            if deeper:
                _add("noun_phrase_stacking", "medium",
                     f"4层+定语堆叠",
                     "定语嵌套过深，建议拆分")

        # ─ 7. 标点均匀度 ─
        if len(sentences) >= 4:
            punct_types = set()
            for ch in para:
                if ch in '。！？!?':
                    punct_types.add(ch)
                elif ch in '——':
                    punct_types.add('——')
                elif ch in '……':
                    punct_types.add('……')
                elif ch in '；;':
                    punct_types.add('；')
                elif ch in '：:':
                    punct_types.add('：')
            end_puncts = set(re.findall(r'[。！？!?]', para))
            if len(end_puncts) <= 1 and len(punct_types) <= 2:
                _add("monotone_punctuation", "medium",
                     f"仅用{len(punct_types)}种标点",
                     "标点过于单一，偶尔使用破折号、省略号、分号等增加变化")

        # ── 风险判定（门槛调低）──
        high_count = sum(1 for i in issues if i["severity"] == "high")
        medium_count = sum(1 for i in issues if i["severity"] == "medium")
        total_count = len(issues)

        if high_count >= 1 and medium_count >= 1:
            risk_level = "high"
        elif medium_count >= 3:
            risk_level = "high"
        elif high_count >= 1 or medium_count >= 2 or total_count >= 3:
            risk_level = "medium"
        else:
            risk_level = "low"

        results.append({
            "text": para[:200] + ("..." if len(para) > 200 else ""),
            "full_text": para,
            "index": idx,
            "risk_level": risk_level,
            "issues": issues,
            "suggestions": suggestions,
            "sentence_stats": sentence_stats,
        })

    return results


def detect_uncited_medical_facts(content: str) -> dict[str, Any]:
    """
    启发式检测可能缺少 [共识] 标注的医学事实性句子。
    扫描含医学事实关键词但既无文献引用也无 [共识]/[推断]/[[待补充]] 标注的句子。
    """
    import re

    content = _strip_markdown(content)

    _MEDICAL_FACT_MARKERS = [
        "患者应", "患者需", "建议每天", "建议每周", "建议定期",
        "是一种常见", "是常见的", "的发病率", "的患病率", "的主要原因",
        "可能导致", "可能引起", "有助于", "可以降低", "可以预防",
        "属于", "分为", "包括", "主要有", "通常表现为",
        "正常范围", "正常值", "参考值", "标准是",
        "应避免", "应限制", "不宜", "禁忌",
    ]

    sentences = re.split(r'[。！？\n]', content)
    uncited: list[dict[str, str]] = []

    for s in sentences:
        s = s.strip()
        if len(s) < 15:
            continue
        has_marker = any(m in s for m in _MEDICAL_FACT_MARKERS)
        if not has_marker:
            continue
        has_citation = bool(re.search(
            r"\[文献\d+\]|\[共识\]|\[推断[:：]|\[\[待补充|\[\d+\]",
            s,
        ))
        has_natural_attribution = bool(re.search(
            r"研究(显示|发现|证实|表明)|指南(建议|推荐)|普遍认为|临床公认|医学界",
            s,
        ))
        if not has_citation and not has_natural_attribution:
            preview = s[:80] + ("…" if len(s) > 80 else "")
            uncited.append({
                "sentence": preview,
                "suggestion": "此句含医学事实但未标注来源，建议补充文献引用 [N] 或自然语言归属",
            })

    return {
        "uncited_count": len(uncited),
        "uncited_sentences": uncited[:15],
        "has_issue": len(uncited) > 0,
    }


def extract_provenance_summary(
    content: str,
    available_literature_ids: list[int] | None = None,
) -> dict[str, Any]:
    """
    提取溯源统计：统计 [文献N]、[共识]、[推断:...]、[[待补充:...]] 的数量。
    对应四层 Prompt 架构的输出后处理要求。

    available_literature_ids: Part 2 中实际注入的文献编号列表，用于校验引用完整性。

    返回 { literature, consensus, inference, gaps, total_claims, trust_score,
           referenced_literature_ids, orphan_references, consensus_ratio,
           warnings, gap_details }
    """
    import re

    lit_refs_old = re.findall(r"\[文献\d+\]", content)
    lit_refs_new = re.findall(r"(?<!\[)\[(\d+)\](?!\])", content)
    consensus_refs = re.findall(r"\[共识\]", content)
    inferences = re.findall(r"\[推断[:：][^\]]*\]", content)
    gaps_new = re.findall(r"\[\[待补充[：:][^\]]*\]\]", content)
    gaps_old = re.findall(r"\[DATA:[^\]]*\]", content)

    lit_count = len(lit_refs_old) + len(lit_refs_new)
    cons_count = len(consensus_refs)
    inf_count = len(inferences)
    gap_count = len(gaps_new) + len(gaps_old)
    total = lit_count + cons_count + inf_count + gap_count

    trust_score = 0.0
    if total > 0:
        trust_score = round((lit_count * 1.0 + cons_count * 0.8 + inf_count * 0.5) / total, 2)

    _old_ids = [int(re.search(r"\d+", r).group()) for r in lit_refs_old if re.search(r"\d+", r)]
    _new_ids = [int(n) for n in lit_refs_new]
    unique_lit_ids = sorted(set(_old_ids + _new_ids))

    warnings: list[str] = []

    # 引用完整性校验：检测引用了不存在的文献编号
    orphan_refs: list[int] = []
    if available_literature_ids is not None:
        valid_set = set(available_literature_ids)
        orphan_refs = [lid for lid in unique_lit_ids if lid not in valid_set]
        if orphan_refs:
            warnings.append(f"引用了不存在的文献编号：{orphan_refs}")

    # [共识]滥用检测：比例超过 40% 触发预警
    consensus_ratio = 0.0
    if total > 0:
        consensus_ratio = round(cons_count / total, 2)
        if consensus_ratio > 0.4:
            warnings.append(
                f"[共识]标注比例异常偏高（{cons_count}/{total}={consensus_ratio:.0%}），"
                "可能存在缺乏文献支撑的事实性陈述，建议补充文献或核查"
            )

    # [推断]+[[待补充]]比例预警
    uncertain_count = inf_count + gap_count
    if total > 0 and uncertain_count / total > 0.5:
        warnings.append(
            f"[推断]+[[待补充]]合计占比过高（{uncertain_count}/{total}），"
            "说明文献不足，建议补充更多相关文献"
        )

    return {
        "literature": lit_count,
        "consensus": cons_count,
        "inference": inf_count,
        "gaps": gap_count,
        "total_claims": total,
        "trust_score": trust_score,
        "referenced_literature_ids": unique_lit_ids,
        "orphan_references": orphan_refs,
        "consensus_ratio": consensus_ratio,
        "warnings": warnings,
        "gap_details": [g for g in gaps_new + gaps_old],
    }
