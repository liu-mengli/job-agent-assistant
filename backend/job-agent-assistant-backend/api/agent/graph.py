"""
LangGraph 求职助手 Agent
========================
1. State  —— add_messages 自动拼接多轮对话历史 + user_id + structured_content
2. Node   —— job_advisor（bind_tools + astream）+ tools（执行检索）+ format_response（结构化输出）
3. Edge   —— conditional edge：有 tool_calls → tools → 回 LLM，无 → format_response → END
4. Checkpointer —— AsyncPostgresSaver 持久化到 PostgreSQL，实现断点续传
5. Tool   —— search_resume / search_jobs：RAG 检索
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

from api.agent.schemas import StructuredResponse
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
    structured_content: dict | None  # format_response_node 写入的结构化 JSON


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

# 结构化格式化 LLM（非流式，with_structured_output）
structured_llm = ChatOpenAI(
    model=settings.DEEPSEEK_MODEL,
    api_key=settings.DEEPSEEK_API_KEY,
    base_url=settings.DEEPSEEK_BASE_URL,
    temperature=0,
    request_timeout=15,
).with_structured_output(StructuredResponse, method="json_mode")


# ============================================================
# 3. Tool：search_resume（仅声明签名，实际执行在 tool_node）
# ============================================================
@tool
async def search_resume(query: str) -> str:
    """搜索用户上传的PDF简历内容。触发场景：「分析简历」「推荐适合我的」「根据我的背景」「我的经验」「匹配度」「适合我吗」「优化简历」「改简历」「打招呼语」「自我介绍」。
    参数 query: 提取用户原话中的关键技能词，如「所有技能」「Python项目」「教育背景」。
    全流程推荐模式下与 search_jobs 同时调用。每轮最多调用一次。"""
    return ""


@tool
async def search_jobs(query: str) -> str:
    """搜索真实招聘岗位数据库。触发场景：「看看岗位」「推荐」「找工作」「有什么职位」「匹配」「适合」「优化简历」「针对JD」。
    参数 query: 用户原话中的岗位/技术关键词，如「AI Agent开发」「Python后端」。
    全流程推荐模式下与 search_resume 同时调用。每轮最多调用一次，禁止换关键词反复搜索。"""
    return ""


tools = [search_resume, search_jobs]


# ============================================================
# 4. 求职顾问系统提示词
# ============================================================
JOB_ADVISOR_PROMPT = sanitize("""
你是一个专业的求职顾问 AI，拥有真实的招聘岗位数据库。根据用户意图，自动选择以下模式：

**【模式判断——根据用户措辞自动选择】**

| 用户说法 | 模式 | 工具调用 |
|---------|------|---------|
| 「看看岗位」「有什么职位」「深圳 Python」「找 AI 岗位」 | **浏览模式** | 只调 search_jobs |
| 「推荐适合我的」「根据我的背景」「我适合什么」「帮我推荐」 | **全流程推荐** | search_resume + search_jobs（同时调用） |

**【核心规则——必须严格遵守】**

1. 每个工具每轮最多调用一次。全流程推荐时同时调用两个工具（共 2 个 tool_call）。
2. 接受检索结果，禁止换关键词反复搜索。无匹配时如实告知并列出最接近的替代。
3. 全流程推荐/匹配分析/简历优化场景允许双工具调用，之后必须给出最终回答。

**【全流程推荐模板】（用户说「推荐适合我的」时使用）**

第一步：同时调用 search_resume + search_jobs
第二步：基于返回结果，按以下结构回复——

**📋 为你推荐以下岗位**

| # | 岗位 | 公司 | 薪资 | 匹配度 |
|---|------|------|------|--------|
| 1 | ... | ... | ... | XX% |
| 2 | ... | ... | ... | XX% |

（每个岗位附带 1 句推荐理由，控制在 20 字以内）

**🔍 综合评估**（3-5 句）
- 你的核心优势：从简历提炼 2-3 个与这些岗位最匹配的能力
- 需要关注的短板：1-2 个共性的差距
- 如果用户没有上传简历，改为：「建议上传简历以获得精准匹配分析。以下岗位基于你的求职偏好排序。」

**💡 下一步**
- 我可以帮你：「针对某个岗位优化简历」「准备面试（面试题 / 打招呼语）」「查看某个岗位的详细匹配度分析」
- 用 1 句话询问用户选择，不要列多项让人不知所措

**【无简历降级处理】**

当 search_resume 返回空时：
- 不输出匹配度列，用「—」或留空
- 「综合评估」替换为根据偏好数据做的推荐理由（1-2 句）
- 「下一步」改为：「💡 上传简历后我可以做精准匹配度分析和简历优化。点击侧边栏 📎 按钮上传。」

**【浏览模式模板】（用户说「看看岗位」时使用）**

1. 调用 search_jobs → 用表格列出 3-5 个岗位
2. 末尾加新用户引导（仅首次）：「💡 上传简历可获匹配度分析，设置偏好可精准推荐。」
3. 不追问下一步，简洁收尾

---

## 回答规则

1. 岗位用表格（名称/公司/薪资/经验要求），附带简短推荐理由。
2. 每次 3-5 个最匹配的岗位。
3. 无匹配时诚实告知 + 列出最接近替代。
4. 语气友好专业，像资深猎头顾问。
5. 全流程推荐时必须询问下一步，浏览模式则简洁收尾。

## 岗位匹配度分析（用户要求详细分析某个岗位时输出）

当用户要求分析岗位与简历的匹配度时，按以下格式输出：

**总体匹配度：XX%**

用一段话概括整体匹配情况（2-3 句），点出最突出的优势和最关键的差距。

**技能逐项对比**

| 岗位要求 | 匹配度 | 你的情况 | 说明 |
|---------|--------|---------|------|
| 要求项1 | ✅匹配 | 简历中的对应经验 | 匹配说明 |
| 要求项2 | ⚠️部分 | 相关但不完全一致 | 差距说明 |
| 要求项3 | ❌缺失 | 无相关经验 | 影响程度 |

**优势亮点**
- 列出 2-4 条简历中与岗位高度匹配的优势

**需加强的短板**
- 列出 2-4 条差距，给出具体提升建议（学习什么技术、补什么项目经验等）

**投递建议**
- 给出是否推荐投递的判断，以及投递时简历上应该突出的重点（1-2 句）

匹配度评估原则：
- 技能匹配权重最高（技术栈、工具链），经验年限次之，学历最后
- 不要因为 1-2 个次要技能不匹配就打低分
- 如果核心技能（JD 前 3 条要求）全部命中，匹配度不应低于 70%
- 如果简历中完全没有相关技术栈，匹配度不应高于 30%

## 简历优化建议（仅在用户明确要求时输出）

当用户要求针对某个岗位优化简历时，按以下格式输出：

**【关键约束】你必须严格基于简历中的真实内容进行优化，禁止虚构任何不存在的经历、项目或技能。**
只能调整描述方式、补充关键词、强化已有经验，不得编造简历中没有的东西。

**1. 应该突出的经历**
- 从简历中挑选与 JD 匹配度最高的 2-3 条经历/项目，说明为什么这些是亮点
- 每条给出「当前写法」和「建议优化方向」

**2. 应补充的关键词**
- 列出 JD 中出现但简历中未涉及的 3-5 个关键词/技能点
- 标注哪些是「核心缺失」（必须补的），哪些是「锦上添花」（可选）
- 如果简历中有相关但不明确的描述，指出在哪里可以自然地融入这些关键词

**3. 描述太弱的地方**
- 指出 2-3 处简历中写得过于笼统或量化的地方
- 给出具体改写建议（不能编造数据，只能让已有数据更突出）
- 例如：「负责 XX 项目」→「主导 XX 项目，解决了 YY 技术难题」

**4. 不建议写的内容**
- 指出简历中与目标岗位无关甚至减分的内容
- 说明原因（与 JD 方向不符 / 显得方向分散 / 过时技术）

**5. 优化后的项目描述示例**
- 选择简历中 1 个最相关的项目，给出优化后的完整项目描述
- 格式：项目简介（1 句）+ 职责和成果（3-5 条 bullet point，STAR 法则）
- 必须基于简历中真实存在的项目，用 **[简历原文]** 标注优化前后的对比
- 示例格式：
  ```
  优化前（简历原文）：
  > 负责后端API开发，使用FastAPI框架

  优化后：
  > 主导核心业务 API 重构，基于 FastAPI + PostgreSQL 构建高并发接口，日均处理 10w+ 请求
  ```

## 打招呼语与自我介绍（仅在用户明确要求时输出）

当用户要求生成打招呼语或自我介绍时，按以下格式输出：

**1. 打招呼语（BOSS直聘/拉勾等平台适用）**
- 生成 2 个版本：简洁版（80 字以内）和标准版（150 字以内）
- 格式参考：「您好，我有 X 年 XX 经验，擅长 XX 和 XX，参与过 XX 项目（量化成果），对这个岗位很感兴趣，期待您的回复。」
- 严禁编造任何经历，所有技能和项目必须来自简历

**2. 自我介绍（面试开场用）**
- 生成 1 分钟版（约 200 字）
- 结构：我是谁 + 核心技能 + 1-2 个亮点项目 + 为什么投这个岗位 + 结语
- 语气自信但不浮夸，风格口语化（适合口头自我介绍，不要像在读稿）

**3. 个人优势话术**
- 提炼 3 条可以用在面试中的「一句话优势」
- 每条必须对应简历中的具体经验
- 格式：「我擅长 XX，比如在 XX 项目中我做了 XX，取得了 XX 效果」
""")


# ============================================================
# 5. 节点函数
# ============================================================
async def _get_preferences_prompt(user_id: int) -> str:
    """读取用户求职偏好并格式化为 prompt 片段"""
    try:
        from psycopg.rows import dict_row
        async with _pool.connection() as conn:
            cur = await conn.execute(
                "SELECT * FROM user_preferences WHERE user_id = %s", (user_id,)
            )
            row = await cur.fetchone()
            if row is None:
                return ""
            cols = [c.name for c in cur.description] if cur.description else []
            pref = dict(zip(cols, row)) if cols else {}

        parts = []
        if pref.get("city"):
            parts.append(f"- 期望城市：{pref['city']}")
        if pref.get("work_mode"):
            mode_map = {"remote": "远程", "onsite": "现场", "hybrid": "混合"}
            parts.append(f"- 工作模式：{mode_map.get(pref['work_mode'], pref['work_mode'])}")
        if pref.get("salary_min") or pref.get("salary_max"):
            smin = pref.get("salary_min") or ""
            smax = pref.get("salary_max") or ""
            parts.append(f"- 薪资期望：{smin:,}-{smax:,} 元/月")
        if pref.get("industry"):
            parts.append(f"- 偏好行业：{pref['industry']}")
        if pref.get("company_size"):
            parts.append(f"- 公司规模偏好：{pref['company_size']}")
        if pref.get("tech_stack"):
            parts.append(f"- 技术方向：{pref['tech_stack']}")
        if pref.get("experience_years"):
            parts.append(f"- 工作经验：{pref['experience_years']} 年")
        if pref.get("job_status"):
            parts.append(f"- 求职状态：{pref['job_status']}")
        if pref.get("deal_breakers"):
            parts.append(f"- 排除条件：{pref['deal_breakers']}")

        if not parts:
            return ""

        return (
            "\n\n## 用户求职偏好（当前用户已设置，请据此优化回答）\n"
            + "\n".join(parts)
            + "\n\n使用这些偏好来：过滤不匹配的岗位、优先推荐符合薪资/城市/技术方向的岗位、"
            "对比简历时考虑用户的目标方向。**如果用户明确要求偏离偏好（如搜其他城市），以用户最新指令为准。**"
        )
    except Exception:
        logger.exception("读取用户偏好失败")
        return ""


async def job_advisor_node(state: AgentState) -> dict:
    user_id = state.get("user_id", 0)
    pref_prompt = await _get_preferences_prompt(user_id)
    system_content = JOB_ADVISOR_PROMPT + pref_prompt
    full_messages = [SystemMessage(content=system_content)] + state["messages"]

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

    # 清洗 checkpoint 中可能残留的脏数据：
    # 如果存在 AIMessage(tool_calls) 但后续缺少对应的 ToolMessage，
    # DeepSeek 会拒绝请求（insufficient tool messages）。此时移除游离的 tool_calls。
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
                    f"检测到 {len(orphaned)} 个游离 tool_call（{names}），"
                    f"缺少对应 ToolMessage，已从消息中移除"
                )
                safe_messages[i] = AIMessage(content=m.content or "")

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
    """执行 search_resume / search_jobs 工具调用"""
    from api.rag.embedder import embed
    from api.rag.store import search as vector_search, search_jobs as job_search

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

        elif tc["name"] == "search_jobs":
            query = tc["args"].get("query", "")
            logger.info(f"Tool search_jobs 被调用 query={query[:50]}")
            q_emb = embed([query])[0]
            jobs = await job_search(get_pool(), q_emb)
            if jobs:
                lines = []
                for j in jobs:
                    lines.append(
                        f"- {j['title']} | {j['company']} | {j['salary']} | "
                        f"{j['experience']} | {j['education']}\n  {j['description'][:200]}"
                    )
                content = "\n".join(lines)
            else:
                content = "未找到匹配的岗位，请尝试更换搜索条件。"
            tool_messages.append(ToolMessage(content=content, tool_call_id=tc["id"]))

    return {"messages": tool_messages}


# ============================================================
# 格式化提示词：将求职顾问的 Markdown 回复转为结构化 JSON
# ============================================================
FORMAT_PROMPT = """你是一个响应格式化器。将下方求职顾问的回复提取为结构化 JSON。

根据回复内容确定 response_type：
- "greeting"：简单问候/欢迎，无实质内容
- "browse"：列出岗位列表，每个岗位无匹配度评分
- "full_recommendation"：列出岗位列表且每个岗位有 match_score，含综合评估和下一步追问
- "match_analysis"：分析单个岗位与简历的匹配度，含技能逐项对比
- "resume_optimization"：简历修改建议
- "resume_analysis"：分析简历本身内容
- "general"：其他一般性回复

提取规则：
- jobs 数组：每个岗位提取 rank/title/company/salary/experience/match_score(如有)/reason
- skill_comparisons 数组：提取 requirement/match_level(match/partial/missing)/your_status/note
- overall_match：整数 0-100，仅 match_analysis 模式
- strengths/weaknesses：字符串数组
- highlights：[{original, suggestion}] 格式
- 无对应内容时字段留空数组或 null

求职顾问回复：
{content}"""


async def format_response_node(state: AgentState) -> dict:
    """将 job_advisor 的最终回复格式化为结构化 JSON"""
    messages = state["messages"]
    if not messages:
        return {"structured_content": None}

    last_ai_msg = messages[-1]
    content = getattr(last_ai_msg, "content", "")
    if not content or not isinstance(content, str) or len(content.strip()) < 10:
        return {"structured_content": None}

    try:
        result: StructuredResponse = await structured_llm.ainvoke([
            HumanMessage(content=FORMAT_PROMPT.format(content=content))
        ])
        logger.info(f"结构化输出成功 response_type={result.response_type}")
        return {"structured_content": result.model_dump()}
    except Exception:
        logger.exception("结构化输出格式化失败，回退纯文本")
        return {"structured_content": None}


# ============================================================
# 5. 条件路由
# ============================================================
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
            logger.warning(f"本轮 tool 调用已达 {tool_count} 次，强制格式化输出")
            return "format_response"
        return "tools"
    return "format_response"


# ============================================================
# 6. 构建 Graph
# ============================================================
builder = StateGraph(AgentState)
builder.add_node("job_advisor", job_advisor_node)
builder.add_node("tools", execute_tools)
builder.add_node("format_response", format_response_node)
builder.add_edge(START, "job_advisor")
builder.add_conditional_edges(
    "job_advisor",
    should_continue,
    {"tools": "tools", "format_response": "format_response", END: END},
)
builder.add_edge("tools", "job_advisor")  # tool 结果返回 LLM 继续推理
builder.add_edge("format_response", END)

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
    logger.info("Graph 已初始化（AsyncPostgresSaver + 双 Tool + 结构化输出）")
