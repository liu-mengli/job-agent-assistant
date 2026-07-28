"""
KB RAG 评估脚本
===============
对 10 道测试题逐一执行完整的检索管线（Query改写 → Dense+BM25 → RRF → Rerank → 阈值过滤）
+ LLM 回答生成，所有结果保存到 eval_results.json 供后续标注分析。
"""
import asyncio
import json
import selectors
import time
from pathlib import Path

import numpy as np

from config import settings

# --- 10 道测试题 ---
QUESTIONS = [
    "Run Page有哪些执行模式和执行状态？",
    "Offset Setting的操作步骤是什么？",
    "如何进行Auto Alignment自动校准？",
    "操作3200设备时有哪些安全注意事项？",
    "User Page和Engineer Page的Yield Control良率控制有什么区别？",
    "Timer Setting怎么设置，有哪些参数？",
    "IO Monitor和Motor Monitor分别有什么功能？",
    "Tray File料盘资料和Tray Map有什么不同？",
    "Cobra温度控制怎么设定？",
    "Event Log事件记录在哪几个页面可以看到，有什么不同？",
]

# --- RRF 融合（与 kb_graph.py 完全一致）---
def _rrf_fusion(
    dense_results: list[dict],
    bm25_results: list[dict],
    k: int = 60,
) -> list[dict]:
    scores: dict[str, float] = {}
    merged: dict[str, dict] = {}
    for rank, r in enumerate(dense_results):
        key = r["content"]
        scores[key] = scores.get(key, 0) + 1.0 / (k + rank + 1)
        merged[key] = r
    for rank, r in enumerate(bm25_results):
        key = r["content"]
        scores[key] = scores.get(key, 0) + 1.0 / (k + rank + 1)
        if key not in merged:
            merged[key] = r
    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    result: list[dict] = []
    for key, rrf_score in ranked:
        entry = dict(merged[key])
        entry["rrf_score"] = rrf_score
        result.append(entry)
    return result


async def run_evaluation(questions: list[str]) -> list[dict]:
    """对每道题逐一执行检索管线 + LLM 回答，返回完整结果列表"""
    from psycopg_pool import AsyncConnectionPool
    from api.rag.kb_embedder import kb_embed
    from api.rag.kb_store import kb_search, kb_bm25_search
    from api.rag.kb_reranker import kb_rerank
    from api.agent.kb_graph import _rewrite_queries, KB_ADVISOR_PROMPT, kb_llm
    from api.agent.graph import sanitize

    pool = AsyncConnectionPool(settings.PG_URL, min_size=1, max_size=3, open=False)
    await pool.open()

    results: list[dict] = []

    try:
        for qi, question in enumerate(questions):
            print(f"\n{'='*60}")
            print(f"[{qi+1}/10] {question}")
            print(f"{'='*60}")

            t0 = time.monotonic()

            # ---- 1. Query 改写 ----
            rewritten = await _rewrite_queries(question)
            search_queries = rewritten if rewritten else [question]
            print(f"  改写: {search_queries}")

            # ---- 2. 多路混合检索 ----
            dense_total = 0
            bm25_total = 0
            candidates: dict[str, dict] = {}

            for q in search_queries:
                q_emb = kb_embed([q])[0]
                dense_results = await kb_search(pool, q_emb)
                bm25_results = await kb_bm25_search(pool, q)
                dense_total += len(dense_results)
                bm25_total += len(bm25_results)
                fused = _rrf_fusion(dense_results, bm25_results)
                for r in fused:
                    key = r["content"]
                    if key not in candidates or r["rrf_score"] > candidates[key].get("rrf_score", 0):
                        candidates[key] = r

            print(f"  Dense={dense_total}  BM25={bm25_total}  融合去重={len(candidates)}")

            # ---- 3. RRF top-N 候选 ----
            hybrid_top = sorted(
                candidates.values(), key=lambda r: r["rrf_score"], reverse=True
            )[:settings.KB_RERANK_CANDIDATES]

            # ---- 4. Cross-Encoder 精排 ----
            if hybrid_top:
                reranked = kb_rerank(question, hybrid_top, top_k=settings.KB_RETRIEVAL_TOP_K)
            else:
                reranked = []

            # ---- 5. 阈值过滤 ----
            passed = [r for r in reranked if r["rerank_score"] >= settings.KB_RERANK_THRESHOLD]
            all_filtered = len(reranked) > 0 and len(passed) == 0
            if not passed and reranked:
                passed = reranked[:1]  # fallback top-1，防止口语化等场景零结果
                all_filtered = True

            # ---- 6. LLM 相关性二次过滤 ----
            if len(passed) > 1:
                from api.agent.kb_graph import _llm_relevance_filter
                passed_before = len(passed)
                passed = await _llm_relevance_filter(question, passed)
                all_filtered = all_filtered or (passed_before > 0 and len(passed) == 0)

            retrieval_ms = int((time.monotonic() - t0) * 1000)
            print(f"  精排={len(reranked)}  通过={len(passed)}  耗时={retrieval_ms}ms")

            # ---- 格式化检索结果 ----
            passed_detail = []
            for rank, r in enumerate(passed):
                passed_detail.append({
                    "rank": rank + 1,
                    "section": r.get("section", ""),
                    "document_name": r.get("document_name", ""),
                    "dense_similarity": round(1 - r.get("distance", 1), 4),
                    "bm25_score": round(r.get("bm25_score", 0), 4) if "bm25_score" in r else None,
                    "rrf_score": round(r.get("rrf_score", 0), 6),
                    "rerank_score": round(r.get("rerank_score", 0), 4),
                    "content": r["content"][:500],
                    "content_full": r["content"],
                })

            # ---- 6. LLM 回答生成 ----
            answer_text = ""
            answer_ms = 0
            if passed:
                # 用检索结果构造 ToolMessage 风格上下文
                ctx_parts = []
                for r in passed:
                    src = (
                        f"【来源：《{r['document_name']}》{r['section']}章节】\n"
                        f"{r['content']}"
                    )
                    ctx_parts.append(src)
                context = "\n\n---\n\n".join(ctx_parts)

                system = KB_ADVISOR_PROMPT
                from langchain_core.messages import SystemMessage, HumanMessage

                user_msg = (
                    f"以下是根据你的问题检索到的知识库内容：\n\n"
                    f"{context}\n\n"
                    f"---\n"
                    f"请基于以上检索内容回答用户问题。\n"
                    f"用户问题：{question}"
                )

                t_llm = time.monotonic()
                try:
                    full = None
                    async for chunk in kb_llm.astream([
                        SystemMessage(content=system),
                        HumanMessage(content=user_msg),
                    ]):
                        full = chunk if full is None else full + chunk
                    answer_text = sanitize(full.content) if full and full.content else ""
                except Exception as e:
                    answer_text = f"[LLM 调用失败: {e}]"
                answer_ms = int((time.monotonic() - t_llm) * 1000)
                print(f"  回答={len(answer_text)}字  耗时={answer_ms}ms")
            else:
                answer_text = "知识库中未找到与您问题相关的内容。"

            results.append({
                "index": qi,
                "question": question,
                "retrieval": {
                    "rewritten_queries": search_queries,
                    "dense_hits": dense_total,
                    "bm25_hits": bm25_total,
                    "fused_candidates": len(candidates),
                    "reranked_candidates": len(reranked),
                    "passed_candidates": len(passed),
                    "all_filtered": all_filtered,
                    "latency_ms": retrieval_ms,
                    "passed": passed_detail,
                },
                "answer": {
                    "text": answer_text,
                    "latency_ms": answer_ms,
                },
            })

    finally:
        await pool.close()

    return results


def main():
    import sys
    questions = list(QUESTIONS)
    out_name = "eval_results.json"

    # 支持从 JSON 文件加载自定义问题
    for arg in sys.argv[1:]:
        if arg.startswith("--questions="):
            qpath = arg.split("=", 1)[1]
            with open(qpath, encoding="utf-8") as f:
                questions = json.load(f)
        elif arg.startswith("--out="):
            out_name = arg.split("=", 1)[1]

    print("=" * 60)
    print("KB RAG 评估开始")
    print(f"测试题数: {len(questions)}")
    print(f"Dense阈值: {settings.KB_RETRIEVAL_THRESHOLD}")
    print(f"Rerank阈值: {settings.KB_RERANK_THRESHOLD}")
    print(f"精排候选数: {settings.KB_RERANK_CANDIDATES}")
    print("=" * 60)

    result = asyncio.run(
        run_evaluation(questions),
        loop_factory=lambda: asyncio.SelectorEventLoop(selectors.SelectSelector()),
    )

    out_path = Path(__file__).parent.parent.parent / out_name
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"\n结果已保存到: {out_path}")
    print(f"共 {len(result)} 条记录")


if __name__ == "__main__":
    main()
