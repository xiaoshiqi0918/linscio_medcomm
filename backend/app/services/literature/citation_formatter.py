"""引用格式导出：APA / BibTeX / NLM / GB/T 7714"""
import json
from typing import Any


class CitationFormatter:
    def __init__(self, paper: Any):
        self.p = paper
        raw = paper.authors if hasattr(paper, "authors") else "[]"
        self.authors = json.loads(raw) if isinstance(raw, str) else (raw or [])

    def format(self, fmt: str) -> str:
        fn = getattr(self, f"_fmt_{fmt}", None)
        if fn:
            return fn()
        return self._fmt_apa()

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
