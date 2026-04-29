"""
全流程计费测试脚本
从检索词智能设计 → 文献检索 → 文献筛选 → 文献分析 → 创建文章 → 全文生成 → AI优化 → 导出
观察每个计费点，统计总费用
"""
import asyncio
import httpx
import json
import time
import sys
from decimal import Decimal

BASE = "http://127.0.0.1:8765"
API = f"{BASE}/api/v1"

TEST_PHONE = "13800138099"
TEST_PASSWORD = "test123456"

import warnings
warnings.filterwarnings("ignore")

billing_log = []


def log_billing(step: str, cost: float, balance_before: float, balance_after: float, detail: str = ""):
    entry = {
        "step": step,
        "cost": cost,
        "balance_before": round(balance_before, 4),
        "balance_after": round(balance_after, 4),
        "actual_deduct": round(balance_before - balance_after, 4),
        "detail": detail,
    }
    billing_log.append(entry)
    status = "✅" if abs(balance_before - balance_after - cost) < 0.01 or cost == -1 else "⚠️"
    print(f"  {status} [{step}] 费用={cost}, 余额: {balance_before:.2f} → {balance_after:.2f} (实扣={balance_before - balance_after:.4f})")
    if detail:
        print(f"     详情: {detail}")


async def main():
    async with httpx.AsyncClient(base_url=API, timeout=120) as c:
        # ═══════════════════════════════════════════════════
        # STEP 0: 注册/登录获取 Token
        # ═══════════════════════════════════════════════════
        print("=" * 70)
        print("STEP 0: 登录/注册")
        print("=" * 70)

        # Try login first
        r = await c.post("/auth/login", json={"phone": TEST_PHONE, "password": TEST_PASSWORD})
        if r.status_code != 200:
            print(f"  登录失败({r.status_code})，尝试注册...")
            r = await c.post("/auth/register", json={
                "phone": TEST_PHONE,
                "password": TEST_PASSWORD,
                "display_name": "测试用户",
                "agreed_terms": True,
            })
            if r.status_code != 200:
                print(f"  ❌ 注册也失败: {r.status_code} {r.text}")
                return
            print(f"  ✅ 注册成功")
        else:
            print(f"  ✅ 登录成功")

        token_data = r.json()
        token = token_data.get("access_token") or token_data.get("token")
        if not token:
            print(f"  ❌ 无法获取 token: {token_data}")
            return

        headers = {"Authorization": f"Bearer {token}"}
        print(f"  Token: {token[:20]}...")

        # Get initial balance
        async def get_balance():
            br = await c.get("/credits/balance", headers=headers)
            if br.status_code == 200:
                d = br.json()
                return float(d.get("credits", 0)) + float(d.get("gift_credits", 0))
            return -1

        initial_balance = await get_balance()
        print(f"  初始余额: {initial_balance:.2f} 积分")

        if initial_balance < 10:
            print(f"  ⚠️  余额较低 ({initial_balance})，测试可能因余额不足而中断")

        # ═══════════════════════════════════════════════════
        # STEP 1: 检索词智能设计
        # ═══════════════════════════════════════════════════
        print("\n" + "=" * 70)
        print("STEP 1: 检索词智能设计 (design-keywords)")
        print("=" * 70)
        balance_before = await get_balance()
        r = await c.post("/literature/search/design-keywords", headers=headers, json={
            "description": "我想写一篇关于2型糖尿病患者运动干预对血糖控制效果的综述文章",
        })
        if r.status_code == 200:
            data = r.json()
            groups = data.get("groups", [])
            print(f"  ✅ 生成 {len(groups)} 组关键词:")
            for g in groups[:3]:
                print(f"     · {g}")
            if len(groups) > 3:
                print(f"     ... (共 {len(groups)} 组)")
            balance_after = await get_balance()
            log_billing("检索词智能设计", -1, balance_before, balance_after, f"预期 0.1 积分, 关键词组数={len(groups)}")
        else:
            print(f"  ❌ 失败: {r.status_code} {r.text[:200]}")
            balance_after = balance_before
            log_billing("检索词智能设计", 0, balance_before, balance_after, f"请求失败: {r.status_code}")

        # ═══════════════════════════════════════════════════
        # STEP 2: 文献检索 (免费)
        # ═══════════════════════════════════════════════════
        print("\n" + "=" * 70)
        print("STEP 2: 文献检索 (应免费，含 PubMed 查询优化)")
        print("=" * 70)
        balance_before = await get_balance()
        search_query = "type 2 diabetes exercise intervention blood glucose"
        r = await c.post("/literature/search", headers=headers, json={
            "query": search_query,
            "source": "pubmed",
            "max_results": 5,
        })
        paper_ids = []
        if r.status_code == 200:
            data = r.json()
            papers = data.get("papers", data.get("results", []))
            print(f"  ✅ 检索到 {len(papers)} 篇文献")
            for p in papers[:3]:
                pid = p.get("id") or p.get("pmid")
                title = (p.get("title") or "")[:60]
                print(f"     · [{pid}] {title}...")
                if pid:
                    paper_ids.append(pid)
            balance_after = await get_balance()
            log_billing("文献检索", 0, balance_before, balance_after, f"检索 {len(papers)} 篇 (应免费)")
        else:
            print(f"  ❌ 检索失败: {r.status_code} {r.text[:200]}")
            balance_after = balance_before
            log_billing("文献检索", 0, balance_before, balance_after, f"请求失败: {r.status_code}")

        # ═══════════════════════════════════════════════════
        # STEP 3: 文献 AI 智能筛选
        # ═══════════════════════════════════════════════════
        print("\n" + "=" * 70)
        print("STEP 3: 文献 AI 智能筛选 (literature filter)")
        print("=" * 70)
        balance_before = await get_balance()
        if paper_ids:
            r = await c.post("/literature/search/filter", headers=headers, json={
                "paper_ids": paper_ids[:5],
                "topic": "2型糖尿病运动干预对血糖控制效果",
                "top_k": 3,
            })
            if r.status_code == 200:
                fdata = r.json()
                kept = fdata.get("kept", fdata.get("results", []))
                print(f"  ✅ 筛选结果: 保留 {len(kept)} 篇")
                balance_after = await get_balance()
                log_billing("文献AI筛选", -1, balance_before, balance_after, f"筛选 {len(paper_ids)} → {len(kept)} 篇")
            else:
                print(f"  ❌ 筛选失败: {r.status_code} {r.text[:200]}")
                balance_after = balance_before
                log_billing("文献AI筛选", 0, balance_before, balance_after, f"请求失败: {r.status_code}")
        else:
            print("  ⏭️  跳过 (无文献)")
            balance_after = balance_before

        # ═══════════════════════════════════════════════════
        # STEP 4: 文献分析
        # ═══════════════════════════════════════════════════
        print("\n" + "=" * 70)
        print("STEP 4: 文献分析 (literature analyze)")
        print("=" * 70)
        balance_before = await get_balance()
        if paper_ids:
            analysis_text = ""
            try:
                async with c.stream(
                    "POST", "/literature/analyze",
                    headers=headers,
                    json={"paper_ids": paper_ids[:3], "topic_hint": "2型糖尿病运动干预"},
                ) as resp:
                    if resp.status_code == 200:
                        async for line in resp.aiter_lines():
                            if line.startswith("data: "):
                                try:
                                    evt = json.loads(line[6:])
                                    if evt.get("type") == "chunk":
                                        analysis_text += evt.get("text", "")
                                    elif evt.get("type") == "done":
                                        analysis_text = evt.get("full_text", analysis_text)
                                except:
                                    pass
                        print(f"  ✅ 分析完成，输出 {len(analysis_text)} 字符")
                        print(f"     内容预览: {analysis_text[:100]}...")
                    else:
                        body = await resp.aread()
                        print(f"  ❌ 分析失败: {resp.status_code} {body.decode()[:200]}")
            except Exception as e:
                print(f"  ❌ 分析异常: {type(e).__name__}: {e}")
            balance_after = await get_balance()
            log_billing("文献分析", -1, balance_before, balance_after, f"输出 {len(analysis_text)} 字符")
        else:
            print("  ⏭️  跳过 (无文献)")
            balance_after = balance_before

        # ═══════════════════════════════════════════════════
        # STEP 5: 创建文章
        # ═══════════════════════════════════════════════════
        print("\n" + "=" * 70)
        print("STEP 5: 创建文章 (应免费)")
        print("=" * 70)
        balance_before = await get_balance()
        r = await c.post("/medcomm/articles", headers=headers, json={
            "title": "2型糖尿病患者运动干预对血糖控制效果的综述",
            "article_type": "review",
            "target_journal": "中华糖尿病杂志",
        })
        article_id = None
        section_ids = []
        if r.status_code == 200:
            adata = r.json()
            article_id = adata.get("id")
            print(f"  ✅ 文章创建成功: id={article_id}")

            # Get sections
            r2 = await c.get(f"/medcomm/articles/{article_id}", headers=headers)
            if r2.status_code == 200:
                art = r2.json()
                sections = art.get("sections", [])
                for sec in sections:
                    section_ids.append(sec["id"])
                    print(f"     · 章节 {sec['id']}: {sec.get('title', sec.get('name', 'N/A'))}")
            balance_after = await get_balance()
            log_billing("创建文章", 0, balance_before, balance_after, f"article_id={article_id}, sections={len(section_ids)}")
        else:
            print(f"  ❌ 创建失败: {r.status_code} {r.text[:200]}")
            balance_after = balance_before
            log_billing("创建文章", 0, balance_before, balance_after, f"请求失败: {r.status_code}")

        # ═══════════════════════════════════════════════════
        # STEP 6: 全文生成 (generate-all)
        # ═══════════════════════════════════════════════════
        print("\n" + "=" * 70)
        print("STEP 6: 全文生成 (generate-all)")
        print("=" * 70)
        balance_before = await get_balance()
        total_gen_chars = 0
        if article_id:
            try:
                async with c.stream(
                    "POST", f"/medcomm/articles/{article_id}/generate-all",
                    headers=headers,
                    json={},
                    timeout=300,
                ) as resp:
                    if resp.status_code == 200:
                        section_results = {}
                        async for line in resp.aiter_lines():
                            if line.startswith("data: "):
                                try:
                                    evt = json.loads(line[6:])
                                    etype = evt.get("type", "")
                                    sid = evt.get("section_id")
                                    if etype == "section_start":
                                        section_results[sid] = {"chars": 0, "title": evt.get("title", "")}
                                    elif etype == "chunk" and sid in section_results:
                                        section_results[sid]["chars"] += len(evt.get("text", ""))
                                    elif etype == "section_done" and sid in section_results:
                                        section_results[sid]["chars"] = evt.get("char_count", section_results[sid]["chars"])
                                    elif etype == "all_done":
                                        pass
                                except:
                                    pass
                        for sid, info in section_results.items():
                            total_gen_chars += info["chars"]
                            print(f"     · 章节 {sid} ({info.get('title','')[:20]}): {info['chars']} 字符")
                        print(f"  ✅ 全文生成完成，总计 {total_gen_chars} 字符")
                    else:
                        body = await resp.aread()
                        print(f"  ❌ 生成失败: {resp.status_code} {body.decode()[:200]}")
            except Exception as e:
                print(f"  ❌ 生成异常: {type(e).__name__}: {e}")
            balance_after = await get_balance()
            log_billing("全文生成", -1, balance_before, balance_after, f"总输出 {total_gen_chars} 字符")
        else:
            print("  ⏭️  跳过 (无文章)")
            balance_after = balance_before

        # ═══════════════════════════════════════════════════
        # STEP 7: AI 写作辅助 (ai-assist)
        # ═══════════════════════════════════════════════════
        print("\n" + "=" * 70)
        print("STEP 7: AI 写作辅助 (ai-assist)")
        print("=" * 70)
        balance_before = await get_balance()
        ai_assist_output = ""
        try:
            async with c.stream(
                "POST", "/medcomm/ai-assist",
                headers=headers,
            json={
                "selected_text": "2型糖尿病是一种以胰岛素抵抗和胰岛β细胞功能障碍为特征的代谢性疾病。",
                "action": "continue",
                "context_before": "运动干预综述文章的引言部分",
            },
                timeout=120,
            ) as resp:
                if resp.status_code == 200:
                    async for line in resp.aiter_lines():
                        if line.startswith("data: "):
                            try:
                                evt = json.loads(line[6:])
                                if evt.get("type") == "chunk":
                                    ai_assist_output += evt.get("text", "")
                                elif evt.get("type") == "done":
                                    ai_assist_output = evt.get("full_text", ai_assist_output)
                            except:
                                pass
                    print(f"  ✅ AI写作辅助完成，输出 {len(ai_assist_output)} 字符")
                    print(f"     预览: {ai_assist_output[:100]}...")
                else:
                    body = await resp.aread()
                    print(f"  ❌ 失败: {resp.status_code} {body.decode()[:200]}")
        except Exception as e:
            print(f"  ❌ 异常: {type(e).__name__}: {e}")
        balance_after = await get_balance()
        log_billing("AI写作辅助", -1, balance_before, balance_after, f"输出 {len(ai_assist_output)} 字符")

        # ═══════════════════════════════════════════════════
        # STEP 8: AI 翻译
        # ═══════════════════════════════════════════════════
        print("\n" + "=" * 70)
        print("STEP 8: AI 翻译")
        print("=" * 70)
        balance_before = await get_balance()
        translate_text = "2型糖尿病是全球最常见的慢性代谢性疾病之一，运动干预已被证明是控制血糖的有效手段。"
        r = await c.post("/translate", headers=headers, json={
            "text": translate_text,
            "target_lang": "en",
        })
        if r.status_code == 200:
            tdata = r.json()
            translated = tdata.get("text", "")
            cost_reported = tdata.get("cost", 0)
            print(f"  ✅ 翻译完成:")
            print(f"     输入: {len(translate_text)} 字符")
            print(f"     输出: {len(translated)} 字符")
            print(f"     API 返回费用: {cost_reported}")
            print(f"     译文: {translated[:100]}...")
            balance_after = await get_balance()
            log_billing("AI翻译", cost_reported, balance_before, balance_after, f"入={len(translate_text)} 出={len(translated)} 字符")
        else:
            print(f"  ❌ 翻译失败: {r.status_code} {r.text[:200]}")
            balance_after = balance_before
            log_billing("AI翻译", 0, balance_before, balance_after, f"请求失败: {r.status_code}")

        # ═══════════════════════════════════════════════════
        # STEP 9: AI 润色/优化 (polish)
        # ═══════════════════════════════════════════════════
        print("\n" + "=" * 70)
        print("STEP 9: AI 润色/优化 (polish)")
        print("=" * 70)
        balance_before = await get_balance()
        if article_id and section_ids:
            target_section_id = section_ids[0]

            # First create a polish session
            r = await c.post("/polish/sessions", headers=headers, json={
                "article_id": article_id,
                "section_id": target_section_id,
                "polish_type": "language",
            })
            if r.status_code == 200:
                pdata = r.json()
                polish_session_id = pdata.get("session_id", pdata.get("id"))
                print(f"  润色会话创建: session_id={polish_session_id}")

                # Run polish
                r2 = await c.post("/polish/run", headers=headers, json={
                    "session_id": polish_session_id,
                })
                if r2.status_code == 200:
                    pr = r2.json()
                    changes = pr.get("changes_count", 0)
                    pcost = pr.get("cost", 0)
                    print(f"  ✅ 润色完成: {changes} 处修改, API费用={pcost}")
                    balance_after = await get_balance()
                    log_billing("AI润色", pcost, balance_before, balance_after, f"修改 {changes} 处")
                else:
                    print(f"  ❌ 润色运行失败: {r2.status_code} {r2.text[:200]}")
                    balance_after = await get_balance()
                    log_billing("AI润色", 0, balance_before, balance_after, f"运行失败: {r2.status_code}")
            else:
                print(f"  ❌ 润色会话创建失败: {r.status_code} {r.text[:200]}")
                balance_after = balance_before
                log_billing("AI润色", 0, balance_before, balance_after, f"会话创建失败: {r.status_code}")
        else:
            print("  ⏭️  跳过 (无文章/章节)")
            balance_after = balance_before

        # ═══════════════════════════════════════════════════
        # STEP 10: 导出
        # ═══════════════════════════════════════════════════
        print("\n" + "=" * 70)
        print("STEP 10: 无水印导出 (export)")
        print("=" * 70)
        balance_before = await get_balance()
        if article_id:
            r = await c.get(
                f"/medcomm/articles/{article_id}/export",
                headers=headers,
                params={"format": "docx", "watermark": "false"},
            )
            if r.status_code == 200:
                content_len = len(r.content)
                print(f"  ✅ 导出成功: {content_len} bytes")
                balance_after = await get_balance()
                log_billing("无水印导出", 3.0, balance_before, balance_after, f"预期固定 3 积分")
            else:
                print(f"  ❌ 导出失败: {r.status_code} {r.text[:200] if r.headers.get('content-type','').startswith('application/json') else '(binary)'}")
                balance_after = await get_balance()
                log_billing("无水印导出", 0, balance_before, balance_after, f"请求失败: {r.status_code}")
        else:
            print("  ⏭️  跳过 (无文章)")
            balance_after = balance_before

        # ═══════════════════════════════════════════════════
        # STEP 11: 配图 AI 提示词
        # ═══════════════════════════════════════════════════
        print("\n" + "=" * 70)
        print("STEP 11: 配图 AI 提示词 (medpic/ai-prompt)")
        print("=" * 70)
        balance_before = await get_balance()
        r = await c.post("/medpic/ai-prompt", headers=headers, json={
            "description": "糖尿病患者在公园里进行有氧运动的医学插图",
            "specialty": "内分泌科",
            "stream": False,
        })
        if r.status_code == 200:
            pdata = r.json()
            print(f"  ✅ 提示词生成成功")
            if isinstance(pdata, dict):
                for k in ["positive", "negative"]:
                    v = pdata.get(k, "")
                    if v:
                        print(f"     {k}: {str(v)[:80]}...")
            balance_after = await get_balance()
            log_billing("配图AI提示词", -1, balance_before, balance_after, f"预期 0.2 积分")
        else:
            print(f"  ❌ 失败: {r.status_code} {r.text[:200]}")
            balance_after = balance_before
            log_billing("配图AI提示词", 0, balance_before, balance_after, f"请求失败: {r.status_code}")

        # ═══════════════════════════════════════════════════
        # 最终报告
        # ═══════════════════════════════════════════════════
        final_balance = await get_balance()
        total_spent = initial_balance - final_balance

        print("\n")
        print("╔" + "═" * 68 + "╗")
        print("║" + " 全流程计费测试报告 ".center(60) + "║")
        print("╠" + "═" * 68 + "╣")
        print(f"║  初始余额: {initial_balance:>10.2f} 积分" + " " * 36 + "║")
        print(f"║  最终余额: {final_balance:>10.2f} 积分" + " " * 36 + "║")
        print(f"║  总消耗:   {total_spent:>10.4f} 积分" + " " * 34 + "║")
        print("╠" + "═" * 68 + "╣")
        print("║  计费明细:" + " " * 57 + "║")
        print("╟" + "─" * 68 + "╢")

        for entry in billing_log:
            step = entry["step"]
            actual = entry["actual_deduct"]
            status = "✅" if actual >= 0 else "⚠️"
            line = f"║  {status} {step:<18s}  实扣: {actual:>8.4f}  (余额: {entry['balance_before']:.2f}→{entry['balance_after']:.2f})"
            pad = 69 - len(line.encode('utf-8')) + len(line)
            print(line + " " * max(0, pad - len(line)) + "║")

        print("╠" + "═" * 68 + "╣")

        billed_steps = [e for e in billing_log if e["actual_deduct"] > 0.001]
        free_steps = [e for e in billing_log if abs(e["actual_deduct"]) < 0.001]

        print("║  📊 分类统计:" + " " * 54 + "║")
        print(f"║    付费功能: {len(billed_steps)} 个" + " " * 50 + "║")
        for e in billed_steps:
            print(f"║      · {e['step']}: {e['actual_deduct']:.4f} 积分" + " " * 30 + "║")
        print(f"║    免费功能: {len(free_steps)} 个" + " " * 50 + "║")
        for e in free_steps:
            print(f"║      · {e['step']}" + " " * 45 + "║")

        print("╠" + "═" * 68 + "╣")
        print(f"║  💰 生成一篇完整文章的预估总费用: {total_spent:.4f} 积分" + " " * 20 + "║")
        print("╚" + "═" * 68 + "╝")

        # Print raw billing log as JSON for detailed analysis
        print("\n\n--- 原始计费日志 (JSON) ---")
        print(json.dumps(billing_log, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
