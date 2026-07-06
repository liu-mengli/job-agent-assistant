"""
LangGraph 求职助手 Agent
========================
1. State  —— add_messages 自动拼接多轮对话历史 + user_id 供 tool 使用
2. Node   —— LLM 调用节点（bind_tools + astream 循环）+ tool 执行节点
3. Edge   —— conditional edge：有 tool_calls → tools → 回 LLM，无 → END
4. Checkpointer —— AsyncPostgresSaver 持久化到 PostgreSQL，实现断点续传
5. Tool   —— search_resume：检索用户上传的 PDF 简历
"""
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

from api.log import logger
from config import settings

# 模块级池引用（init_graph 时赋值）
_pool: AsyncConnectionPool | None = None


def get_pool() -> AsyncConnectionPool:
    if _pool is None:
        raise RuntimeError("Pool 尚未初始化")
    return _pool


# ============================================================
# 工具函数：清洗 DeepSeek 响应中可能混入的 Unicode 代理字符
# ============================================================
def sanitize(text: str) -> str:
    return text.encode("utf-8", errors="replace").decode("utf-8")


# ============================================================
# 1. 定义 State
# ============================================================
class AgentState(TypedDict):
    messages: Annotated[list, add_messages]
    user_id: int  # 供 tool 检索时过滤归属


# ============================================================
# 2. 初始化 DeepSeek 大模型
# ============================================================
llm = ChatOpenAI(
    model=settings.DEEPSEEK_MODEL,
    api_key=settings.DEEPSEEK_API_KEY,
    base_url=settings.DEEPSEEK_BASE_URL,
    temperature=0,
    request_timeout=30,
)


# ============================================================
# 3. Tool：search_resume（仅声明签名，实际执行在 tool_node）
# ============================================================
@tool
async def search_resume(query: str) -> str:
    """搜索用户上传的PDF简历。当用户要求「分析简历」「看看我的履历」「根据我的背景推荐」「我的工作经验」等涉及个人简历的查询时，必须调用此工具。
    参数 query: 自然语言查询，如「Python 项目经验」「教育背景」「工作经历」"""
    # 实际执行在 execute_tools 节点中
    return ""


tools = [search_resume]


# ============================================================
# 4. Mock 岗位数据
# ============================================================
MOCK_JOB_PROMPT = sanitize("""
你是一个专业的求职顾问 AI，掌握以下招聘岗位数据（仅限这 18 个岗位）。
当用户询问时，请基于数据回答，并给出求职建议。

如果用户询问关于他们简历的问题（如「分析我的简历」「看看我的背景」「根据我的经验推荐岗位」），
请调用一次 search_resume 工具检索简历内容。获取结果后，**必须立即**基于检索结果给出回答，**禁止**再次调用工具。

**【关键】对话历史中可能残留旧简历的检索结果（用户可能已上传新简历导致历史数据过期）。
每次涉及简历的问题，你必须重新调用 search_resume 获取最新数据，严禁仅凭对话历史中的旧检索结果直接回答。**

## 深圳

| 岗位 | 公司 | 薪资 | 要求 |
|------|------|------|------|
| Python 后端开发 | 腾讯 | 25k-40k·14薪 | 3年+ Python，熟悉 FastAPI/Django，有高并发经验 |
| 前端开发工程师 | 字节跳动 | 30k-50k·15薪 | 3年+ Vue3/React，TypeScript 熟练，有大型项目经验 |
| AI 算法工程师 | 商汤科技 | 35k-60k·14薪 | 硕士+，PyTorch，有 CV/NLP 落地经验 |
| DevOps 工程师 | 华为 | 20k-35k·14薪 | 熟悉 K8s/Docker，CI/CD 流水线搭建经验 |

## 上海

| 岗位 | 公司 | 薪资 | 要求 |
|------|------|------|------|
| Go 后端开发 | 哔哩哔哩 | 28k-45k·15薪 | 3年+ Go，微服务架构，有中间件开发经验优先 |
| 数据分析师 | 小红书 | 20k-35k·14薪 | SQL/Python，有用户增长分析经验 |
| 产品经理（B端） | 钉钉 | 30k-50k·16薪 | 3年+ B端产品经验，有 SaaS 背景优先 |
| 测试开发 | 美团 | 22k-38k·14薪 | 自动化测试框架搭建，有性能测试经验 |

## 北京

| 岗位 | 公司 | 薪资 | 要求 |
|------|------|------|------|
| Java 架构师 | 百度 | 40k-65k·16薪 | 5年+ Java，分布式系统设计，有中间件研发经验 |
| 安全工程师 | 奇安信 | 25k-45k·14薪 | 渗透测试/安全审计，有 CISSP 证书优先 |
| 运维开发 | 京东 | 20k-35k·14薪 | Python/Shell，有大规模集群管理经验 |
| 客户端开发（iOS） | 快手 | 30k-50k·15薪 | Swift/OC 精通，有音视频开发经验优先 |

## 广州

| 岗位 | 公司 | 薪资 | 要求 |
|------|------|------|------|
| 前端开发 | 网易 | 20k-35k·14薪 | 2年+ Vue/React，有小程序开发经验 |
| PHP 开发 | 唯品会 | 18k-28k·13薪 | 3年+ PHP，熟悉 Laravel/Hyperf 框架 |
| 数据分析师 | 希音 | 18k-30k·14薪 | SQL 熟练，有电商数据分析经验 |

## 成都

| 岗位 | 公司 | 薪资 | 要求 |
|------|------|------|------|
| Java 开发 | 蚂蚁集团 | 22k-35k·14薪 | 3年+ Java，Spring Boot 微服务，有金融背景优先 |
| 游戏测试 | 腾讯天美 | 15k-25k·14薪 | 热爱游戏，有自动化测试能力 |
| UI 设计师 | 完美世界 | 18k-28k·13薪 | 3年+ 游戏 UI 设计经验，有完整项目案例 |

## 回答规则

1. 当用户提到城市 + 岗位方向时，列出匹配的岗位，简要说明推荐理由。
2. 当用户只问城市时，列出该城市所有岗位。
3. 当用户问的岗位/城市不在数据中时，诚实告知暂无数据，并建议扩大搜索范围。
4. 语气友好、专业，像一位有经验的猎头顾问。
5. 每次回答控制在 200 字以内，重点突出，避免冗长。
""")


# ============================================================
# 5. 节点函数
# ============================================================
async def job_advisor_node(state: AgentState) -> dict:
    full_messages = [SystemMessage(content=MOCK_JOB_PROMPT)] + state["messages"]

    safe_messages = []
    for m in full_messages:
        if isinstance(m, SystemMessage) or isinstance(m, HumanMessage):
            safe_messages.append(type(m)(content=sanitize(m.content)))
        elif isinstance(m, AIMessage):
            # 保留原始消息（含 tool_calls），内容做 sanitize
            tc = getattr(m, "tool_calls", None)
            clean = sanitize(m.content) if m.content else ""
            safe_messages.append(AIMessage(content=clean, tool_calls=tc))
        elif isinstance(m, ToolMessage):
            # 保留 ToolMessage，DeepSeek 需要它匹配 tool_calls
            clean = sanitize(m.content) if m.content else ""
            safe_messages.append(ToolMessage(content=clean, tool_call_id=m.tool_call_id))  # type: ignore[arg-type]
        else:
            safe_messages.append(m)

    # 绑定工具：LLM 可以在需要时调用 search_resume
    llm_with_tools = llm.bind_tools(tools)
    full = None  # type: ignore[var-annotated]  # AIMessageChunk 累加，含 content + tool_calls
    async for chunk in llm_with_tools.astream(safe_messages):
        # LangChain AIMessageChunk 的 + 运算自动合并 content 和 tool_calls
        full = chunk if full is None else full + chunk  # type: ignore[assignment]

    if full is None:
        return {"messages": [AIMessage(content="")]}

    has_tool_calls = bool(getattr(full, "tool_calls", None))
    logger.info(
        f"求职助手回复完成，长度: {len(full.content)} 字，"
        f"tool_calls: {has_tool_calls}，"
        f"本轮后消息总数: {len(state['messages']) + 1}"
    )
    return {"messages": [full]}


async def execute_tools(state: AgentState) -> dict:
    """执行 search_resume 工具调用，将检索结果返回给 LLM"""
    from api.rag.embedder import embed
    from api.rag.store import search as vector_search

    last_msg = state["messages"][-1]
    user_id = state.get("user_id", 0)

    tool_messages = []
    for tc in last_msg.tool_calls:
        if tc["name"] == "search_resume":
            query = tc["args"].get("query", "")
            logger.info(f"Tool search_resume 被调用 user={user_id} query={query[:50]}")
            q_emb = embed([query])[0]
            chunks = await vector_search(get_pool(), q_emb, user_id)
            if chunks:
                content = "\n\n---\n\n".join(chunks)
            else:
                content = "简历中未找到与您问题相关的内容。请确认简历已上传。"
            tool_messages.append(ToolMessage(content=content, tool_call_id=tc["id"]))

    return {"messages": tool_messages}


def should_continue(state: AgentState) -> str:
    """检查最后一条 AI 消息是否包含 tool_calls，且本轮调用未超过 2 次"""
    last_msg = state["messages"][-1]
    if hasattr(last_msg, "tool_calls") and last_msg.tool_calls:
        # 统计本轮（最近一条 HumanMessage 之后）已执行的 tool 调用次数
        tool_count = 0
        for m in reversed(state["messages"]):
            if isinstance(m, HumanMessage):
                break
            if isinstance(m, ToolMessage):
                tool_count += 1
        if tool_count >= 2:
            logger.warning(f"本轮 tool 调用已达 {tool_count} 次，强制结束")
            return END
        return "tools"
    return END


# ============================================================
# 6. 构建 Graph
# ============================================================
builder = StateGraph(AgentState)
builder.add_node("job_advisor", job_advisor_node)
builder.add_node("tools", execute_tools)
builder.add_edge(START, "job_advisor")
builder.add_conditional_edges("job_advisor", should_continue, {"tools": "tools", END: END})
builder.add_edge("tools", "job_advisor")  # tool 结果返回 LLM 继续推理

_graph: CompiledStateGraph | None = None


def get_graph() -> CompiledStateGraph:
    if _graph is None:
        raise RuntimeError("Graph 尚未初始化，请在 lifespan 中先调用 init_graph()")
    return _graph


async def get_checkpoint_state(thread_id: str) -> dict | None:
    if _graph is None:
        return None
    config = {"configurable": {"thread_id": thread_id}}
    tup = await _graph.checkpointer.aget_tuple(config)
    if tup is None:
        return None
    return tup.checkpoint.get("channel_values", {})


async def init_graph(pool: AsyncConnectionPool) -> None:
    global _graph, _pool
    from psycopg import AsyncConnection
    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

    _pool = pool

    setup_conn = await AsyncConnection.connect(settings.PG_URL, autocommit=True)
    try:
        temp_saver = AsyncPostgresSaver(conn=setup_conn)
        await temp_saver.setup()
    finally:
        await setup_conn.close()

    _graph = builder.compile(checkpointer=AsyncPostgresSaver(conn=pool))  # type: ignore[arg-type]
    logger.info("Graph 已初始化（AsyncPostgresSaver + search_resume tool）")
