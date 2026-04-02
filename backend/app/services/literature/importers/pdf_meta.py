"""从 PDF 提取元数据（pypdf）"""
import re
from pathlib import Path
from typing import Any


class PDFMetadataImporter:
    def extract(self, pdf_path: str | Path) -> dict[str, Any]:
        path = Path(pdf_path)
        if not path.exists():
            return {}
        try:
            from pypdf import PdfReader
        except ImportError:
            return {}
        try:
            reader = PdfReader(str(path))
            meta = reader.metadata or {}
        except Exception:
            return {}

        def get_meta(k: str) -> str:
            v = meta.get(k) or meta.get(f"/{k.lstrip('/')}")
            return (v or "").strip() if isinstance(v, str) else ""

        result: dict[str, Any] = {
            "title": get_meta("Title") or get_meta("/Title"),
            "author": get_meta("Author") or get_meta("/Author"),
        }

        if not result["title"] and len(reader.pages) > 0:
            try:
                first_page = reader.pages[0].extract_text() or ""
                lines = [l.strip() for l in first_page.split("\n") if l.strip()]
                if lines:
                    result["title"] = lines[0][:200]
            except Exception:
                pass

        if result.get("author"):
            names = re.split(r"[,;]", result["author"])
            result["authors"] = [{"name": n.strip(), "affil": ""} for n in names if n.strip()]
            del result["author"]
        elif "author" in result:
            del result["author"]

        return {k: v for k, v in result.items() if v}
