"""引用格式导出：APA / BibTeX / NLM / GB/T 7714 / 科普（popular）"""
import json
from typing import Any


class CitationFormatter:
    """文献引用格式化器，支持学术与科普两大类格式。

    科普格式优先级（推荐）：
      1. popular   — 类学术型，兼顾可读性与严谨性（默认科普格式）
      2. numbered  — 编号制，等同 popular 但由调用方加 [n] 前缀
      3. hyperlink — 超链接型，DOI/URL 可点击验证
    """

    def __init__(self, paper: Any):
        self.p = paper
        raw = paper.authors if hasattr(paper, "authors") else "[]"
        self.authors = json.loads(raw) if isinstance(raw, str) else (raw or [])

    def format(self, fmt: str) -> str:
        fn = getattr(self, f"_fmt_{fmt}", None)
        if fn:
            return fn()
        return self._fmt_apa()

    # ------------------------------------------------------------------
    # 科普格式：类学术型（推荐主格式）
    # 结构：作者. 标题. 期刊/出版社, 年份, 卷(期): 页码
    # 元数据不完整时自动降级，始终保证可读
    # ------------------------------------------------------------------
    def _fmt_popular(self) -> str:
        author_str = self._popular_authors()
        title = (self.p.title or "").rstrip(".")
        journal = self.p.journal or ""
        year = str(self.p.year) if self.p.year else ""
        vol_issue_pages = self._vol_issue_pages()
        doi_url = self._doi_or_url()

        if journal and vol_issue_pages:
            source = f"{journal}, {year}, {vol_issue_pages}" if year else f"{journal}, {vol_issue_pages}"
        elif journal and year:
            source = f"{journal}, {year}"
        elif journal:
            source = journal
        elif year:
            source = year
        else:
            source = ""

        segments = [s for s in [author_str, title, source] if s]
        line = ". ".join(segments)
        if doi_url:
            line += f". {doi_url}"
        if line and not line.endswith("."):
            line += "."
        return line

    def _popular_authors(self) -> str:
        if not self.authors:
            return ""
        names = [a.get("name", "") for a in self.authors[:3] if a.get("name")]
        if not names:
            return ""
        result = ", ".join(names)
        if len(self.authors) > 3:
            result += " 等" if self._is_chinese_name(names[0]) else " et al."
        return result

    @staticmethod
    def _is_chinese_name(name: str) -> bool:
        return any("\u4e00" <= ch <= "\u9fff" for ch in name)

    def _vol_issue_pages(self) -> str:
        vol = getattr(self.p, "volume", "") or ""
        issue = getattr(self.p, "issue", "") or ""
        pages = getattr(self.p, "pages", "") or ""
        if vol and issue and pages:
            return f"{vol}({issue}): {pages}"
        if vol and pages:
            return f"{vol}: {pages}"
        if vol and issue:
            return f"{vol}({issue})"
        if vol:
            return vol
        return ""

    def _doi_or_url(self) -> str:
        doi = getattr(self.p, "doi", "") or ""
        url = getattr(self.p, "url", "") or ""
        if doi:
            return f"https://doi.org/{doi}"
        if url:
            return url
        return ""

    # ------------------------------------------------------------------
    # 科普格式：超链接型（互联网科普/公众号）
    # 只保留最核心信息 + 可验证链接
    # ------------------------------------------------------------------
    def _fmt_hyperlink(self) -> str:
        title = (self.p.title or "").rstrip(".")
        year = f"({self.p.year})" if self.p.year else ""
        source = self.p.journal or ""
        link = self._doi_or_url()

        desc_parts = [s for s in [source, year] if s]
        desc = " ".join(desc_parts)
        if desc:
            line = f"{title}. {desc}"
        else:
            line = title
        if link:
            line += f" {link}"
        return line

    # ------------------------------------------------------------------
    # 外部引用格式化（无 volume/issue/pages，降级处理）
    # ------------------------------------------------------------------
    @staticmethod
    def format_external_ref(ref: Any) -> str:
        """格式化 ArticleExternalReference，自动选择最佳呈现"""
        authors = ""
        try:
            raw = ref.authors if isinstance(ref.authors, str) else "[]"
            arr = json.loads(raw) if isinstance(raw, str) else (ref.authors or [])
            names = [a.get("name", "") for a in (arr or []) if isinstance(a, dict) and a.get("name")]
            if names:
                authors = ", ".join(names[:3])
                if len(names) > 3:
                    is_cn = any("\u4e00" <= ch <= "\u9fff" for ch in names[0])
                    authors += " 等" if is_cn else " et al."
        except Exception:
            pass

        title = (getattr(ref, "title", "") or "").rstrip(".")
        journal = getattr(ref, "journal", "") or ""
        year = str(ref.year) if getattr(ref, "year", None) else ""
        doi = (getattr(ref, "doi", "") or "").strip()
        url = getattr(ref, "url", "") or ""

        source_parts = [s for s in [journal, year] if s]
        source = ", ".join(source_parts)

        segments = [s for s in [authors, title, source] if s]
        line = ". ".join(segments)

        if doi:
            line += f". https://doi.org/{doi}"
        elif url:
            line += f". {url}"
        if line and not line.endswith("."):
            line += "."
        return line

    # ------------------------------------------------------------------
    # 学术格式（保留原有）
    # ------------------------------------------------------------------
    def _fmt_apa(self) -> str:
        author_str = self._apa_authors()
        year = f"({self.p.year})" if self.p.year else "(n.d.)"
        title = (self.p.title or "").rstrip(".")
        journal = f"*{self.p.journal}*" if self.p.journal else ""
        vol_issue = ""
        if self.p.volume:
            vol_issue = f"*{self.p.volume}*"
            if self.p.issue:
                vol_issue += f"({self.p.issue})"
        pages = self.p.pages or ""
        doi = f"https://doi.org/{self.p.doi}" if self.p.doi else (self.p.url or "")
        parts = filter(None, [author_str, year, title, journal, vol_issue, pages, doi])
        return ". ".join(str(p) for p in parts) + "."

    def _apa_authors(self) -> str:
        if not self.authors:
            return "Anonymous"
        parts = []
        for a in self.authors[:6]:
            name = a.get("name", "")
            names = name.split()
            if len(names) >= 2:
                initials = ". ".join(n[0] for n in names[1:]) + "."
                parts.append(f"{names[0]}, {initials}")
            else:
                parts.append(name)
        if len(self.authors) > 6:
            parts.append("...")
            last = self.authors[-1].get("name", "")
            parts.append(last)
        if len(parts) == 1:
            return parts[0]
        return ", ".join(parts[:-1]) + ", & " + parts[-1]

    def _fmt_bibtex(self) -> str:
        first_author = "Unknown"
        if self.authors:
            last_part = self.authors[0].get("name", "").split()[-1]
            first_author = last_part if last_part else "Unknown"
        key = f"{first_author}{self.p.year or ''}"
        author_str = " and ".join(
            self._bibtex_author(a.get("name", "")) for a in self.authors
        ) or "Unknown"
        fields = {
            "author": author_str,
            "title": self.p.title or "",
            "journal": self.p.journal or "",
            "year": str(self.p.year) if self.p.year else "",
            "volume": self.p.volume or "",
            "number": self.p.issue or "",
            "pages": self.p.pages or "",
            "doi": self.p.doi or "",
        }
        field_strs = "\n  ".join(f"{k} = {{{v}}}" for k, v in fields.items() if v)
        return f"@article{{{key},\n  {field_strs}\n}}"

    def _bibtex_author(self, name: str) -> str:
        parts = [p.strip() for p in name.split(",")]
        if len(parts) >= 2:
            return f"{parts[0]}, {' '.join(parts[1:])}"
        return name

    def _fmt_nlm(self) -> str:
        """NLM (Vancouver)"""
        authors_str = "; ".join(a.get("name", "") for a in self.authors[:6]) or "Unknown"
        if len(self.authors) > 6:
            authors_str += " et al."
        title = (self.p.title or "").rstrip(".")
        journal = self.p.journal or ""
        year = self.p.year or ""
        vol = self.p.volume or ""
        issue = f"({self.p.issue})" if self.p.issue else ""
        pages = self.p.pages or ""
        return f"{authors_str}. {title}. {journal}. {year};{vol}{issue}:{pages}."

    def _fmt_gbt7714(self) -> str:
        """GB/T 7714 中文标准"""
        authors_str = ", ".join(a.get("name", "") for a in self.authors[:3]) or "佚名"
        if len(self.authors) > 3:
            authors_str += ", 等"
        title = (self.p.title or "").rstrip(".")
        journal = self.p.journal or ""
        year = self.p.year or ""
        vol = self.p.volume or ""
        issue = self.p.issue or ""
        pages = self.p.pages or ""
        parts = [authors_str, title, f"{journal}, {year}, {vol}({issue}): {pages}"]
        return ".".join(str(p) for p in parts if p) + "."
