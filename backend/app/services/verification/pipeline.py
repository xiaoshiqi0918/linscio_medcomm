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
    """检测 [DATA:] 占位符"""
    import re
    matches = list(re.finditer(r"\[DATA:[^\]]*\]", content))
    return content, [{"text": m.group(), "message": "需补充权威数据"} for m in matches]


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

    rag_str = _format_rag_context(rag_context)
    prompt = CLAIM_VERIFY_PROMPT.format(content=content[:4000], rag_context=rag_str)
    try:
        resp = await chat_completion(
            messages=[{"role": "user", "content": prompt}],
            stream=False,
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

    prompt = FACT_VERIFY_PROMPT.format(
        content=content[:4000],
        verified_data_list=verified_data_list or "（无，本次未传入已核实数据）",
    )
    try:
        resp = await chat_completion(
            messages=[{"role": "user", "content": prompt}],
            stream=False,
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
        msg += f"存在 {len(data_warnings)} 处 [DATA:] 占位符需补充；"
    if absolute_terms:
        msg += f"存在 {len(absolute_terms)} 处绝对化表述建议修改。"
    return {
        "can_export": not has_warnings,
        "data_warnings": data_warnings,
        "absolute_terms": absolute_terms,
        "message": msg.strip() or None,
    }
