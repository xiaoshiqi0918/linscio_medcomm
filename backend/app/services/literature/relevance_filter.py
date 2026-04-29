"""文献 AI 智能筛选：Embedding 粗筛 + LLM 精排两阶段流水线。"""

from __future__ import annotations

import json
import logging
import math
import os
from dataclasses import dataclass, field

logger = logging.getLogger("uvicorn.error")

FILTER_SYSTEM_PROMPT = """\
你是一位医学文献筛选专家。你的任务是根据给定的研究主题，评估每篇文献的相关性和引用价值。

评分维度（综合为 1-10 的单一总分）：
1. 主题相关度：文献内容与研究主题的直接相关程度
2. 研究设计质量：优先 Meta分析/系统综述 > RCT > 队列研究 > 病例报告 > 叙述性综述
3. 引用价值：该文献对撰写该主题学术文章的实际参考价值

输出要求：
- 严格输出 JSON 数组，不要有任何其他文字
- 每个元素包含三个字段：index (文献编号，从0开始), score (1-10的浮点数), reason (一句话中文理由)
- 按 index 顺序输出"""


def _build_filter_prompt(topic: str, papers: list[dict]) -> str:
    lines = [f"研究主题：{topic}\n\n待评估文献：\n"]
    for i, p in enumerate(papers):
        title = p.get("title", "").strip()
        abstract = (p.get("abstract") or "").strip()
        year = p.get("year") or ""
        journal = p.get("journal") or ""
        pub_types = ", ".join(p.get("pub_types") or [])
        cite_count = p.get("cite_count", 0)

        entry = f"[{i}] {title}"
        if year:
            entry += f" ({year})"
        if journal:
            entry += f" - {journal}"
        if pub_types:
            entry += f" [{pub_types}]"
        if cite_count:
            entry += f" (被引{cite_count}次)"
        if abstract:
            entry += f"\n    摘要：{abstract[:500]}"
        else:
            entry += "\n    摘要：（无摘要）"
        lines.append(entry)
    return "\n".join(lines)


@dataclass
class FilteredPaper:
    item: dict
    relevance_score: float = 0.0
    reason: str = ""


@dataclass
class FilterResult:
    kept: list[FilteredPaper] = field(default_factory=list)
    removed_count: int = 0
    total_count: int = 0
    method: str = ""  # "hybrid" | "llm_only" | "embedding_only"


# ---------------------------------------------------------------------------
# Embedding helpers (reused patterns from rag_retriever.py)
# ---------------------------------------------------------------------------

def _cosine_sim(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na < 1e-12 or nb < 1e-12:
        return 0.0
    return dot / (na * nb)


def _embed_available() -> bool:
    """Check whether any embedding backend is reachable."""
    from app.core.config import is_saas
    if is_saas():
        return bool(os.environ.get("OPENAI_API_KEY"))
    try:
        import httpx
        r = httpx.get("http://127.0.0.1:11434/api/tags", timeout=2.0)
        return r.status_code == 200
    except Exception:
        return False


async def _embed_texts(texts: list[str]) -> list[list[float]] | None:
    """Batch-embed a list of texts via SaaS OpenAI or local Ollama.

    Returns list of embedding vectors (same order as input), or None on failure.
    """
    from app.core.config import is_saas
    if not texts:
        return None

    if is_saas():
        return await _embed_texts_saas(texts)
    return await _embed_texts_ollama(texts)


async def _embed_texts_saas(texts: list[str]) -> list[list[float]] | None:
    openai_key = os.environ.get("OPENAI_API_KEY")
    if not openai_key:
        return None
    base = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")
    model = "text-embedding-3-small"
    try:
        import httpx
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                f"{base.rstrip('/')}/embeddings",
                headers={"Authorization": f"Bearer {openai_key}", "Content-Type": "application/json"},
                json={"model": model, "input": [t[:8000] for t in texts]},
            )
            if resp.status_code != 200:
                logger.warning("SaaS embedding failed: status=%d", resp.status_code)
                return None
            data = resp.json().get("data")
            if not data:
                return None
            emb_map: dict[int, list[float]] = {}
            for item in data:
                emb_map[item["index"]] = item["embedding"]
            return [emb_map[i] for i in range(len(texts))]
    except Exception as exc:
        logger.warning("SaaS embedding error: %s", exc)
        return None


async def _embed_texts_ollama(texts: list[str]) -> list[list[float]] | None:
    model = os.environ.get("OLLAMA_EMBED_MODEL", "nomic-embed-text")
    try:
        import httpx
        results: list[list[float]] = []
        async with httpx.AsyncClient(timeout=120.0) as client:
            for t in texts:
                resp = await client.post(
                    "http://127.0.0.1:11434/api/embeddings",
                    json={"model": model, "prompt": t[:4000]},
                )
                if resp.status_code != 200:
                    return None
                emb = resp.json().get("embedding")
                if not isinstance(emb, list) or not emb:
                    return None
                results.append(emb)
        return results
    except Exception as exc:
        logger.warning("Ollama embedding error: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Stage 1: Embedding rough filter
# ---------------------------------------------------------------------------

async def _embedding_rough_filter(
    topic: str,
    papers: list[dict],
    top_k: int,
) -> list[tuple[dict, float]]:
    """Return papers sorted by embedding similarity to topic, with scores."""
    texts = [topic] + [
        f"{p.get('title', '')}. {(p.get('abstract') or '')[:500]}"
        for p in papers
    ]
    embeddings = await _embed_texts(texts)
    if embeddings is None:
        raise RuntimeError("Embedding unavailable")

    topic_emb = embeddings[0]
    scored: list[tuple[dict, float]] = []
    for i, paper in enumerate(papers):
        sim = _cosine_sim(topic_emb, embeddings[i + 1])
        scored.append((paper, sim))
    scored.sort(key=lambda x: -x[1])
    return scored[:top_k]


# ---------------------------------------------------------------------------
# Stage 2: LLM fine-ranking
# ---------------------------------------------------------------------------

def _parse_llm_scores(raw: str, count: int) -> list[dict]:
    """Extract JSON array from LLM response, tolerating markdown fences."""
    text = raw.strip()
    if text.startswith("```"):
        first_nl = text.index("\n") if "\n" in text else 3
        text = text[first_nl:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()

    try:
        arr = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("[")
        end = text.rfind("]")
        if start >= 0 and end > start:
            try:
                arr = json.loads(text[start:end + 1])
            except json.JSONDecodeError:
                return []
        else:
            return []

    if not isinstance(arr, list):
        return []
    result = []
    for item in arr:
        if not isinstance(item, dict):
            continue
        idx = item.get("index", item.get("idx", item.get("i", -1)))
        score = item.get("score", item.get("relevance_score", 0))
        reason = item.get("reason", item.get("reasoning", ""))
        try:
            idx = int(idx)
            score = float(score)
        except (TypeError, ValueError):
            continue
        if 0 <= idx < count:
            result.append({"index": idx, "score": score, "reason": reason})
    return result


async def _llm_score_batch(
    topic: str,
    papers: list[dict],
    *,
    user_id: int = 0,
    user: object | None = None,
) -> list[dict]:
    """Score a batch of papers using LLM. Returns list of {index, score, reason}.

    In SaaS mode uses call_llm_with_fallback for three-tier degradation;
    in desktop mode uses chat_completion directly.
    """
    prompt = _build_filter_prompt(topic, papers)
    messages = [
        {"role": "system", "content": FILTER_SYSTEM_PROMPT},
        {"role": "user", "content": prompt},
    ]
    try:
        from app.core.config import is_saas
        if is_saas():
            from app.services.llm.openai_client import call_llm_with_fallback
            result = await call_llm_with_fallback(
                "literature_filter",
                messages,
                user_id=user_id,
                temperature=0.1,
                user=user,
            )
        else:
            from app.services.llm.openai_client import chat_completion
            result = await chat_completion(
                messages,
                temperature=0.1,
                _log_user_id=user_id,
                _log_task_type="literature_filter",
            )
        return _parse_llm_scores(result, len(papers))
    except Exception as exc:
        logger.error("LLM scoring failed: %s", exc)
        return []


async def _llm_fine_rank(
    topic: str,
    papers: list[dict],
    *,
    batch_size: int = 10,
    user_id: int = 0,
    user: object | None = None,
) -> list[tuple[dict, float, str]]:
    """Score all papers with LLM, processing in batches.

    Returns list of (paper, score, reason) sorted by score descending.
    """
    all_scored: list[tuple[dict, float, str]] = []

    for start in range(0, len(papers), batch_size):
        batch = papers[start:start + batch_size]
        scores = await _llm_score_batch(topic, batch, user_id=user_id, user=user)
        score_map = {s["index"]: s for s in scores}

        for local_idx, paper in enumerate(batch):
            info = score_map.get(local_idx, {})
            score = info.get("score", 0.0)
            reason = info.get("reason", "")
            all_scored.append((paper, score, reason))

    all_scored.sort(key=lambda x: -x[1])
    return all_scored


# ---------------------------------------------------------------------------
# Main entry: two-stage filter pipeline
# ---------------------------------------------------------------------------

async def filter_papers(
    topic: str,
    papers: list[dict],
    *,
    top_k: int = 15,
    min_score: float = 5.0,
    user_id: int = 0,
    user: object | None = None,
    embedding_pre_k: int = 30,
) -> FilterResult:
    """Run the two-stage (embedding + LLM) relevance filter pipeline.

    Falls back to LLM-only when embedding is unavailable.
    Works in both SaaS and desktop modes.
    """
    total = len(papers)
    if total == 0:
        return FilterResult(kept=[], removed_count=0, total_count=0, method="none")

    use_embedding = _embed_available() and total > top_k

    if use_embedding:
        try:
            pre_k = max(embedding_pre_k, top_k)
            rough = await _embedding_rough_filter(topic, papers, pre_k)
            candidates = [p for p, _ in rough]
            method = "hybrid"
        except Exception as exc:
            logger.warning("Embedding stage failed, falling back to LLM-only: %s", exc)
            candidates = papers
            method = "llm_only"
    else:
        candidates = papers
        method = "llm_only" if total > top_k else "llm_only"

    scored = await _llm_fine_rank(topic, candidates, user_id=user_id, user=user)

    kept: list[FilteredPaper] = []
    for paper, score, reason in scored:
        if score >= min_score and len(kept) < top_k:
            kept.append(FilteredPaper(item=paper, relevance_score=score, reason=reason))

    if not kept and scored:
        best_paper, best_score, best_reason = scored[0]
        kept.append(FilteredPaper(item=best_paper, relevance_score=best_score, reason=best_reason))

    return FilterResult(
        kept=kept,
        removed_count=total - len(kept),
        total_count=total,
        method=method,
    )
