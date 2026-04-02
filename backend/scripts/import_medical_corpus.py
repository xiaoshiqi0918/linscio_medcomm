"""
Medical Corpus 批量导入管道（可选）
==================================
默认推荐流程：在 MedComm 客户端 **知识库** 中手动上传需参考的 TXT / PDF / MD；
写作规范与系统侧 RAG 摘要、Few-shot 种子由人工维护（见 prompt-example 与
seed_web_corpus_examples.py），不必跑本脚本。

本脚本仅在需要 **大批量扫描 / 试导入 / 自动筛 examples** 时使用，按目录分类处理语料、
过滤低质内容，分流到 RAG 知识库文件或 Few-shot 示例。

语料库结构：
  Medical Corpus/
  ├── Clinical Guidance/     (34 files)   → RAG 知识库（系统内置，高优先）
  ├── Expert Consensus/      (121 files)  → RAG 知识库（系统内置，高优先）
  ├── Textbook/              (43 files)   → RAG 知识库（系统内置）
  ├── EMR/                   (7 files)    → RAG 知识库（仅供参考）
  ├── Web Article/           (大量 txt)   → 过滤后分流到 RAG / Few-shot / 丢弃
  └── Wiki/                  (1 file)     → RAG 知识库

用法（在 linscio_medcomm/backend 目录下）：

  # 只扫「Web Article」文件夹（推荐：--corpus-dir 直接指向 Web Article）
  python -m scripts.import_medical_corpus --corpus-dir "/path/to/Medical Corpus/Medical Corpus/Web Article" --mode scan

  # 导入 Web Article 到 prompt-example/system-knowledge/（限流避免一次写几十万文件）
  python -m scripts.import_medical_corpus --corpus-dir "/path/to/.../Web Article" --mode import --category web_article --limit 500 --dry-run

  # 从 Web Article 筛选高分条目写入 writing_examples（需数据库可用）
  python -m scripts.import_medical_corpus --corpus-dir "/path/to/.../Web Article" --mode examples --limit 100 --dry-run

  # 语料根目录（含多个子文件夹）扫描
  python -m scripts.import_medical_corpus --corpus-dir "/path/to/Medical Corpus/Medical Corpus" --mode scan
"""
import argparse
import asyncio
import logging
import os
import re
from pathlib import Path

from app.core.database import AsyncSessionLocal
from app.models.knowledge import KnowledgeDoc

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("corpus_import")

CATEGORY_MAP = {
    "Clinical Guidance": "clinical_guidance",
    "Expert Consensus": "expert_consensus",
    "Textbook": "textbook",
    "EMR": "emr",
    "Web Article": "web_article",
    "Wiki": "wiki",
}

PRIORITY_CATEGORIES = {"clinical_guidance", "expert_consensus", "textbook"}

MIN_CONTENT_LENGTH = 100
MAX_CONTENT_LENGTH = 500_000

AD_BRAND_PATTERNS = [
    r"以岭",
    r"八子补肾",
    r"碧凯",
    r"保妇康",
    r"丁桂",
    r"薏芽健脾",
    r"热淋清",
    r"欣康",
    r"六味地黄",
    r"汤臣倍健",
    r"修正",
    r"同仁堂",
    r"仁和",
    r"云南白药",
]

AD_STRUCTURE_PATTERNS = [
    r"以上内容就是针对",
    r"以上就是对.{2,10}的(简单)?介绍",
    r"看完你就了解了",
    r"这些你都了解了吗",
    r"具有非常好的.{2,10}效果",
    r"从根本上(补肾|治疗|解决)",
    r"疗程服用也放心",
    r"成分包含了\d+个",
]

TEMPLATE_DIET_PATTERN = re.compile(
    r"饮食以清淡.*易消化为主.*多吃蔬果.*合理搭配膳食.*注意营养充足.*忌辛辣.*油腻.*生冷"
)

_ad_brand_re = re.compile("|".join(AD_BRAND_PATTERNS))
_ad_struct_re = re.compile("|".join(AD_STRUCTURE_PATTERNS))


class QualityResult:
    __slots__ = ("passed", "score", "reject_reasons")

    def __init__(self, passed: bool, score: float, reject_reasons: list[str]):
        self.passed = passed
        self.score = score
        self.reject_reasons = reject_reasons


def assess_quality(text: str, category: str) -> QualityResult:
    """
    评估文章质量，返回通过/拒绝和分数。
    高优先类别（指南、共识、教科书）仅做基本长度检查。
    Web Article 需要通过广告检测、模板检测、长度检查。
    """
    reasons = []
    score = 50.0

    content = text.strip()
    length = len(content)

    if length < MIN_CONTENT_LENGTH:
        reasons.append(f"too_short({length})")
        return QualityResult(False, 0, reasons)

    if length > MAX_CONTENT_LENGTH:
        reasons.append(f"too_long({length})")
        return QualityResult(False, 0, reasons)

    if category in PRIORITY_CATEGORIES:
        score = 80.0
        if length > 1000:
            score += 10
        return QualityResult(True, min(score, 100), reasons)

    brand_matches = _ad_brand_re.findall(content)
    if brand_matches:
        reasons.append(f"ad_brand({','.join(list(set(brand_matches))[:3])})")
        score -= 40

    struct_matches = _ad_struct_re.findall(content)
    if struct_matches:
        reasons.append(f"ad_structure({len(struct_matches)} hits)")
        score -= 20

    if TEMPLATE_DIET_PATTERN.search(content):
        reasons.append("template_diet")
        score -= 15

    if length < 200:
        score -= 10
    elif length > 500:
        score += 10
    elif length > 1500:
        score += 20

    numbered = len(re.findall(r"^\s*\d+[.、．）]", content, re.MULTILINE))
    if numbered >= 3:
        score += 10

    passed = score >= 40 and not brand_matches
    return QualityResult(passed, max(0, min(100, score)), reasons)


def read_txt(path: Path) -> str:
    for enc in ("utf-8", "gbk", "gb2312", "latin-1"):
        try:
            return path.read_text(encoding=enc)
        except (UnicodeDecodeError, UnicodeError):
            continue
    return ""


def resolve_paths(corpus_dir: Path) -> tuple[Path, Path]:
    """
    返回 (corpus_root, web_article_dir)。

    corpus-dir 可以是：
    - …/Medical Corpus/Medical Corpus（内含 Web Article、Clinical Guidance 等）
    - …/Web Article（直接指向网页文章文件夹）
    """
    corpus_dir = corpus_dir.expanduser().resolve()
    if corpus_dir.name == "Web Article":
        return corpus_dir.parent, corpus_dir
    return corpus_dir, corpus_dir / "Web Article"


def count_txt_files(dir_path: Path) -> int:
    """大目录下统计 .txt 数量，不占内存列出全部文件名。"""
    if not dir_path.is_dir():
        return 0
    n = 0
    with os.scandir(dir_path) as it:
        for entry in it:
            if entry.is_file() and entry.name.endswith(".txt"):
                n += 1
    return n


def iter_txt_files(dir_path: Path, limit: int | None = None):
    """遍历目录下 .txt，大目录勿一次性 sorted(glob)。"""
    n = 0
    with os.scandir(dir_path) as it:
        for entry in it:
            if entry.is_file() and entry.name.endswith(".txt"):
                yield Path(entry.path)
                n += 1
                if limit is not None and n >= limit:
                    return


def scan_corpus(corpus_dir: Path, sample_limit: int = 200):
    """扫描语料库，输出各目录统计和质量分布。"""
    root, web_article_dir = resolve_paths(corpus_dir)
    logger.info(f"Corpus root: {root}")
    logger.info(f"Web Article dir: {web_article_dir}")

    for dir_name, cat_key in CATEGORY_MAP.items():
        if dir_name == "Web Article":
            sub = web_article_dir
        else:
            sub = root / dir_name

        if not sub.exists():
            logger.info(f"  {dir_name}: NOT FOUND ({sub})")
            continue

        if dir_name == "Web Article":
            total = count_txt_files(sub)
            files_iter = iter_txt_files(sub, limit=min(sample_limit, total) if total else sample_limit)
            file_list = list(files_iter)
        else:
            files = sorted(sub.glob("*.txt"))
            total = len(files)
            file_list = files[: min(sample_limit, total)]

        sample_size = len(file_list)
        passed = 0
        rejected = 0
        reject_reasons_agg: dict[str, int] = {}

        for f in file_list:
            text = read_txt(f)
            result = assess_quality(text, cat_key)
            if result.passed:
                passed += 1
            else:
                rejected += 1
                for r in result.reject_reasons:
                    key = r.split("(")[0]
                    reject_reasons_agg[key] = reject_reasons_agg.get(key, 0) + 1

        logger.info(
            f"  {dir_name}: {total} files total, "
            f"sampled {sample_size} → {passed} passed, {rejected} rejected"
        )
        if reject_reasons_agg:
            logger.info(f"    reject reasons: {reject_reasons_agg}")


async def import_category(
    corpus_dir: Path,
    category: str,
    limit: int = 0,
    dry_run: bool = False,
):
    """导入指定类别到 system-knowledge 目录。"""
    dir_name = None
    for dn, ck in CATEGORY_MAP.items():
        if ck == category:
            dir_name = dn
            break
    if not dir_name:
        logger.error(f"Unknown category: {category}")
        return

    root, web_article_dir = resolve_paths(corpus_dir)
    if dir_name == "Web Article":
        sub = web_article_dir
    else:
        sub = root / dir_name

    if not sub.exists():
        logger.error(f"Directory not found: {sub}")
        return

    target_dir = Path(__file__).resolve().parents[1].parent / "prompt-example" / "system-knowledge"
    target_dir.mkdir(parents=True, exist_ok=True)

    if dir_name == "Web Article":
        cap = limit if limit > 0 else 1000
        if limit == 0:
            logger.warning(
                "Web Article: --limit 未指定，默认只处理前 1000 个文件，避免一次性导入超大规模目录。"
                " 需要更多请显式传入，例如 --limit 5000"
            )
        files = list(iter_txt_files(sub, limit=cap))
    else:
        files = sorted(sub.glob("*.txt"))
        if limit > 0:
            files = files[:limit]

    imported = 0
    skipped = 0
    rejected = 0

    for f in files:
        text = read_txt(f)
        result = assess_quality(text, category)

        if not result.passed:
            rejected += 1
            if rejected <= 5:
                logger.debug(f"  rejected: {f.name} — {result.reject_reasons}")
            continue

        safe_name = f"corpus_{category}_{f.stem}"
        target_file = target_dir / f"{safe_name}.txt"

        if target_file.exists():
            skipped += 1
            continue

        if dry_run:
            logger.info(f"  [dry-run] would write: {target_file.name} (score={result.score:.0f})")
            imported += 1
            continue

        header = (
            f"【语料来源】Medical Corpus / {dir_name} / {f.name}\n"
            f"【质量评分】{result.score:.0f}/100\n\n"
        )
        target_file.write_text(header + text.strip(), encoding="utf-8")
        imported += 1

    logger.info(
        f"Category '{category}': {imported} imported, {skipped} skipped (exists), {rejected} rejected"
    )

    if not dry_run and imported > 0:
        logger.info("Restart the app to trigger system_knowledge auto-indexing.")


async def import_web_articles_as_examples(
    corpus_dir: Path,
    limit: int = 50,
    dry_run: bool = False,
    scan_cap: int = 20_000,
):
    """
    从 Web Article 中筛选高质量文章作为 Few-shot 示例。
    仅选择 score >= 70 的文章。
    大目录下按顺序扫描至多 scan_cap 个文件寻找候选（避免 glob 百万文件）。
    """
    from app.models.example import WritingExample

    _, sub = resolve_paths(corpus_dir)
    if not sub.exists():
        logger.error("Web Article directory not found: %s", sub)
        return

    candidates = []
    scanned = 0

    for f in iter_txt_files(sub):
        scanned += 1
        if scanned > scan_cap:
            logger.warning(
                "Stopped scanning after %s files (no enough high-score candidates). "
                "Increase scan_cap in code or pass --scan-cap when added.",
                scan_cap,
            )
            break
        if len(candidates) >= limit * 5:
            break
        text = read_txt(f)
        result = assess_quality(text, "web_article")
        if result.passed and result.score >= 70:
            candidates.append((f, text, result.score))

    candidates.sort(key=lambda x: -x[2])
    top = candidates[:limit]

    logger.info("Scanned %s .txt files under Web Article, %s high-score candidates", scanned, len(candidates))

    if dry_run:
        for f, text, score in top:
            title = text.strip().split("\n")[0][:60]
            logger.info(f"  [dry-run] example candidate: {f.name} score={score:.0f} title={title}")
        logger.info(f"Would add up to {len(top)} examples (dry-run).")
        return

    async with AsyncSessionLocal() as db:
        added = 0
        for f, text, score in top:
            source_doc = f"Medical Corpus/Web Article/{f.stem}"
            existing = await db.execute(
                WritingExample.__table__.select().where(
                    WritingExample.source_doc == source_doc
                )
            )
            if existing.first():
                continue

            row = WritingExample(
                content_format="article",
                section_type="body",
                target_audience="public",
                platform="universal",
                specialty=None,
                content_text=text.strip(),
                content_json=None,
                analysis_text=None,
                source_doc=source_doc,
                source="corpus",
                medical_reviewed=0,
                is_active=1,
            )
            db.add(row)
            added += 1

        await db.commit()
        logger.info(f"Added {added} web article examples to writing_examples.")


def main():
    parser = argparse.ArgumentParser(description="Medical Corpus batch import pipeline")
    parser.add_argument(
        "--corpus-dir",
        required=True,
        help="Medical Corpus 根目录（含 Web Article 等子文件夹），或直接指向 …/Web Article 文件夹",
    )
    parser.add_argument(
        "--mode",
        choices=["scan", "import", "examples"],
        required=True,
        help="scan: preview stats; import: import to system-knowledge; examples: import as few-shot",
    )
    parser.add_argument("--category", help="Category to import (for import mode)")
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="import: max files（Web Article 未指定时默认 1000）；examples: 写入示例条数上限（默认 50）",
    )
    parser.add_argument(
        "--sample",
        type=int,
        default=200,
        help="scan 模式：每个目录最多抽样评估质量的文件数（Web Article 为目录内前 N 个，顺序取决于文件系统）",
    )
    parser.add_argument(
        "--scan-cap",
        type=int,
        default=20_000,
        help="examples 模式：最多扫描多少个 txt 以寻找高分候选（避免遍历整个超大规模目录）",
    )
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing files")
    args = parser.parse_args()

    corpus_dir = Path(args.corpus_dir)
    if not corpus_dir.exists():
        logger.error(f"Corpus directory not found: {corpus_dir}")
        return

    if args.mode == "scan":
        scan_corpus(corpus_dir, sample_limit=args.sample)
    elif args.mode == "import":
        if not args.category:
            logger.error("--category is required for import mode")
            return
        asyncio.run(import_category(corpus_dir, args.category, args.limit, args.dry_run))
    elif args.mode == "examples":
        ex_limit = args.limit if args.limit > 0 else 50
        asyncio.run(
            import_web_articles_as_examples(
                corpus_dir, ex_limit, args.dry_run, scan_cap=args.scan_cap
            )
        )


if __name__ == "__main__":
    main()
