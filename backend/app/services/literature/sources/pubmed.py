"""PubMed source via NCBI E-utilities."""
from __future__ import annotations

import asyncio
import time
import re
import httpx

_CJK_RE = re.compile(r"[\u4e00-\u9fff\u3400-\u4dbf]")

_MEDICAL_ZH_EN: dict[str, str] = {
    "糖尿病": "diabetes mellitus",
    "高血压": "hypertension",
    "冠心病": "coronary heart disease",
    "心力衰竭": "heart failure",
    "心衰": "heart failure",
    "脑卒中": "stroke",
    "中风": "stroke",
    "肺癌": "lung cancer",
    "乳腺癌": "breast cancer",
    "肝癌": "liver cancer",
    "胃癌": "gastric cancer",
    "结直肠癌": "colorectal cancer",
    "前列腺癌": "prostate cancer",
    "白血病": "leukemia",
    "淋巴瘤": "lymphoma",
    "哮喘": "asthma",
    "慢阻肺": "chronic obstructive pulmonary disease",
    "慢性阻塞性肺疾病": "chronic obstructive pulmonary disease",
    "肾病": "kidney disease",
    "肾衰竭": "renal failure",
    "肝硬化": "liver cirrhosis",
    "脂肪肝": "fatty liver disease",
    "动脉粥样硬化": "atherosclerosis",
    "血脂异常": "dyslipidemia",
    "高脂血症": "hyperlipidemia",
    "骨质疏松": "osteoporosis",
    "类风湿关节炎": "rheumatoid arthritis",
    "痛风": "gout",
    "帕金森病": "Parkinson disease",
    "阿尔茨海默病": "Alzheimer disease",
    "老年痴呆": "Alzheimer disease",
    "癫痫": "epilepsy",
    "抑郁症": "depression",
    "焦虑症": "anxiety disorder",
    "精神分裂症": "schizophrenia",
    "甲状腺": "thyroid",
    "甲亢": "hyperthyroidism",
    "甲减": "hypothyroidism",
    "贫血": "anemia",
    "败血症": "sepsis",
    "肺炎": "pneumonia",
    "结核": "tuberculosis",
    "艾滋病": "HIV AIDS",
    "乙肝": "hepatitis B",
    "丙肝": "hepatitis C",
    "新冠": "COVID-19",
    "流感": "influenza",
    "肿瘤": "neoplasm",
    "癌症": "cancer",
    "免疫治疗": "immunotherapy",
    "化疗": "chemotherapy",
    "放疗": "radiotherapy",
    "靶向治疗": "targeted therapy",
    "基因治疗": "gene therapy",
    "干细胞": "stem cell",
    "人工智能": "artificial intelligence",
    "深度学习": "deep learning",
    "机器学习": "machine learning",
    "临床试验": "clinical trial",
    "随机对照试验": "randomized controlled trial",
    "Meta分析": "meta-analysis",
    "荟萃分析": "meta-analysis",
    "系统综述": "systematic review",
    "横断面研究": "cross-sectional study",
    "队列研究": "cohort study",
    "病例对照研究": "case-control study",
    "护理": "nursing care",
    "康复": "rehabilitation",
    "预后": "prognosis",
    "诊断": "diagnosis",
    "治疗": "treatment",
    "预防": "prevention",
    "筛查": "screening",
    "药物不良反应": "adverse drug reaction",
    "耐药": "drug resistance",
    "抗生素": "antibiotic",
    "胰岛素": "insulin",
    "血糖": "blood glucose",
    "血压": "blood pressure",
    "心电图": "electrocardiogram",
    "超声": "ultrasound",
    "核磁共振": "magnetic resonance imaging",
    "CT": "computed tomography",
}


async def _translate_query_to_english(query: str) -> str:
    """Translate a Chinese query to English for PubMed.

    Uses a built-in medical term dictionary first. Falls back to LLM
    translation for terms not found in the dictionary.
    """
    q = query.strip()
    if not _CJK_RE.search(q):
        return q

    if q in _MEDICAL_ZH_EN:
        return _MEDICAL_ZH_EN[q]

    for zh, en in sorted(_MEDICAL_ZH_EN.items(), key=lambda x: -len(x[0])):
        if zh in q:
            q = q.replace(zh, en)
    if not _CJK_RE.search(q):
        return q

    try:
        from app.services.llm.openai_client import chat_completion
        from app.services.llm.manager import resolve_model

        model = await resolve_model()
        messages = [
            {
                "role": "system",
                "content": (
                    "You are a medical literature search assistant. "
                    "Translate the following Chinese medical search query into "
                    "English PubMed search terms. Output ONLY the English "
                    "search terms, nothing else. Use standard MeSH terminology "
                    "when possible."
                ),
            },
            {"role": "user", "content": query},
        ]
        translated = await chat_completion(messages, model=model)
        translated = (translated or "").strip().strip('"').strip("'")
        if translated:
            return translated
    except Exception:
        pass

    return query


class PubMedSource:
    BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
    ESEARCH = BASE_URL + "/esearch.fcgi"
    ESUMMARY = BASE_URL + "/esummary.fcgi"
    EFETCH = BASE_URL + "/efetch.fcgi"

    COMMON_PARAMS = {
        "tool": "LinScioMedComm",
        "email": "support@linscio.com",
        "retmode": "json",
    }

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key
        self._rate = 10 if api_key else 3
        self._lock = asyncio.Lock()
        self._last_ts = 0.0

    async def _throttle(self):
        min_interval = 1.0 / float(self._rate)
        async with self._lock:
            now = time.monotonic()
            wait = (self._last_ts + min_interval) - now
            if wait > 0:
                await asyncio.sleep(wait)
            self._last_ts = time.monotonic()

    async def search(
        self,
        query: str,
        year_from: int | None = None,
        year_to: int | None = None,
        pub_types: list[str] | None = None,
        max_results: int = 20,
        language: str = "all",
        progress_cb=None,
    ) -> list[dict]:
        if progress_cb:
            await progress_cb("准备检索 PMID", 12)

        effective_query = query
        if _CJK_RE.search(query):
            if progress_cb:
                await progress_cb("翻译中文关键词", 18)
            effective_query = await _translate_query_to_english(query)
            print(
                f"[PubMed] Chinese query detected: '{query}' -> '{effective_query}'",
                flush=True,
            )

        q = self._build_query(effective_query, year_from, year_to, pub_types, language)
        params = {
            **self.COMMON_PARAMS,
            "db": "pubmed",
            "term": q,
            "retmax": max_results,
            "sort": "relevance",
            "usehistory": "n",
        }
        if self.api_key:
            params["api_key"] = self.api_key

        async with httpx.AsyncClient(timeout=8.0) as client:
            last_err: Exception | None = None
            for attempt in range(2):
                try:
                    await self._throttle()
                    if progress_cb:
                        await progress_cb("检索 PMID 列表", 35)
                    resp = await client.get(self.ESEARCH, params=params)
                    resp.raise_for_status()
                    data = resp.json()
                    es = data.get("esearchresult", {})
                    pmids = es.get("idlist", [])
                    if not pmids:
                        return []
                    qt = (es.get("querytranslation") or "").strip()
                    if not qt:
                        print(
                            f"[PubMed] empty querytranslation — query was not understood, returning 0 results",
                            flush=True,
                        )
                        return []
                    if progress_cb:
                        await progress_cb("获取元数据", 70)
                    return await self._fetch_summaries(client, pmids)
                except Exception as e:
                    last_err = e
                    # 轻量退避：NCBI 在限流时更容易返回异常结构
                    await asyncio.sleep(min(4.0, (attempt + 1) * 1.5))
                    continue
            if last_err:
                raise last_err
            return []

    def _build_query(
        self,
        query: str,
        year_from: int | None,
        year_to: int | None,
        pub_types: list[str] | None,
        language: str,
    ) -> str:
        parts = [query]
        if year_from or year_to:
            y_from = year_from or 1900
            y_to = year_to or 2099
            parts.append(f"{y_from}:{y_to}[dp]")
        if pub_types:
            type_map = {
                "review": "Review[pt]",
                "rct": "Randomized Controlled Trial[pt]",
                "meta": "Meta-Analysis[pt]",
                "guideline": "Guideline[pt]",
                "clinical_trial": "Clinical Trial[pt]",
                "systematic": "Systematic Review[pt]",
            }
            filters = [type_map[t] for t in pub_types if t in type_map]
            if filters:
                parts.append("(" + " OR ".join(filters) + ")")
        if language == "en":
            parts.append("english[la]")
        elif language == "zh":
            parts.append("chinese[la]")
        return " AND ".join(parts)

    async def _fetch_summaries(self, client: httpx.AsyncClient, pmids: list[str]) -> list[dict]:
        params = {
            **self.COMMON_PARAMS,
            "db": "pubmed",
            "id": ",".join(pmids),
        }
        if self.api_key:
            params["api_key"] = self.api_key
        last_err: Exception | None = None
        for attempt in range(2):
            try:
                await self._throttle()
                resp = await client.get(self.ESUMMARY, params=params)
                resp.raise_for_status()
                js = resp.json()
                result = js.get("result", {})
                # NCBI 在限流/出错时可能返回非预期结构（例如 result 为字符串）
                if not isinstance(result, dict):
                    raise RuntimeError(f"NCBI esummary unexpected result type: {type(result).__name__}")
                papers = []
                for pmid in pmids:
                    entry = result.get(pmid)
                    if not isinstance(entry, dict) or "error" in entry:
                        continue
                    papers.append(self._parse_summary(entry))
                return papers
            except Exception as e:
                last_err = e
                await asyncio.sleep(min(4.0, (attempt + 1) * 1.5))
                continue
        if last_err:
            raise last_err
        return []

    async def fetch_abstract(self, pmid: str) -> str:
        """
        按需拉取单篇摘要（EFetch，MEDLINE text）
        不在批量检索中调用，避免超速率限制
        """
        pid = str(pmid or "").strip()
        if not pid:
            return ""
        async with httpx.AsyncClient(timeout=10.0) as client:
            params = {
                "tool": self.COMMON_PARAMS["tool"],
                "email": self.COMMON_PARAMS["email"],
                "db": "pubmed",
                "id": pid,
                "rettype": "medline",
                "retmode": "text",
            }
            if self.api_key:
                params["api_key"] = self.api_key
            await self._throttle()
            resp = await client.get(self.EFETCH, params=params)
            resp.raise_for_status()
            text = resp.text or ""
        # MEDLINE: AB  - 开始，直到下一个字段（如 CI  - / FAU - / JT  -）
        m = re.search(r"(?:\n|^)AB\\s{2}-\\s*(.*?)(?:\\n[A-Z]{2,4}\\s{2}-|\\Z)", text, flags=re.S)
        if not m:
            return ""
        raw = m.group(1)
        # 摘要常跨多行：以空格拼接并压缩空白
        return " ".join(raw.split())

    def _parse_summary(self, entry: dict) -> dict:
        if not isinstance(entry, dict):
            return {
                "source": "pubmed",
                "source_id": "",
                "title": "",
                "authors": [],
                "journal": "",
                "year": None,
                "volume": "",
                "issue": "",
                "pages": "",
                "pmid": "",
                "doi": None,
                "pub_types": [],
                "abstract": "",
            }
        raw_authors = entry.get("authors", [])
        authors = []
        if isinstance(raw_authors, list):
            for a in raw_authors:
                if isinstance(a, dict):
                    authors.append({"name": a.get("name", ""), "affil": ""})
                elif isinstance(a, str):
                    authors.append({"name": a, "affil": ""})
        pub_date = entry.get("pubdate", "")
        year = int(pub_date[:4]) if pub_date[:4].isdigit() else None
        doi = None
        raw_articleids = entry.get("articleids", [])
        if isinstance(raw_articleids, list):
            for it in raw_articleids:
                if isinstance(it, dict) and it.get("idtype") == "doi":
                    v = it.get("value")
                    if isinstance(v, str) and v.strip():
                        doi = v.lower()
                        break
        raw_pubtypes = entry.get("pubtype", [])
        pub_types: list[str] = []
        if isinstance(raw_pubtypes, list):
            for t in raw_pubtypes:
                if isinstance(t, dict):
                    pub_types.append(str(t.get("value", "")))
                elif isinstance(t, str):
                    pub_types.append(t)
        return {
            "source": "pubmed",
            "source_id": entry.get("uid", ""),
            "title": (entry.get("title") or "").rstrip("."),
            "authors": authors,
            "journal": entry.get("fulljournalname") or entry.get("source", ""),
            "year": year,
            "volume": entry.get("volume", ""),
            "issue": entry.get("issue", ""),
            "pages": entry.get("pages", ""),
            "pmid": entry.get("uid", ""),
            "doi": doi,
            "pub_types": pub_types,
            "abstract": "",
        }
