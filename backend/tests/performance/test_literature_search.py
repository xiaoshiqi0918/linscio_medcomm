"""
文献支撑库性能与验收测试

运行方式：
  1. 启动后端：uvicorn app.main:app --reload
  2. 执行测试：pytest tests/performance/test_literature_search.py -v -s
  3. 需安装：pip install pytest pytest-asyncio httpx

环境变量 LITERATURE_API_BASE 可覆盖默认 base_url（默认 http://127.0.0.1:8765）
"""
import os
import time

import pytest
from httpx import AsyncClient

BASE_URL = os.environ.get("LITERATURE_API_BASE", "http://127.0.0.1:8765")


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def async_client():
    async with AsyncClient(base_url=BASE_URL, timeout=30.0) as client:
        yield client


async def _seed_papers(client: AsyncClient, count: int):
    """预置 count 条测试数据"""
    for i in range(count):
        await client.post(
            "/api/v1/literature/papers",
            json={
                "title": f"糖尿病防治指南与中国慢性病管理研究 {i}",
                "authors": [{"name": "张三", "affil": "某医院"}],
                "journal": "中华医学杂志",
                "year": 2020 + (i % 4),
                "doi": None if i < count - 100 else f"10.1000/test.{i:06d}",
            },
        )


@pytest.mark.asyncio
async def test_search_1w_papers(async_client: AsyncClient):
    """1万条数据量级下列表检索响应 < 500ms（需预置数据，或跳过）"""
    # 先测当前列表接口响应时间
    start = time.perf_counter()
    resp = await async_client.get(
        "/api/v1/literature/papers",
        params={"q": "糖尿病", "year_from": 2020, "page": 1, "page_size": 20},
    )
    elapsed = time.perf_counter() - start

    assert resp.status_code == 200
    assert elapsed < 0.5, f"响应时间 {elapsed:.3f}s 超过 500ms"


@pytest.mark.asyncio
async def test_doi_dedup_accuracy(async_client: AsyncClient):
    """DOI 去重场景：相同 DOI 返回 exact_match=True"""
    doi = "10.2337/dc22-1399"
    r1 = await async_client.post(
        "/api/v1/literature/papers",
        json={
            "title": "已存在文献",
            "authors": [{"name": "A", "affil": ""}],
            "doi": doi,
        },
    )
    assert r1.status_code in (200, 201)

    resp = await async_client.post(
        "/api/v1/literature/papers/check-duplicate",
        json={"doi": doi, "title": "任意标题"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["exact_match"] is True
    assert data.get("paper_id") is not None


@pytest.mark.asyncio
async def test_ris_import_success_rate(async_client: AsyncClient):
    """RIS 标准样本成功率 > 95%"""
    samples_ris = """TY  - JOUR
TI  - Standards of Care in Diabetes
AU  - American Diabetes Association
JO  - Diabetes Care
PY  - 2023
VL  - 46
IS  - 1
SP  - 1
EP  - 100
DO  - 10.2337/dc23-S001
ER  - 

TY  - JOUR
TI  - GLP-1 Receptor Agonists
AU  - Smith J
AU  - Doe A
JO  - Nature Medicine
PY  - 2024
DO  - 10.1038/s41591-024-00001
ER  - 
"""
    files = {"file": ("test.ris", samples_ris.encode("utf-8"), "application/x-research-info-systems")}
    resp = await async_client.post("/api/v1/literature/papers/import", files=files)
    assert resp.status_code == 200
    data = resp.json()
    success = data.get("success", 0)
    total = 2
    success_rate = success / total
    assert success_rate >= 0.95, f"RIS 成功率 {success_rate:.1%} 低于 95%"
