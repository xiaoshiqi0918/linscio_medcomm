"""形式路由 API - FormatPicker / 章节结构"""
from fastapi import APIRouter

from app.services.format_router import (
    get_all_formats,
    get_format_sections,
    FORMAT_PLATFORM_MATRIX,
)

router = APIRouter()


@router.get("")
async def list_formats():
    """返回所有科普形式定义，供前端 FormatPicker 使用"""
    return {
        "formats": get_all_formats(),
        "matrix": FORMAT_PLATFORM_MATRIX,
    }


@router.get("/{format_id}/sections")
async def get_sections(format_id: str):
    """返回某形式的章节结构定义"""
    sections = get_format_sections(format_id)
    if sections is None:
        return {"sections": [], "error": "unknown_format"}
    return {"sections": sections}
