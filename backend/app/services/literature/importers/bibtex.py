"""BibTeX 格式解析"""
from typing import Any


class BibTeXImporter:
    FIELD_MAP = {
        "title": "title",
        "author": "author",
        "journal": "journal",
        "year": "year",
        "volume": "volume",
        "number": "issue",
        "pages": "pages",
        "doi": "doi",
        "url": "url",
        "abstract": "abstract",
        "keywords": "keywords",
        "publisher": "publisher",
        "booktitle": "journal",
    }

    def parse(self, content: str) -> list[dict[str, Any]]:
        try:
            import bibtexparser
            from bibtexparser.bparser import BibTexParser
        except ImportError:
            return []
        parser = BibTexParser(common_strings=True)
        bib = bibtexparser.loads(content, parser=parser)
        results = []
        for entry in bib.entries:
            paper: dict[str, Any] = {}
            for bib_field, our_field in self.FIELD_MAP.items():
                val = (entry.get(bib_field, "") or "").strip("{}").strip()
                if not val:
                    continue
                if bib_field == "author":
                    paper["authors"] = self._parse_authors(val)
                elif bib_field == "year":
                    try:
                        paper["year"] = int(val)
                    except ValueError:
                        pass
                elif bib_field == "keywords":
                    paper["keywords"] = [k.strip() for k in val.split(",") if k.strip()]
                elif bib_field == "doi":
                    paper["doi"] = val.lower().lstrip("https://doi.org/")
                else:
                    paper[our_field] = val
            if paper.get("title"):
                results.append(paper)
        return results

    def _parse_authors(self, author_str: str) -> list[dict[str, str]]:
        names = [a.strip() for a in author_str.split(" and ") if a.strip()]
        result = []
        for name in names:
            parts = [p.strip() for p in name.split(",")]
            if len(parts) >= 2:
                full_name = f"{parts[1]} {parts[0]}"
            else:
                full_name = parts[0]
            result.append({"name": full_name.strip("{}"), "affil": ""})
        return result
