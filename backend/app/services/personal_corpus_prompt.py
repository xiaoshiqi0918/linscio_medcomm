"""个人语料 → 提示词片段"""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.personal_corpus import PersonalCorpusEntry

MAX_ENTRIES_IN_PROMPT = 36


async def load_corpus_block(db: AsyncSession, user_id: int = 1) -> str:
    r = await db.execute(
        select(PersonalCorpusEntry)
        .where(
            PersonalCorpusEntry.user_id == user_id,
            PersonalCorpusEntry.enabled == True,
        )
        .order_by(PersonalCorpusEntry.id.desc())
        .limit(MAX_ENTRIES_IN_PROMPT)
    )
    rows = list(r.scalars().all())
    if not rows:
        return ""

    avoids, prefers, notes = [], [], []
    for e in rows:
        k = (e.kind or "note").lower()
        a = (e.anchor or "").strip()
        c = (e.content or "").strip()
        if k == "avoid" and a:
            avoids.append(f"- 避免使用「{a}」" + (f"；建议：{c}" if c else ""))
        elif k == "prefer" and a:
            prefers.append(f"- 涉及「{a}」时优先表述为：{c or a}")
        elif k == "note" and (a or c):
            notes.append(f"- {a + '：' if a else ''}{c}")

    parts = []
    if avoids:
        parts.append("【避免用语】\n" + "\n".join(avoids))
    if prefers:
        parts.append("【倾向表述】\n" + "\n".join(prefers))
    if notes:
        parts.append("【个人备忘】\n" + "\n".join(notes))
    if not parts:
        return ""
    return (
        "【个人写作语料（长期使用中积累，请尽量遵守；与医学事实冲突时以事实为准）】\n"
        + "\n\n".join(parts)
    )
