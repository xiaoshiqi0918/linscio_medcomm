"""
学科包 / 绘图扩展包管理 API
安装 / 卸载 / 状态查询 / 本地导入
"""
import json
import logging
import shutil
import zipfile
from pathlib import Path

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.config import settings
from app.models.specialty_package import SpecialtyPackage
from app.models.knowledge import KnowledgeDoc
from app.models.term import MedicalTerm
from app.models.example import WritingExample

logger = logging.getLogger("linscio.specialty_api")

router = APIRouter()


class InstallRequest(BaseModel):
    pack_dir: str
    specialty_id: str
    name: str = ""
    version: str = "1.0.0"


class InstallResponse(BaseModel):
    ok: bool
    specialty_id: str
    config: bool = False
    knowledge_docs: int = 0
    terms: int = 0
    examples: int = 0
    errors: list[str] = []


class UninstallRequest(BaseModel):
    specialty_id: str


class PackStatusItem(BaseModel):
    specialty_id: str
    name: str
    category: str = "specialty"
    local_version: str | None = None
    remote_version: str | None = None
    status: str = "not_installed"
    knowledge_docs: int = 0
    terms: int = 0
    examples: int = 0


@router.post("/install", response_model=InstallResponse)
async def install_pack(req: InstallRequest, db: AsyncSession = Depends(get_session)):
    """安装学科包：接收解压后的目录路径，执行知识/术语/范例/配置的全量导入"""
    from app.services.knowledge.pack_installer import install_specialty_pack

    pack_path = Path(req.pack_dir)
    if not pack_path.exists():
        return InstallResponse(ok=False, specialty_id=req.specialty_id, errors=[f"目录不存在: {req.pack_dir}"])

    result = await install_specialty_pack(pack_path, req.specialty_id, db)

    # 更新 specialty_packages 状态表
    sp = await db.execute(
        select(SpecialtyPackage).where(SpecialtyPackage.specialty_id == req.specialty_id)
    )
    pkg = sp.scalar_one_or_none()
    if pkg:
        pkg.local_version = req.version
        pkg.status = "installed"
        pkg.name = req.name or pkg.name
        from datetime import datetime
        pkg.installed_at = datetime.utcnow()
        pkg.updated_at = datetime.utcnow()
    else:
        from datetime import datetime
        pkg = SpecialtyPackage(
            specialty_id=req.specialty_id,
            name=req.name or req.specialty_id,
            local_version=req.version,
            remote_version=req.version,
            status="installed",
            installed_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db.add(pkg)
    await db.commit()

    has_errors = len(result.get("errors", [])) > 0
    return InstallResponse(
        ok=not has_errors,
        specialty_id=req.specialty_id,
        config=result.get("config", False),
        knowledge_docs=result.get("knowledge_docs", 0),
        terms=result.get("terms", 0),
        examples=result.get("examples", 0),
        errors=result.get("errors", []),
    )


@router.post("/uninstall")
async def uninstall_pack(req: UninstallRequest, db: AsyncSession = Depends(get_session)):
    """卸载学科包：清除该学科 package 来源的所有数据"""
    from app.services.knowledge.pack_installer import uninstall_specialty_pack

    counts = await uninstall_specialty_pack(req.specialty_id, db)

    sp = await db.execute(
        select(SpecialtyPackage).where(SpecialtyPackage.specialty_id == req.specialty_id)
    )
    pkg = sp.scalar_one_or_none()
    if pkg:
        pkg.status = "not_installed"
        pkg.local_version = None
        await db.commit()

    return {"ok": True, "specialty_id": req.specialty_id, "removed": counts}


@router.get("/status", response_model=list[PackStatusItem])
async def get_pack_status(db: AsyncSession = Depends(get_session)):
    """获取所有已知学科包状态（含内容统计）"""
    result = await db.execute(select(SpecialtyPackage))
    packages = result.scalars().all()

    items = []
    for pkg in packages:
        sid = pkg.specialty_id

        doc_count = await db.execute(
            select(func.count()).select_from(KnowledgeDoc).where(
                KnowledgeDoc.specialty == sid, KnowledgeDoc.source == "package"
            )
        )
        term_count = await db.execute(
            select(func.count()).select_from(MedicalTerm).where(
                MedicalTerm.specialty == sid, MedicalTerm.source == "package"
            )
        )
        example_count = await db.execute(
            select(func.count()).select_from(WritingExample).where(
                WritingExample.specialty == sid, WritingExample.source == "package"
            )
        )

        cat = "drawing" if sid.startswith("medpic-") else "specialty"
        items.append(PackStatusItem(
            specialty_id=sid,
            name=pkg.name,
            category=cat,
            local_version=pkg.local_version,
            remote_version=pkg.remote_version,
            status=pkg.status,
            knowledge_docs=doc_count.scalar() or 0,
            terms=term_count.scalar() or 0,
            examples=example_count.scalar() or 0,
        ))

    return items


class ImportLocalRequest(BaseModel):
    zip_path: str


@router.post("/import-local")
async def import_local_pack(req: ImportLocalRequest, db: AsyncSession = Depends(get_session)):
    """
    从本地 zip 导入扩展包（学科包或绘图扩展包）。
    zip 内需包含 manifest.json 描述 pack_id / name / version / category。
    """
    zip_path = Path(req.zip_path)
    if not zip_path.exists() or not zip_path.suffix == ".zip":
        return {"ok": False, "error": f"文件不存在或非 zip: {req.zip_path}"}

    packs_root = Path(settings.DATA_DIR) / "imported-packs"
    packs_root.mkdir(parents=True, exist_ok=True)

    extract_dir = packs_root / zip_path.stem
    if extract_dir.exists():
        shutil.rmtree(extract_dir)

    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(extract_dir)
    except zipfile.BadZipFile:
        return {"ok": False, "error": "无效的 zip 文件"}

    manifest_file = extract_dir / "manifest.json"
    if not manifest_file.exists():
        inner_dirs = [d for d in extract_dir.iterdir() if d.is_dir()]
        if len(inner_dirs) == 1 and (inner_dirs[0] / "manifest.json").exists():
            extract_dir = inner_dirs[0]
            manifest_file = extract_dir / "manifest.json"

    if not manifest_file.exists():
        return {"ok": False, "error": "扩展包缺少 manifest.json"}

    try:
        meta = json.loads(manifest_file.read_text(encoding="utf-8"))
    except Exception:
        return {"ok": False, "error": "manifest.json 格式错误"}

    pack_id = meta.get("id") or meta.get("pack_id") or zip_path.stem
    pack_name = meta.get("name") or pack_id
    pack_version = meta.get("version", "1.0.0")
    pack_category = meta.get("category", "specialty")

    sp = await db.execute(
        select(SpecialtyPackage).where(SpecialtyPackage.specialty_id == pack_id)
    )
    pkg = sp.scalar_one_or_none()

    from datetime import datetime
    now = datetime.utcnow()

    if pkg:
        pkg.local_version = pack_version
        pkg.status = "installed"
        pkg.name = pack_name
        pkg.updated_at = now
    else:
        pkg = SpecialtyPackage(
            specialty_id=pack_id,
            name=pack_name,
            local_version=pack_version,
            remote_version=pack_version,
            status="installed",
            installed_at=now,
            updated_at=now,
        )
        db.add(pkg)

    await db.commit()

    result = {
        "ok": True,
        "pack_id": pack_id,
        "name": pack_name,
        "version": pack_version,
        "category": pack_category,
        "install_dir": str(extract_dir),
    }

    if pack_category == "specialty":
        try:
            from app.services.knowledge.pack_installer import install_specialty_pack
            install_result = await install_specialty_pack(extract_dir, pack_id, db)
            result["knowledge_docs"] = install_result.get("knowledge_docs", 0)
            result["terms"] = install_result.get("terms", 0)
            result["examples"] = install_result.get("examples", 0)
        except Exception as e:
            logger.warning("specialty pack install content failed: %s", e)

    return result
