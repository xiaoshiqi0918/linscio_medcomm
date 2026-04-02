"""数据管理 API"""
import json
import zipfile
import io
from pathlib import Path
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy import select, func

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.core.license import load_license
from app.models.article import Article, ArticleSection, ArticleContent
from app.models.term import MedicalTerm
from app.models.example import WritingExample

router = APIRouter()


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session


@router.post("/backup/export")
async def export_backup():
    """导出数据备份（JSON 快照）"""
    from sqlalchemy import select

    async with AsyncSessionLocal() as db:
        articles = (await db.execute(select(Article).where(Article.deleted_at.is_(None)))).scalars().all()
        sections = (await db.execute(select(ArticleSection))).scalars().all()
        contents = (await db.execute(select(ArticleContent))).scalars().all()
    data = {
        "version": 1,
        "exported_at": datetime.utcnow().isoformat(),
        "articles": [_row_to_dict(a) for a in articles],
        "sections": [_row_to_dict(s) for s in sections],
        "contents": [_row_to_dict(c) for c in contents],
    }
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("backup.json", json.dumps(data, ensure_ascii=False, indent=2))
    buf.seek(0)
    fn = f"linscio_backup_{datetime.utcnow().strftime('%Y%m%d_%H%M')}.zip"
    return Response(
        content=buf.getvalue(),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{fn}"'},
    )


def _row_to_dict(row) -> dict:
    d = {}
    for c in row.__table__.columns:
        v = getattr(row, c.name)
        if hasattr(v, "isoformat"):
            v = v.isoformat() if v else None
        d[c.name] = v
    return d


class ImportRequest(BaseModel):
    merge_strategy: str = "replace"  # replace | merge


@router.post("/backup/import")
async def import_backup(file: UploadFile, merge_strategy: str = "replace"):
    """导入数据备份（含 merge_strategy：replace 覆盖 / merge 合并）"""
    if not file.filename or not file.filename.endswith(".zip"):
        raise HTTPException(400, detail="仅支持 .zip 备份文件")
    raw = await file.read()
    try:
        with zipfile.ZipFile(io.BytesIO(raw), "r") as zf:
            data = json.loads(zf.read("backup.json").decode("utf-8"))
    except Exception as e:
        raise HTTPException(400, detail=f"备份文件解析失败: {e}")
    # 简化实现：仅记录导入请求，实际写入需根据 merge_strategy 处理
    return {"ok": True, "message": "备份导入功能开发中", "merge_strategy": merge_strategy}


@router.get("/content-stats")
async def content_stats():
    """内容库统计：词典、示例、知识库数量。基础版返回通用预置，定制版返回学科包统计"""
    lic = load_license()
    stats: dict = {"terms": 0, "examples": 0, "docs": 0, "by_specialty": {}}
    specialty_stats = lic.get("specialty_stats", {})
    async with AsyncSessionLocal() as db:
        if lic.get("type") == "custom":
            for sp in lic.get("custom_specialties", []):
                cfg = specialty_stats.get(sp, {})
                if cfg:
                    stats["by_specialty"][sp] = {
                        "terms": cfg.get("terms", 0),
                        "examples": cfg.get("examples", 0),
                        "docs": cfg.get("docs", 0),
                        "updated_at": cfg.get("updated_at"),
                    }
                else:
                    t_res = await db.execute(
                        select(func.count(MedicalTerm.id)).where(
                        (MedicalTerm.specialty == sp) | (MedicalTerm.specialty.is_(None))
                    ))
                    e_res = await db.execute(
                        select(func.count(WritingExample.id)).where(
                        (WritingExample.specialty == sp) | (WritingExample.specialty.is_(None))
                    ))
                    stats["by_specialty"][sp] = {
                        "terms": t_res.scalar() or 0,
                        "examples": e_res.scalar() or 0,
                        "docs": len([d for d in lic.get("preset_docs", []) if d.get("specialty") == sp]),
                        "updated_at": None,
                    }
        stats["terms"] = (await db.execute(select(func.count(MedicalTerm.id)))).scalar() or 0
        stats["examples"] = (await db.execute(select(func.count(WritingExample.id)))).scalar() or 0
    from app.models.knowledge import KnowledgeDoc
    async with AsyncSessionLocal() as db:
        stats["docs"] = (await db.execute(select(func.count(KnowledgeDoc.id)))).scalar() or 0
    return stats


@router.post("/images/cleanup")
async def cleanup_images():
    """清理未关联的生成图像文件"""
    from sqlalchemy import select
    from app.models.image import GeneratedImage

    async with AsyncSessionLocal() as db:
        used = (await db.execute(select(GeneratedImage.file_path))).fetchall()
    used_paths = {r[0] for r in used if r[0]}
    images_dir = Path(settings.app_data_root) / "images"
    removed = 0
    if images_dir.exists():
        for f in images_dir.rglob("*.png"):
            rel = f.relative_to(settings.app_data_root).as_posix()
            if rel not in used_paths:
                try:
                    f.unlink()
                    removed += 1
                except Exception:
                    pass
    return {"ok": True, "removed": removed}
