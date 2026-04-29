#!/usr/bin/env python3
"""
文章生成质量评测脚本
用法:  python3 backend/scripts/eval_article.py [--topic "..."] [--word-count N]
"""
import argparse, json, time, re, sys
import httpx

API = "http://127.0.0.1:8765/api/v1"
TOKEN: str = ""

SECTION_TITLES = {
    "body": "正文",
    "case": "案例",
    "qa": "Q&A",
    "summary": "小结",
}


def _headers() -> dict:
    if TOKEN:
        return {"Authorization": f"Bearer {TOKEN}"}
    return {}


def ensure_auth():
    """注册或登录测试用户，获取 JWT token"""
    global TOKEN
    phone = "13800000099"
    password = "test123456"

    resp = httpx.post(f"{API}/auth/login", json={
        "phone": phone, "password": password,
    }, timeout=10)

    if resp.status_code == 200:
        TOKEN = resp.json()["access_token"]
        print(f"   ✅ 登录成功 (user_id={resp.json().get('user_id')})")
        return

    resp2 = httpx.post(f"{API}/auth/register", json={
        "phone": phone, "password": password,
        "display_name": "评测用户", "agreed_terms": True,
    }, timeout=10)
    if resp2.status_code == 200:
        TOKEN = resp2.json()["access_token"]
        print(f"   ✅ 注册成功 (user_id={resp2.json().get('user_id')})")
        return

    print(f"   ❌ 认证失败: {resp2.status_code} {resp2.text}")
    sys.exit(1)


def _bigrams(s: str) -> set[str]:
    return {s[i:i+2] for i in range(len(s) - 1)}


def paragraph_similarity(a: str, b: str) -> float:
    if len(a) < 20 or len(b) < 20:
        return 0.0
    sa, sb = _bigrams(a), _bigrams(b)
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def create_article(topic: str, word_count: int) -> dict:
    """POST 创建文章"""
    resp = httpx.post(f"{API}/medcomm/articles", json={
        "content_format": "article",
        "topic": topic,
        "platform": "wechat",
        "target_audience": "public",
        "target_word_count": word_count,
    }, headers=_headers(), timeout=30)
    resp.raise_for_status()
    return resp.json()


def generate_all_sse(article_id: int) -> dict[str, str]:
    """SSE 流式生成全部章节，返回 {section_type: content}"""
    sections: dict[str, str] = {}
    current_section_type = ""
    current_section_buf = []

    with httpx.stream(
        "POST", f"{API}/medcomm/articles/{article_id}/generate-all",
        headers=_headers(),
        timeout=httpx.Timeout(connect=10, read=600, write=10, pool=10),
    ) as resp:
        resp.raise_for_status()
        for line in resp.iter_lines():
            if not line.startswith("data: "):
                continue
            data = json.loads(line[6:])
            evt_type = data.get("type", "")

            if evt_type == "section_start":
                if current_section_type and current_section_buf:
                    sections[current_section_type] = "".join(current_section_buf)
                current_section_type = data.get("section_type", "")
                current_section_buf = []
                st_label = SECTION_TITLES.get(current_section_type, current_section_type)
                print(f"  ⏳ 生成中: {st_label} ({data.get('index')}/{data.get('total')})")

            elif evt_type == "delta":
                current_section_buf.append(data.get("text", ""))

            elif evt_type == "rewritten_content":
                current_section_buf = [data.get("content", "")]

            elif evt_type == "section_done":
                if current_section_type and current_section_buf:
                    sections[current_section_type] = "".join(current_section_buf)
                    st_label = SECTION_TITLES.get(current_section_type, current_section_type)
                    wc = len(sections[current_section_type])
                    print(f"  ✅ {st_label}: {wc} 字")
                current_section_buf = []

            elif evt_type == "batch_done":
                if current_section_type and current_section_buf:
                    sections[current_section_type] = "".join(current_section_buf)
                break

    return sections


def evaluate(sections: dict[str, str], target_wc: int):
    """评估指标"""
    print("\n" + "=" * 60)
    print("📊 评 测 报 告")
    print("=" * 60)

    all_text = "\n\n".join(sections.values())
    total_wc = len(all_text)
    print(f"\n📝 总字数: {total_wc} / 目标 {target_wc}")
    deviation = abs(total_wc - target_wc) / target_wc * 100
    print(f"   偏差: {deviation:.1f}%")

    # --- 1. 各章节字数 ---
    print(f"\n📏 章节字数分布:")
    for st, content in sections.items():
        label = SECTION_TITLES.get(st, st)
        wc = len(content)
        pct = wc / total_wc * 100 if total_wc else 0
        print(f"   {label}: {wc} 字 ({pct:.0f}%)")

    # --- 2. 跨章节段落相似度检测 ---
    print(f"\n🔍 跨章节重复检测:")
    all_paras: list[tuple[str, str]] = []
    for st, content in sections.items():
        paras = [p.strip() for p in content.split("\n\n") if len(p.strip()) >= 30]
        for p in paras:
            cleaned = re.sub(r'^#{1,4}\s+', '', p).strip()
            if len(cleaned) >= 30:
                all_paras.append((st, cleaned))

    dup_count = 0
    seen_pairs = set()
    for i in range(len(all_paras)):
        for j in range(i + 1, len(all_paras)):
            st_i, p_i = all_paras[i]
            st_j, p_j = all_paras[j]
            if st_i == st_j:
                continue
            pair_key = (min(i, j), max(i, j))
            if pair_key in seen_pairs:
                continue
            sim = paragraph_similarity(p_i, p_j)
            if sim >= 0.45:
                seen_pairs.add(pair_key)
                dup_count += 1
                label_i = SECTION_TITLES.get(st_i, st_i)
                label_j = SECTION_TITLES.get(st_j, st_j)
                print(f"   ⚠️ [{label_i}] vs [{label_j}] 相似度={sim:.2f}")
                print(f"      A: {p_i[:60]}…")
                print(f"      B: {p_j[:60]}…")

    if dup_count == 0:
        print("   ✅ 未检测到跨章节重复段落")
    else:
        print(f"   共 {dup_count} 对高相似段落")

    # --- 3. 章节内段落自重复 ---
    print(f"\n🔄 章节内重复检测:")
    intra_dup_total = 0
    for st, content in sections.items():
        paras = [p.strip() for p in content.split("\n\n") if len(p.strip()) >= 30]
        paras = [re.sub(r'^#{1,4}\s+', '', p).strip() for p in paras]
        paras = [p for p in paras if len(p) >= 30]
        intra_dups = 0
        for i in range(len(paras)):
            for j in range(i + 1, len(paras)):
                sim = paragraph_similarity(paras[i], paras[j])
                if sim >= 0.45:
                    intra_dups += 1
                    label = SECTION_TITLES.get(st, st)
                    print(f"   ⚠️ [{label}] 段落 {i+1} vs {j+1} 相似度={sim:.2f}")
                    print(f"      A: {paras[i][:60]}…")
                    print(f"      B: {paras[j][:60]}…")
        intra_dup_total += intra_dups
    if intra_dup_total == 0:
        print("   ✅ 未检测到章节内重复段落")

    # --- 4. 承诺覆盖率（引入段话题 → 后续交付）---
    print(f"\n📋 引入段承诺检测:")
    body = sections.get("body", "")
    body_paras = body.split("\n\n")
    intro_text = body_paras[0] if body_paras else ""
    rest_text = "\n\n".join(body_paras[1:]) + "\n\n" + "\n\n".join(
        v for k, v in sections.items() if k != "body"
    )

    topic_patterns = re.findall(r'[「「](.+?)[」」]|(?:聊聊|探讨|了解|揭秘|介绍)(.+?)(?:[，。！？,\n])', intro_text)
    promised = []
    for groups in topic_patterns:
        for g in groups:
            if g and len(g) >= 2:
                promised.append(g.strip())

    if promised:
        for p in promised:
            keywords = [p[i:i+2] for i in range(0, len(p) - 1, 2)][:3]
            found = sum(1 for kw in keywords if kw in rest_text)
            covered = found >= len(keywords) * 0.5
            status = "✅" if covered else "❌"
            print(f"   {status} 承诺话题「{p}」→ 关键词命中 {found}/{len(keywords)}")
    else:
        print("   ℹ️ 未检测到明确的话题承诺句式（可人工检查引入段）")
        if intro_text:
            print(f"   引入段前100字: {intro_text[:100]}…")

    # --- 5. 衔接质量（相邻章节首尾连贯性）---
    print(f"\n🔗 章节衔接检测:")
    section_order = ["body", "case", "qa", "summary"]
    present = [s for s in section_order if s in sections]
    for i in range(len(present) - 1):
        prev_content = sections[present[i]]
        next_content = sections[present[i + 1]]
        prev_ending = prev_content.strip().split("\n")[-1].strip()
        next_opening = ""
        for line in next_content.strip().split("\n"):
            stripped = line.strip()
            if stripped and not stripped.startswith("#"):
                next_opening = stripped
                break
        prev_label = SECTION_TITLES.get(present[i], present[i])
        next_label = SECTION_TITLES.get(present[i + 1], present[i + 1])
        print(f"   {prev_label} → {next_label}:")
        print(f"      尾句: {prev_ending[:80]}")
        print(f"      首句: {next_opening[:80]}")

    # --- 6. "承上启下"违规检测 ---
    print(f"\n🚫 回顾前文违规检测:")
    recall_patterns = [
        r"前文提到", r"上文中", r"正文中我们", r"我们在前面",
        r"前面提到", r"如前所述", r"前文所述", r"上一章",
        r"正文已经", r"前面我们",
    ]
    violations = 0
    for st, content in sections.items():
        if st == "body":
            continue
        for pat in recall_patterns:
            matches = re.findall(pat, content)
            if matches:
                violations += len(matches)
                label = SECTION_TITLES.get(st, st)
                print(f"   ⚠️ [{label}] 出现「{pat}」{len(matches)} 次")
    if violations == 0:
        print("   ✅ 无违规回顾前文表述")

    print("\n" + "=" * 60)
    print("📊 评测总结")
    print(f"   总字数偏差:        {deviation:.1f}%")
    print(f"   跨章节重复段落:    {dup_count} 对")
    print(f"   章节内重复段落:    {intra_dup_total} 对")
    print(f"   回顾前文违规:      {violations} 处")
    print("=" * 60)

    return {
        "total_wc": total_wc,
        "target_wc": target_wc,
        "deviation_pct": round(deviation, 1),
        "cross_section_dups": dup_count,
        "intra_section_dups": intra_dup_total,
        "recall_violations": violations,
    }


def main():
    parser = argparse.ArgumentParser(description="文章生成质量评测")
    parser.add_argument("--topic", default="肠道菌群与生物钟：揭秘代谢失衡的幕后推手")
    parser.add_argument("--word-count", type=int, default=2500)
    args = parser.parse_args()

    print(f"🎯 评测主题: {args.topic}")
    print(f"📏 目标字数: {args.word_count}")
    print()

    # Step 0: 认证
    print("🔐 认证...")
    ensure_auth()

    # Step 1: 创建文章
    print("📝 创建文章...")
    art = create_article(args.topic, args.word_count)
    article_id = art.get("id") or art.get("article", {}).get("id")
    print(f"   文章 ID: {article_id}")

    # Step 2: 生成全部章节
    print("\n🚀 开始生成...")
    t0 = time.time()
    sections = generate_all_sse(article_id)
    elapsed = time.time() - t0
    print(f"\n⏱️ 生成耗时: {elapsed:.1f}s")

    if not sections:
        print("❌ 未获取到任何章节内容")
        sys.exit(1)

    # Step 3: 保存原文
    output_path = f"backend/scripts/eval_output_{article_id}.md"
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(f"# {args.topic}\n\n")
        f.write(f"> 目标字数: {args.word_count} | 文章ID: {article_id}\n\n")
        for st in ["body", "case", "qa", "summary"]:
            if st in sections:
                label = SECTION_TITLES.get(st, st)
                f.write(f"\n---\n## [{label}]\n\n")
                f.write(sections[st])
                f.write("\n\n")
    print(f"\n💾 原文已保存: {output_path}")

    # Step 4: 评测
    metrics = evaluate(sections, args.word_count)

    # 保存评测结果
    metrics_path = f"backend/scripts/eval_metrics_{article_id}.json"
    metrics["topic"] = args.topic
    metrics["elapsed_s"] = round(elapsed, 1)
    metrics["article_id"] = article_id
    with open(metrics_path, "w", encoding="utf-8") as f:
        json.dump(metrics, f, ensure_ascii=False, indent=2)
    print(f"💾 指标已保存: {metrics_path}")


if __name__ == "__main__":
    main()
