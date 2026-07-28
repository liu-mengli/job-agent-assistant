"""
LangGraph HR 面试助手 Agent
===========================
1. State  —— AgentState（add_messages + user_id + structured_content + conversation_summary）
2. Node   —— hr_advisor（直接注入简历文件全文，无需 tool）+ format_response
3. Edge   —— START → hr_advisor → format_response → END
4. Checkpointer —— AsyncPostgresSaver 持久化到 PostgreSQL
5. 简历来源 —— 从 HR_RESUME_PATH 指定的 .md 文件读取，嵌入 System Prompt
"""
import os
from typing import Annotated

from langchain_core.messages import (
    SystemMessage, HumanMessage, AIMessage, ToolMessage,
)
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.graph.state import CompiledStateGraph
from psycopg_pool import AsyncConnectionPool
from typing_extensions import TypedDict

from api.agent.schemas import StructuredResponse
from api.agent.graph import sanitize
from api.log import logger
from config import settings

# ------------------------------------------------------------
# State
# ------------------------------------------------------------
class AgentState(TypedDict):
    messages: Annotated[list, add_messages]
    user_id: int
    structured_content: dict | None
    conversation_summary: str | None  # 增量摘要


# ------------------------------------------------------------
# LLM
# ------------------------------------------------------------
hr_llm = ChatOpenAI(
    model=settings.DEEPSEEK_MODEL,
    api_key=settings.DEEPSEEK_API_KEY,
    base_url=settings.DEEPSEEK_BASE_URL,
    temperature=0,
    request_timeout=30,
    extra_body={"ep_enable_prompt_caching": True},
)

hr_structured_llm = ChatOpenAI(
    model=settings.DEEPSEEK_MODEL,
    api_key=settings.DEEPSEEK_API_KEY,
    base_url=settings.DEEPSEEK_BASE_URL,
    temperature=0,
    request_timeout=15,
    extra_body={"ep_enable_prompt_caching": True},
).with_structured_output(StructuredResponse, method="json_mode")


# ------------------------------------------------------------
# 简历文件读取
# ------------------------------------------------------------
def _load_resume() -> str:
    """读取简历 .md 文件全文，失败时返回空字符串"""
    path = settings.HR_RESUME_PATH
    if not os.path.isabs(path):
        path = os.path.join(os.path.dirname(__file__), "..", "..", path)
    try:
        with open(path, encoding="utf-8") as f:
            content = f.read().strip()
        if content:
            logger.info(f"[HR] 简历文件加载成功 path={path} chars={len(content)}")
            return content
        logger.warning(f"[HR] 简历文件为空 path={path}")
        return ""
    except FileNotFoundError:
        logger.warning(f"[HR] 简历文件不存在 path={path}")
        return ""
    except Exception:
        logger.exception(f"[HR] 简历文件读取失败 path={path}")
        return ""


# 模块加载时读取一次，后续复用
_RESUME_CONTENT = _load_resume()


# ------------------------------------------------------------
# HR 面试官 System Prompt
# ------------------------------------------------------------
HR_ADVISOR_PROMPT_TEMPLATE = sanitize("""你是一位专业的求职顾问，帮助求职者向 HR 展现竞争力。以下是候选人的完整简历，你需要基于这份简历，从求职者的角度出发，帮助 TA 展现最好的自己。

**核心原则——必须严格遵守**

1. 所有回答必须基于简历真实内容，**严禁虚构任何经历、技能或项目**。
2. 简历中没有提到的信息，明确告知「简历中未提及」。
3. 始终以求职者利益为先，只展示候选人的优势和亮点，**严禁提及候选人「不会」「没做过」「未掌握」「未提及」「不具备」的任何技术或经验**。不要帮 HR 找候选人的短板。
4. 人称必须使用「候选人」（第三人称），**严禁使用「你」「你的」**，因为这份分析是给 HR 看的，不是给候选人看的。
5. 语气专业客观，像一位真正为求职者着想的顾问。

**回答格式**

**技能分析型**（「擅长什么技术？」「XX 能力怎么样？」）：
1. 用表格列出技能 + 掌握程度 + 简历原文佐证
2. 总结核心竞争力（2-3 句），聚焦亮点

**项目分析型**（「做过哪些项目？」）：
1. 每个项目列出：项目名称/技术栈/角色/关键成果
2. 重点评价技术深度和工程价值，突显候选人的贡献

**匹配度分析型**（「适合 XX 岗位吗？」）：
1. 按「总体匹配度 X%」→「技能逐项对比」→「优势」→「提升建议」结构

**通用问答型**：
1. 直接基于简历内容回答，突出候选人的优势面
2. 简洁收尾

**回复格式要求**：在回复末尾，附加一个 JSON 块来描述你的回答类型，格式为：
```json
{"response_type": "match_analysis", "summary": "一句话总结"}
```
response_type 可选值：skill_analysis（技能分析）、project_analysis（项目分析）、match_analysis（匹配度分析）、general（通用问答）。
""")


def _build_system_prompt() -> str:
    """组装完整的 System Prompt（模板 + 简历全文）"""
    if not _RESUME_CONTENT:
        return HR_ADVISOR_PROMPT_TEMPLATE + "\n\n⚠️ 简历文件未加载，请确认 HR_RESUME_PATH 配置正确。"
    return (
        HR_ADVISOR_PROMPT_TEMPLATE
        + "\n\n---\n\n## 候选人简历全文\n\n"
        + _RESUME_CONTENT
    )


HR_SYSTEM_PROMPT = _build_system_prompt()


# ------------------------------------------------------------
# 节点函数
# ------------------------------------------------------------
async def hr_advisor_node(state: AgentState) -> dict:
    from api.agent.context_manager import manage_context, get_summarize_llm

    full_messages, ctx_mutations = await manage_context(
        state, HR_SYSTEM_PROMPT, get_summarize_llm()
    )

    # sanitize 所有消息，兼容旧 checkpoint 中可能存在的 tool 相关消息
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

    # 不绑定工具，直接生成文本回复
    full = None  # type: ignore[var-annotated]
    async for chunk in hr_llm.astream(safe_messages):
        full = chunk if full is None else full + chunk  # type: ignore[assignment]

    if full is None:
        result = dict(ctx_mutations)
        result["messages"] = result.get("messages", []) + [AIMessage(content="")]
        return result

    logger.info(
        f"[HR] 回复完成，长度: {len(full.content)} 字，"
        f"本轮后消息总数: {len(state['messages']) + 1}"
    )
    result = dict(ctx_mutations)
    result["messages"] = result.get("messages", []) + [full]
    return result


# ------------------------------------------------------------
# 格式化节点
# ------------------------------------------------------------
HR_FORMAT_PROMPT = """你是一个响应格式化器。将下方 HR 面试助手的回复提取为结构化 JSON。

根据回复内容确定 response_type：
- "greeting"：简单问候/欢迎，无实质内容
- "resume_analysis"：分析简历内容（技能/项目/经验总结）
- "match_analysis"：分析候选人与岗位的匹配度，含技能逐项对比
- "general"：其他一般性回复（包括面试问题生成）

提取规则：
- skill_comparisons 数组：提取 requirement/match_level(match/partial/missing)/your_status/note
- strengths/weaknesses：字符串数组
- skill_matrix：[{{skill, level, evidence}}] 格式
- projects：[{{name, tech_stack, role, highlights}}] 格式
- 无对应内容时字段留空数组或 null

HR 助手回复：
{content}"""


async def hr_format_response_node(state: AgentState) -> dict:
    messages = state["messages"]
    if not messages:
        return {"structured_content": None}

    last_ai_msg = messages[-1]
    content = getattr(last_ai_msg, "content", "")
    if not content or not isinstance(content, str) or len(content.strip()) < 10:
        return {"structured_content": None}

    # 直接从 LLM 回复末尾提取 JSON，提取不到就跳过
    from api.agent.schemas import extract_structured_json
    parsed = extract_structured_json(content)
    if parsed is not None:
        logger.info(f"[HR] 提取结构化成功 response_type={parsed.response_type}")
        return {"structured_content": parsed.model_dump()}
    logger.info("[HR] 未提取到结构化 JSON，跳过")
    return {"structured_content": None}


# ------------------------------------------------------------
# 构建 Graph（无 tool，直接直线）
# ------------------------------------------------------------
hr_builder = StateGraph(AgentState)
hr_builder.add_node("hr_advisor", hr_advisor_node)
hr_builder.add_node("format_response", hr_format_response_node)
hr_builder.add_edge(START, "hr_advisor")
hr_builder.add_edge("hr_advisor", "format_response")
hr_builder.add_edge("format_response", END)

_hr_graph: CompiledStateGraph | None = None


def get_hr_graph() -> CompiledStateGraph:
    if _hr_graph is None:
        raise RuntimeError("HR Graph 尚未初始化，请在 lifespan 中先调用 init_hr_graph()")
    return _hr_graph


async def get_hr_checkpoint_state(thread_id: str) -> dict | None:
    if _hr_graph is None:
        return None
    config = {"configurable": {"thread_id": thread_id}}
    tup = await _hr_graph.checkpointer.aget_tuple(config)
    if tup is None:
        return None
    return tup.checkpoint.get("channel_values", {})


async def init_hr_graph(pool: AsyncConnectionPool) -> None:
    global _hr_graph
    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

    _hr_graph = hr_builder.compile(checkpointer=AsyncPostgresSaver(conn=pool))  # type: ignore[arg-type]
    logger.info("HR Graph 已初始化（简历文件注入 + 结构化输出，无 tool 直线架构）")
