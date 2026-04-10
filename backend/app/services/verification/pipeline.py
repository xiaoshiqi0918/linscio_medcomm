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
    from app.services.llm.openai_client import chat_completion
    from app.services.llm.manager import TaskTier

    rag_str = _format_rag_context(rag_context)
    prompt = CLAIM_VERIFY_PROMPT.format(content=content[:4000], rag_context=rag_str)
    try:
        resp = await chat_completion(
            messages=[{"role": "user", "content": prompt}],
            stream=False,
            task=TaskTier.BALANCED,
        )
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
    from app.services.llm.openai_client import chat_completion
    from app.services.llm.manager import TaskTier

    prompt = FACT_VERIFY_PROMPT.format(
        content=content[:4000],
        verified_data_list=verified_data_list or "（无，本次未传入已核实数据）",
    )
    try:
        resp = await chat_completion(
            messages=[{"role": "user", "content": prompt}],
            stream=False,
            task=TaskTier.BALANCED,
        )
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
    from app.services.llm.openai_client import chat_completion
    from app.services.llm.manager import TaskTier

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
        resp = await chat_completion(
            messages=[{"role": "user", "content": prompt}],
            stream=False,
            task=TaskTier.BALANCED,
        )
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

    total_issues = sum(len(v) for v in results.values())

    score = 100
    penalty_weights = {
        "share_call": 12,
        "list_cliche": 8,
        "mechanical_transition": 6,
        "excessive_modifier": 4,
        "ai_ending": 10,
        "ai_connector": 3,
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

    return {
        "score": score,
        "total_issues": total_issues,
        "details": {k: v for k, v in results.items() if v},
        "warnings": warnings,
        "needs_polish": score < 60,
    }


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
            r"\[文献\d+\]|\[共识\]|\[推断[:：]|\[\[待补充",
            s,
        ))
        if not has_citation:
            preview = s[:80] + ("…" if len(s) > 80 else "")
            uncited.append({
                "sentence": preview,
                "suggestion": "此句含医学事实但未标注来源，建议补充 [共识] 或对应文献引用",
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

    lit_refs = re.findall(r"\[文献\d+\]", content)
    consensus_refs = re.findall(r"\[共识\]", content)
    inferences = re.findall(r"\[推断[:：][^\]]*\]", content)
    gaps_new = re.findall(r"\[\[待补充[：:][^\]]*\]\]", content)
    gaps_old = re.findall(r"\[DATA:[^\]]*\]", content)

    lit_count = len(lit_refs)
    cons_count = len(consensus_refs)
    inf_count = len(inferences)
    gap_count = len(gaps_new) + len(gaps_old)
    total = lit_count + cons_count + inf_count + gap_count

    trust_score = 0.0
    if total > 0:
        trust_score = round((lit_count * 1.0 + cons_count * 0.8 + inf_count * 0.5) / total, 2)

    unique_lit_ids = sorted(set(
        int(re.search(r"\d+", r).group()) for r in lit_refs if re.search(r"\d+", r)
    ))

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
