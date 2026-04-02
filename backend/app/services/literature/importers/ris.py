"""RIS 格式解析（EndNote / Zotero / PubMed 导出）"""
from typing import Any


class RISImporter:
    RIS_TAG_MAP = {
        "TI": "title", "T1": "title",
        "AU": "author", "A1": "author",
        "JO": "journal", "JF": "journal", "T2": "journal",
        "PY": "year", "Y1": "year",
        "VL": "volume",
        "IS": "issue",
        "SP": "start_page",
        "EP": "end_page",
        "DO": "doi",
        "UR": "url",
        "AB": "abstract", "N2": "abstract",
        "KW": "keyword",
        "LA": "language",
        "PB": "publisher",
    }

    def parse(self, content: str) -> list[dict[str, Any]]:
        papers = []
        current: dict[str, Any] = {}
        authors: list[str] = []
        keywords: list[str] = []

        for line in content.splitlines():
            line = line.strip()
            if not line:
                continue
            if line.startswith("TY  -"):
                current = {}
                authors = []
                keywords = []
            elif line.startswith("ER  -"):
                if current:
                    current["authors"] = [{"name": a, "affil": ""} for a in authors]
                    current["keywords"] = keywords
                    if "start_page" in current:
                        current["pages"] = str(current.pop("start_page", ""))
                        if "end_page" in current:
                            current["pages"] += "-" + str(current.pop("end_page", ""))
                    papers.append(current)
            else:
                parts = line.split("  -  ", 1)
                if len(parts) != 2:
                    continue
                tag, value = parts[0].strip(), parts[1].strip()
                field = self.RIS_TAG_MAP.get(tag)
                if field == "author":
                    authors.append(value)
                elif field == "keyword":
                    keywords.append(value)
                elif field == "year":
                    try:
                        current["year"] = int(value[:4])
                    except (ValueError, IndexError):
                        pass
                elif field and value:
                    current[field] = value
        return papers
