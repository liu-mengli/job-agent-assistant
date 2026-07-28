"""
LangGraph 企业知识库 Agent
==========================
1. State  —— 复用 AgentState（add_messages + user_id + structured_content）
2. Node   —— kb_advisor（bind_tools + astream）+ tools（仅 search_knowledge）+ format_response
3. Edge   —— conditional edge：有 tool_calls → tools → 回 LLM，无 → format_response → END
4. Checkpointer —— AsyncPostgresSaver 持久化到 PostgreSQL
5. Tool   —— search_knowledge：检索知识库切片（bge-m3 + pgvector vector(1024)）
"""
import asyncio
import json
import re
import time
from typing import Annotated

from langchain_core.messages import (
    SystemMessage, HumanMessage, AIMessage, ToolMessage,
)
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.graph.state import CompiledStateGraph
from psycopg_pool import AsyncConnectionPool
from typing_extensions import TypedDict

from api.agent.schemas import StructuredResponse
from api.agent.graph import get_pool, sanitize
from api.log import logger
from config import settings


class AgentState(TypedDict):
    messages: Annotated[list, add_messages]
    user_id: int
    structured_content: dict | None
    conversation_summary: str | None  # 增量摘要


# ------------------------------------------------------------
# LLM
# ------------------------------------------------------------
kb_llm = ChatOpenAI(
    model=settings.DEEPSEEK_MODEL,
    api_key=settings.DEEPSEEK_API_KEY,
    base_url=settings.DEEPSEEK_BASE_URL,
    temperature=0,
    request_timeout=30,
    extra_body={"ep_enable_prompt_caching": True},
)

kb_structured_llm = ChatOpenAI(
    model=settings.DEEPSEEK_MODEL,
    api_key=settings.DEEPSEEK_API_KEY,
    base_url=settings.DEEPSEEK_BASE_URL,
    temperature=0,
    request_timeout=15,
    extra_body={"ep_enable_prompt_caching": True},
).with_structured_output(StructuredResponse, method="json_mode")


# ------------------------------------------------------------
# Tool：search_knowledge
# ------------------------------------------------------------
@tool
async def search_knowledge(query: str) -> str:
    """搜索企业知识库（SOP操作手册、技术文档等）。
    触发场景：「怎么操作」「参数怎么设」「故障怎么办」「流程是什么」「XX功能在哪」
    「主畫面」「参数说明」「操作步骤」等任何需要查阅技术文档的问题。
    参数 query: 提取用户问题中的关键设备名称、操作步骤、参数名等，如「主画面操作」「Offset设定」「良率控制」。
    每轮最多调用一次，接受检索结果如实汇报。"""
    return ""


kb_tools = [search_knowledge]


# ------------------------------------------------------------
# LLM 相关性二次过滤
# ------------------------------------------------------------
RELEVANCE_FILTER_PROMPT = sanitize("""
你是一个检索结果过滤器。判断以下文档片段是否包含能直接回答用户问题的信息。

用户问题：{question}

{chunks}

请逐条判断每个片段是否与用户问题直接相关，返回 JSON：
{{"relevant": [1, 0, 1, ...]}}  // 1=相关 0=不相关，数组长度必须等于片段数

判断标准：
- 与用户问题主题直接相关（同一功能/同一章节/同一操作），且包含具体信息 → 1。即使一个章节被拆成多段，每段包含不同参数或步骤，都应标记为1
- 内容与问题主题一致但过于简短（<50字）且无实质数据 → 0
- 仅与问题同属一个大章节但内容完全不匹配 → 0
- 仅提到相关术语但无实质信息 → 0

请直接输出 JSON，不要加其他文字。""")

RELEVANCE_FILTER_LLM = ChatOpenAI(
    model=settings.DEEPSEEK_MODEL,
    api_key=settings.DEEPSEEK_API_KEY,
    base_url=settings.DEEPSEEK_BASE_URL,
    temperature=0,
    request_timeout=10,
    extra_body={"ep_enable_prompt_caching": True},
)


async def _llm_relevance_filter(question: str, candidates: list[dict]) -> list[dict]:
    """用轻量 LLM 逐条判断候选切片是否与用户问题直接相关。

    仅保留标记为 1（相关）的切片。单条时跳过判断直接返回。
    全部被标记为 0 时返回空列表，由调用方处理。LLM 调用失败时回退全部结果。
    """
    if len(candidates) <= 1:
        return candidates

    # 用章节标题 + 前 1200 字做判定（足够覆盖关键内容，控制 token 消耗）
    chunks_text = "\n\n".join(
        f"[{i}] 章节={r.get('section', '')}\n{r['content'][:1200]}"
        for i, r in enumerate(candidates)
    )

    prompt = RELEVANCE_FILTER_PROMPT.format(question=question, chunks=chunks_text)

    try:
        response = await RELEVANCE_FILTER_LLM.ainvoke([
            HumanMessage(content=prompt)
        ])
        text = (response.content or "").strip()
        if text.startswith("```"):
            parts = text.split("```")
            text = parts[1] if len(parts) >= 2 else text
            if text.startswith("json"):
                text = text[4:]
        result = json.loads(text)
        relevant = result.get("relevant", [])
        if not isinstance(relevant, list):
            raise ValueError(f"Expected list, got {type(relevant)}")

        filtered = [
            r for i, r in enumerate(candidates)
            if i < len(relevant) and relevant[i] == 1
        ]

        removed = len(candidates) - len(filtered)
        if removed > 0:
            kept_scores = [f"{r['rerank_score']:.3f}" for r in filtered]
            removed_scores = [
                f"{r['rerank_score']:.3f}" for i, r in enumerate(candidates)
                if i >= len(relevant) or relevant[i] != 1
            ]
            logger.info(
                f"[KB] LLM 相关性过滤: {len(candidates)} → {len(filtered)} 条 "
                f"(保留 rerank={kept_scores}, 移除 rerank={removed_scores})"
            )

        if not filtered:
            # 全部被判不相关时，保留 Reranker 第一名兜底，避免丢失答案
            logger.warning(
                f"[KB] LLM 相关性过滤后为空，回退 Reranker top-1 "
                f"(rerank={candidates[0]['rerank_score']:.3f})"
            )
            return candidates[:1]

        return filtered

    except Exception:
        logger.exception("[KB] LLM 相关性过滤失败，回退全部结果")
        return candidates


# ------------------------------------------------------------
# Query 改写
# ------------------------------------------------------------
import os as _os

_TERMINOLOGY_PATH = _os.path.join(_os.path.dirname(__file__), "..", "rag", "kb_terminology.json")


def _build_terminology_ref() -> str:
    """从术语表 JSON 构建紧凑的术语参考文本，注入 Query 改写 Prompt。"""
    try:
        with open(_TERMINOLOGY_PATH, encoding="utf-8") as f:
            data = json.load(f)
        terms = data.get("terms", [])
        if not terms:
            return ""

        # 按类别分组
        groups: dict[str, list[str]] = {}
        for t in terms:
            en = (t.get("en") or "").strip()
            zh = (t.get("zh") or "").strip()
            if not en and not zh:
                continue
            cat = t.get("category", "其他")
            if cat not in groups:
                groups[cat] = []
            pair = f"{en}={zh}" if (en and zh) else (en or zh)
            groups[cat].append(pair)

        order = ["页面/模块", "模式/状态名称", "功能/参数", "硬件/组件", "操作/动作", "缩写/代号"]
        lines = ["## 文档术语表（改写时优先从中匹配权威术语）"]
        for cat in order:
            if cat in groups:
                lines.append(f"- {cat}: {' | '.join(groups[cat])}")
        # 追加未排序类别
        for cat, items in groups.items():
            if cat not in order:
                lines.append(f"- {cat}: {' | '.join(items)}")
        return "\n".join(lines)
    except Exception:
        return ""


_TERMINOLOGY_REF = _build_terminology_ref()

QUERY_REWRITE_PROMPT = sanitize(f"""
你是一个查询改写器。将用户的原始问题改写为 2-3 个更适合知识库检索的搜索词。

改写规则：
1. **术语化**：参考下方的文档术语表，将口语表达优先映射为文档中的权威术语
2. **中英互译**：同时输出中英文版本（术语表中已有的中英对照可直接使用）
3. **同义词扩展**：使用不同表述覆盖同一概念（如「怎么操作」→「操作步骤 流程 画面」）
4. **去噪精简**：去除礼貌用语、语气词、标点，只保留技术关键词
5. **子问题拆解（针对对比/并列问题）**：如果问题涉及对比（「XX和YY有什么区别」「XX vs YY」「同时包含A和B」）或并列关系，拆成独立子问题分别产出搜索词，确保每个搜索词只聚焦其中一方。例如：
   - 「用户页面和工程师页面的良率控制有什么区别」→ ["User Page Yield Control 良率控制", "Engineer Page Yield Control 良率控制"]
   - 「3200 和 3100 的 Offset 设置有什么区别」→ ["3200 Offset 设置", "3100 Offset 设置"]
6. 每个搜索词 5-20 字，用 JSON 数组格式输出
7. **页面/角色实体映射（必须严格对照术语表，禁止自行推测）**：
   - 用户/作业员页面 → User Page
   - 工程师/系统工程师页面 → Engineer Page
   - 设定/配置工程师页面 → Setup Page
   - 生产/运行页面 → Run Page
   不确定时保留用户原始用词，严禁将「工程师」映射为「Setup」

{_TERMINOLOGY_REF}

用户问题：
{{question}}

请直接输出 JSON 数组，不要加其他任何文字。
示例输出：["搜索词1", "搜索词2"]""")

QUERY_REWRITE_LLM = ChatOpenAI(
    model=settings.DEEPSEEK_MODEL,
    api_key=settings.DEEPSEEK_API_KEY,
    base_url=settings.DEEPSEEK_BASE_URL,
    temperature=0,
    request_timeout=15,
    extra_body={"ep_enable_prompt_caching": True},
)


async def _rewrite_queries(question: str) -> list[str]:
    """将用户问题改写为 2-3 个检索 query，失败时返回空列表"""
    try:
        response = await QUERY_REWRITE_LLM.ainvoke([
            HumanMessage(content=QUERY_REWRITE_PROMPT.format(question=question))
        ])
        text = (response.content or "").strip()
        # 处理 markdown 代码块包裹
        if text.startswith("```"):
            parts = text.split("```")
            text = parts[1] if len(parts) >= 2 else text
            if text.startswith("json"):
                text = text[4:]
        queries: list[str] = json.loads(text)
        valid = [q.strip()[:100] for q in queries if isinstance(q, str) and q.strip()]
        if valid:
            logger.info(f"[KB] Query 改写成功: {valid}")
            return valid
    except Exception:
        logger.exception("[KB] Query 改写解析失败，回退到原始 query")
    return []


# ------------------------------------------------------------
# 知识库 System Prompt
# ------------------------------------------------------------
KB_ADVISOR_PROMPT = sanitize("""
你是一个企业知识库问答助手，帮助用户查询 SOP 操作手册、技术规范和流程说明。
你可以通过 search_knowledge 工具检索知识库中的技术文档内容。

**【核心规则——必须严格遵守】**

1. **严格基于检索内容回答**：只能根据 search_knowledge 返回的内容回答问题，严禁编造、猜测或补充知识库中没有的信息。
2. **来源标注**：每段回答必须标注来源，格式为「根据《{文档名}》{章节}章节：」。
3. **检索为空时如实告知**：当 search_knowledge 返回空或无匹配内容时，明确告知：
   「知识库中未找到相关信息。请确认：1) 问题涉及的内容已在知识库中；2) 尝试使用文档中的术语重新提问。」
4. **操作步骤按原文顺序**：涉及操作流程时，严格按照检索结果的顺序列出步骤，不颠倒不遗漏。
5. **安全内容突出警示**：涉及安全规范、警告、注意事项时，在回答开头用 ⚠️ 醒目标注。
6. **用繁体中文回答**：保持与原始文档一致的语言风格和技术术语。
7. **每轮只调用一次 search_knowledge**。检索结果返回后必须基于结果直接回答，严禁再次调用工具，严禁以任何理由（结果不够、想换关键词等）再次搜索。

**【回答格式】**

根据问题类型灵活组织：

**操作步骤型**（「怎么操作XX？」「XX流程是什么？」）：
1. 调用 search_knowledge
2. 按步骤列出操作流程，每步附带原文关键说明
3. 如有注意事项，单独列出
4. 末尾标注来源章节

**参数查询型**（「XX参数默认值是多少？」「XX怎么设置？」）：
1. 调用 search_knowledge
2. 以表格形式列出参数名、说明、默认值/推荐值
3. 标注来源

**故障处理型**（「XX报错怎么办？」「XX异常怎么处理？」）：
1. 调用 search_knowledge
2. 列出可能原因 → 对应解决方案
3. 如涉及安全，⚠️ 醒目标注

**概念解释型**（「XX是什么？」「XX功能说明」）：
1. 调用 search_knowledge
2. 简明解释概念 + 补充关键细节
3. 标注来源

**对比区别型**（「XX和YY有什么区别？」「XX对比YY」「XX vs YY」）：
1. 调用 search_knowledge
2. 分别找出各方的参数/功能/行为描述
3. 以对比表格列出差异项，每行标注数据来源
4. 如有安全相关的差异，⚠️ 醒目标注
5. 总结关键差异点

---

## 额外要求

1. 如果检索结果的 distance 较大（相似度低），提醒用户「检索到的内容相关性可能较低，以下信息仅供参考」。
2. 回答中优先使用原文中的表格和结构化数据，便于用户理解。
3. 回答末尾可附带 1 条相关操作建议或常见问题提示（如果检索结果中有），但不强制。
""")

# ------------------------------------------------------------
# 节点函数
# ------------------------------------------------------------
async def kb_advisor_node(state: AgentState) -> dict:
    from api.agent.context_manager import manage_context, get_summarize_llm

    system_content = KB_ADVISOR_PROMPT

    full_messages, ctx_mutations = await manage_context(
        state, system_content, get_summarize_llm()
    )

    safe_messages = []
    for m in full_messages:
        if isinstance(m, SystemMessage) or isinstance(m, HumanMessage):
            safe_messages.append(type(m)(content=sanitize(m.content)))
        elif isinstance(m, AIMessage):
            tc = getattr(m, "tool_calls", None)
            clean = sanitize(m.content) if m.content else ""
            safe_messages.append(AIMessage(content=clean, tool_calls=tc))
        elif isinstance(m, ToolMessage):
            clean = sanitize(m.content) if m.content else ""
            safe_messages.append(ToolMessage(content=clean, tool_call_id=m.tool_call_id))  # type: ignore[arg-type]
        else:
            safe_messages.append(m)

    # 清洗 checkpoint 脏数据
    valid_tool_ids = {
        m.tool_call_id
        for m in safe_messages
        if isinstance(m, ToolMessage)
    }
    for i, m in enumerate(safe_messages):
        if isinstance(m, AIMessage) and getattr(m, "tool_calls", None):
            orphaned = [
                tc for tc in m.tool_calls
                if tc["id"] not in valid_tool_ids
            ]
            if orphaned:
                names = [tc["name"] for tc in orphaned]
                logger.warning(
                    f"[KB] 检测到 {len(orphaned)} 个游离 tool_call（{names}），已从消息中移除"
                )
                safe_messages[i] = AIMessage(content=m.content or "")

    llm_with_tools = kb_llm.bind_tools(kb_tools)
    full = None  # type: ignore[var-annotated]
    async for chunk in llm_with_tools.astream(safe_messages):
        full = chunk if full is None else full + chunk  # type: ignore[assignment]

    if full is None:
        result = dict(ctx_mutations)
        result["messages"] = result.get("messages", []) + [AIMessage(content="")]
        return result

    has_tool_calls = bool(getattr(full, "tool_calls", None))
    logger.info(
        f"[KB] 回复完成，长度: {len(full.content)} 字，"
        f"tool_calls: {has_tool_calls}，"
        f"本轮后消息总数: {len(state['messages']) + 1}"
    )

    # LLM 不调工具时，注入图片 URL（工具已在上一轮执行过）
    if not has_tool_calls:
        image_lines = _collect_images_from_state(state)
        if image_lines:
            full.content = (full.content or "") + image_lines

    result = dict(ctx_mutations)
    result["messages"] = result.get("messages", []) + [full]
    return result


# ------------------------------------------------------------
# RRF 融合（Dense + BM25）
# ------------------------------------------------------------
def _rrf_fusion(
    dense_results: list[dict],
    bm25_results: list[dict],
    k: int = 60,
) -> list[dict]:
    """Reciprocal Rank Fusion：融合 Dense 语义检索和 BM25 关键词检索的排序结果。

    不依赖原始分数量纲（余弦距离 vs ts_rank），仅用排名信息融合。
    Dense 擅长语义匹配，BM25 擅长精确术语匹配（型号/缩写/英文术语），
    两者互补后再送 Cross-Encoder 精排。
    """
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


async def kb_execute_tools(state: AgentState) -> dict:
    """执行 search_knowledge 工具（含 query 改写 + Dense/BM25 混合检索 + Cross-Encoder 精排 + 合并去重）

    每次检索完成后自动将各阶段指标写入 kb_retrieval_logs 表，用于离线评估
    命中率、MRR、各阶段过滤率、分数分布等质量指标。
    """
    from api.rag.kb_embedder import kb_embed
    from api.rag.kb_store import kb_bm25_search, kb_insert_retrieval_log, kb_search
    from api.rag.kb_reranker import kb_rerank

    start_time = time.monotonic()
    last_msg = state["messages"][-1]

    # 找到用户原始问题，用于 query 改写和 reranker
    user_question = ""
    for m in reversed(state["messages"]):
        if isinstance(m, HumanMessage):
            user_question = (m.content or "").strip()
            break

    user_id = state.get("user_id", 0)

    # 检索指标（跨多路查询累计）
    total_dense_hits = 0
    total_bm25_hits = 0

    tool_messages = []
    for tc in last_msg.tool_calls:
        if tc["name"] == "search_knowledge":
            original_query = tc["args"].get("query", "")
            logger.info(f"[KB] Tool search_knowledge 被调用 query={original_query[:80]}")

            # Query 改写：多路召回
            rewritten = await _rewrite_queries(user_question)
            search_queries = rewritten if rewritten else [original_query]

            # 多 query → Dense + BM25 → RRF 融合 → 合并去重
            candidates: dict[str, dict] = {}
            for q in search_queries:
                q_emb = kb_embed([q])[0]
                dense_results = await kb_search(get_pool(), q_emb)
                bm25_results = await kb_bm25_search(get_pool(), q)
                total_dense_hits += len(dense_results)
                total_bm25_hits += len(bm25_results)
                fused = _rrf_fusion(dense_results, bm25_results)
                for r in fused:
                    key = r["content"]
                    if key not in candidates or r["rrf_score"] > candidates[key].get("rrf_score", 0):
                        candidates[key] = r

            if not candidates:
                content = "知识库中未找到与您问题相关的内容。"
                logger.warning(f"[KB] 检索无结果 original_query={original_query[:50]}")
                tool_messages.append(ToolMessage(content=content, tool_call_id=tc["id"]))
                # 记录零命中日志
                _schedule_retrieval_log(
                    user_id, user_question, rewritten,
                    dense_hits=total_dense_hits, bm25_hits=total_bm25_hits,
                    fused_candidates=0, reranked_candidates=0, passed_candidates=0,
                    top_rerank_scores=[], top_dense_similarities=[], top_bm25_scores=[],
                    all_filtered=True, start_time=start_time,
                )
                continue

            # RRF 融合后取 top-N 候选供精排
            fused_count = len(candidates)
            hybrid_top = sorted(candidates.values(), key=lambda r: r["rrf_score"], reverse=True)[:settings.KB_RERANK_CANDIDATES]
            logger.info(
                f"[KB] 混合检索: {len(search_queries)} 路查询 → "
                f"{fused_count} 条去重 → {len(hybrid_top)} 条候选待精排"
            )

            # 收集融合后的 top 分数用于日志
            top_dense_sims = [round(1 - r.get("distance", 1), 3) for r in hybrid_top[:3]]
            top_bm25 = [round(r.get("bm25_score", 0), 3) for r in hybrid_top[:3] if "bm25_score" in r]

            # Cross-Encoder 精排
            reranked = kb_rerank(user_question, hybrid_top, top_k=settings.KB_RETRIEVAL_TOP_K)

            # 精排分数门槛过滤
            passed = [r for r in reranked if r["rerank_score"] >= settings.KB_RERANK_THRESHOLD]
            filtered_count = len(reranked) - len(passed)
            if filtered_count > 0:
                logger.info(
                    f"[KB] Rerank 阈值过滤: {len(reranked)} → {len(passed)} 条，"
                    f"阈值={settings.KB_RERANK_THRESHOLD}，过滤 {filtered_count} 条低相关结果"
                )

            if not passed:
                # 阈值全部过滤时，保留 top-1 兜底，避免口语化等场景下零结果
                logger.warning(
                    f"[KB] Rerank 后全部结果低于阈值({settings.KB_RERANK_THRESHOLD})，"
                    f"fallback top-1 (最高分={reranked[0]['rerank_score']:.3f})"
                )
                passed = reranked[:1]

            # LLM 相关性二次过滤（精排阈值之后，回答生成之前）
            passed_before_llm = len(passed)
            passed = await _llm_relevance_filter(user_question, passed)

            if not passed:
                content = (
                    "知识库中未找到与您问题直接相关的内容。"
                    "请尝试使用文档中的术语重新提问，或换个问法。"
                )
                logger.warning(
                    f"[KB] LLM 相关性过滤后全部不相关 "
                    f"(阈值通过 {passed_before_llm} 条)"
                )
                tool_messages.append(ToolMessage(content=content, tool_call_id=tc["id"]))
                _schedule_retrieval_log(
                    user_id, user_question, rewritten,
                    dense_hits=total_dense_hits, bm25_hits=total_bm25_hits,
                    fused_candidates=fused_count, reranked_candidates=len(reranked),
                    passed_candidates=0,
                    top_rerank_scores=[round(r["rerank_score"], 3) for r in reranked[:3]],
                    top_dense_similarities=top_dense_sims,
                    top_bm25_scores=top_bm25,
                    all_filtered=True, start_time=start_time,
                )
                continue

            # 拼装结果
            parts = []
            for r in passed:
                dist = r.get("distance")
                dense_str = f"Dense={1-dist:.3f}" if dist is not None else "Dense=N/A"
                source = (
                    f"【来源：《{r['document_name']}》{r['section']}章节，"
                    f"{dense_str}，"
                    f"Rerank={r['rerank_score']:.3f}】"
                )
                chunk_text = f"{source}\n{r['content']}"
                # 附带章节截图
                images = r.get("images")
                if images and isinstance(images, list) and len(images) > 0:
                    img_lines = "\n".join(f"![截图]({url})" for url in images)
                    chunk_text += f"\n\n> 📷 本章节截图：\n{img_lines}"
                parts.append(chunk_text)
            content = "\n\n---\n\n".join(parts)
            top3_rerank = [f"{r['rerank_score']:.3f}" for r in passed[:3]]
            logger.info(
                f"[KB] Rerank 精排完成: 有效 {len(passed)} 条，"
                f"rerank top-3 分数: {top3_rerank}"
            )
            tool_messages.append(ToolMessage(content=content, tool_call_id=tc["id"]))

            # 记录检索日志
            _schedule_retrieval_log(
                user_id, user_question, rewritten,
                dense_hits=total_dense_hits, bm25_hits=total_bm25_hits,
                fused_candidates=fused_count, reranked_candidates=len(reranked),
                passed_candidates=len(passed),
                top_rerank_scores=[round(r["rerank_score"], 3) for r in passed[:3]],
                top_dense_similarities=top_dense_sims,
                top_bm25_scores=top_bm25,
                all_filtered=False, start_time=start_time,
            )

    return {"messages": tool_messages}


def _schedule_retrieval_log(
    user_id: int,
    original_query: str,
    rewritten_queries: list[str],
    *,
    dense_hits: int,
    bm25_hits: int,
    fused_candidates: int,
    reranked_candidates: int,
    passed_candidates: int,
    top_rerank_scores: list[float],
    top_dense_similarities: list[float],
    top_bm25_scores: list[float],
    all_filtered: bool,
    start_time: float,
) -> None:
    """fire-and-forget 异步写入检索日志，不阻塞主流程"""
    from api.rag.kb_store import kb_insert_retrieval_log

    latency_ms = int((time.monotonic() - start_time) * 1000)

    async def _write():
        try:
            log_id = await kb_insert_retrieval_log(
                pool=get_pool(),
                user_id=user_id,
                original_query=original_query,
                rewritten_queries=rewritten_queries,
                dense_hits=dense_hits,
                bm25_hits=bm25_hits,
                fused_candidates=fused_candidates,
                reranked_candidates=reranked_candidates,
                passed_candidates=passed_candidates,
                top_rerank_scores=top_rerank_scores,
                top_dense_similarities=top_dense_similarities,
                top_bm25_scores=top_bm25_scores,
                all_filtered=all_filtered,
                latency_ms=latency_ms,
            )
            logger.debug(f"[KB] 检索日志已写入 id={log_id}")
        except Exception:
            logger.exception("[KB] 检索日志写入失败")

    asyncio.create_task(_write())


# ------------------------------------------------------------
# 格式化节点
# ------------------------------------------------------------
KB_FORMAT_PROMPT = """你是一个响应格式化器。将下方知识库助手的回复提取为结构化 JSON。

根据回复内容确定 response_type：
- "greeting"：简单问候/欢迎，无实质内容
- "kb_text"：知识库检索回复（操作步骤/参数查询/故障处理/概念解释等）
- "general"：其他一般性回复（包括告知未找到相关信息）

提取规则：
- summary：用 1-2 句话概括回复要点
- content：保留原始回复的完整文本
- 知识库回复中如果有表格数据，保留在 content 中
- 无对应内容时字段留空数组或 null

知识库助手回复：
{content}"""


async def kb_format_response_node(state: AgentState) -> dict:
    messages = state["messages"]
    if not messages:
        return {"structured_content": None}

    last_ai_msg = messages[-1]
    content = getattr(last_ai_msg, "content", "")

    # 如果 AI 回复为空（LLM 直接调 tool 后未生成文本），回退使用最近的 ToolMessage
    if not content or not isinstance(content, str) or len(content.strip()) < 10:
        for m in reversed(messages):
            if isinstance(m, ToolMessage) and getattr(m, "content", ""):
                tool_content = getattr(m, "content", "")
                if len(tool_content) > 20:
                    logger.info("[KB] AI 回复为空，回退使用检索结果")
                    return {"structured_content": {
                        "response_type": "kb_text",
                        "summary": "知识库检索结果",
                        "content": tool_content,
                    }}
        return {"structured_content": None}

    # 快速路径：直接从 LLM 回复末尾提取 JSON
    from api.agent.schemas import extract_structured_json
    parsed = extract_structured_json(content)
    if parsed is not None:
        logger.info(f"[KB] 快速提取结构化成功 response_type={parsed.response_type}")
        return {"structured_content": parsed.model_dump()}

    # 慢路径：LLM 二次调用格式化
    try:
        result: StructuredResponse = await kb_structured_llm.ainvoke([
            HumanMessage(content=KB_FORMAT_PROMPT.format(content=content))
        ])
        logger.info(f"[KB] LLM 结构化输出成功 response_type={result.response_type}")
        return {"structured_content": result.model_dump()}
    except Exception:
        logger.warning("[KB] 结构化输出格式化失败，回退纯文本")
        return {"structured_content": None}


# ------------------------------------------------------------
# 条件路由
# ------------------------------------------------------------
def kb_should_continue(state: AgentState) -> str:
    """KB Agent 仅 search_knowledge，单 tool 最多 1 次调用。
    若 LLM 再次请求 tool 调用，路由到 finalize 节点强制生成文本回复。"""
    last_msg = state["messages"][-1]
    if hasattr(last_msg, "tool_calls") and last_msg.tool_calls:
        tool_count = 0
        for m in reversed(state["messages"]):
            if isinstance(m, HumanMessage):
                break
            if isinstance(m, ToolMessage):
                tool_count += 1
        if tool_count >= 1:
            logger.warning(f"[KB] 本轮 tool 调用已达 {tool_count} 次，强制生成文本回复")
            return "finalize"
        return "tools"
    return "format_response"


async def kb_finalize_node(state: AgentState) -> dict:
    """不绑定工具，强制 LLM 基于检索结果生成文本回复"""
    from api.agent.context_manager import manage_context, get_summarize_llm

    system_content = KB_ADVISOR_PROMPT

    full_messages, ctx_mutations = await manage_context(
        state, system_content, get_summarize_llm()
    )

    safe_messages = []
    for m in full_messages:
        if isinstance(m, SystemMessage) or isinstance(m, HumanMessage):
            safe_messages.append(type(m)(content=sanitize(m.content)))
        elif isinstance(m, AIMessage):
            tc = getattr(m, "tool_calls", None)
            clean = sanitize(m.content) if m.content else ""
            safe_messages.append(AIMessage(content=clean, tool_calls=tc))
        elif isinstance(m, ToolMessage):
            clean = sanitize(m.content) if m.content else ""
            safe_messages.append(ToolMessage(content=clean, tool_call_id=m.tool_call_id))
        else:
            safe_messages.append(m)

    # 不绑定工具，LLM 只能生成文本
    full = None
    async for chunk in kb_llm.astream(safe_messages):
        full = chunk if full is None else full + chunk

    if full is None:
        result = dict(ctx_mutations)
        result["messages"] = result.get("messages", []) + [AIMessage(content="")]
        return result

    logger.info(f"[KB] finalize 回复完成，长度: {len(full.content)} 字")

    image_lines = _collect_images_from_state(state)
    if image_lines:
        full.content = (full.content or "") + image_lines

    result = dict(ctx_mutations)
    result["messages"] = result.get("messages", []) + [full]
    return result


# ------------------------------------------------------------
# 辅助：从 state 的 ToolMessage 中提取图片 URL
# ------------------------------------------------------------
def _collect_images_from_state(state: AgentState) -> str:
    """从最近一轮的 ToolMessage 中提取图片 URL，返回前端可渲染的 markdown 文本"""
    images: list[str] = []
    for m in reversed(state["messages"]):
        if isinstance(m, ToolMessage):
            content = m.content or ""
            urls = re.findall(r"!\[截图\]\(([^)]+)\)", content)
            for url in urls:
                if url not in images:
                    images.append(url)
            if images:
                break
    if not images:
        return ""
    img_lines = "\n".join(f"![截图]({url})" for url in images)
    return f"\n\n> 📷 相关截图：\n{img_lines}"


# ------------------------------------------------------------
# 构建 Graph
# ------------------------------------------------------------
kb_builder = StateGraph(AgentState)
kb_builder.add_node("kb_advisor", kb_advisor_node)
kb_builder.add_node("tools", kb_execute_tools)
kb_builder.add_node("finalize", kb_finalize_node)
kb_builder.add_node("format_response", kb_format_response_node)
kb_builder.add_edge(START, "kb_advisor")
kb_builder.add_conditional_edges(
    "kb_advisor",
    kb_should_continue,
    {"tools": "tools", "format_response": "format_response", "finalize": "finalize", END: END},
)
kb_builder.add_edge("tools", "kb_advisor")
kb_builder.add_edge("finalize", "format_response")
kb_builder.add_edge("format_response", END)

_kb_graph: CompiledStateGraph | None = None


def get_kb_graph() -> CompiledStateGraph:
    if _kb_graph is None:
        raise RuntimeError("KB Graph 尚未初始化，请在 lifespan 中先调用 init_kb_graph()")
    return _kb_graph


async def get_kb_checkpoint_state(thread_id: str) -> dict | None:
    if _kb_graph is None:
        return None
    config = {"configurable": {"thread_id": thread_id}}
    tup = await _kb_graph.checkpointer.aget_tuple(config)
    if tup is None:
        return None
    return tup.checkpoint.get("channel_values", {})


async def init_kb_graph(pool: AsyncConnectionPool) -> None:
    global _kb_graph
    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

    # checkpoint 表已由 graph.init_graph() 创建，这里只编译 graph
    _kb_graph = kb_builder.compile(checkpointer=AsyncPostgresSaver(conn=pool))  # type: ignore[arg-type]
    logger.info("KB Graph 已初始化（AsyncPostgresSaver + search_knowledge + 结构化输出）")
