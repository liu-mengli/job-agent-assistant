"""
LangGraph 天气查询 Demo
========================
演示核心概念：
1. State —— 图中流动的数据结构（含 add_messages 多轮对话）
2. Node —— 处理数据的函数（LLM 调用）
3. Edge —— 节点之间的连接方向
4. Graph —— 把 Node 和 Edge 组装成可执行图
"""
from typing import Annotated

from langchain_core.messages import SystemMessage, HumanMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.graph.state import CompiledStateGraph
from typing_extensions import TypedDict

from api.log import logger
from config import settings


# ============================================================
# 1. 定义 State（图中各节点共享的数据结构）
# ============================================================
# add_messages 是 LangGraph 内置的消息合并器：
# - 新消息会自动追加到历史消息列表中
# - 同类型消息不会重复，人的消息 + AI 的消息交替拼接
class AgentState(TypedDict):
    messages: Annotated[list, add_messages]  # 多轮对话消息历史


# ============================================================
# 2. 初始化 DeepSeek 大模型
# ============================================================
# temperature=0：确定性问题，输出稳定可预测
# request_timeout=30：API 超过30秒无响应则抛异常
llm = ChatOpenAI(
    model=settings.DEEPSEEK_MODEL,
    api_key=settings.DEEPSEEK_API_KEY,
    base_url=settings.DEEPSEEK_BASE_URL,
    temperature=0,
    request_timeout=30,
)


# ============================================================
# 3. Mock 天气数据（模块级常量，只创建一次）
# ============================================================
MOCK_WEATHER_PROMPT = """
以下是你掌握的城市天气数据（仅限这5个城市）：

| 城市 | 今日天气 | 温度范围 | 其他信息 |
|------|---------|---------|---------|
| 北京 | 晴 | 22°C ~ 30°C | 北风2级，适合户外活动 |
| 深圳 | 多云转阵雨 | 26°C ~ 32°C | 湿度85%，建议带伞 |
| 上海 | 阴天 | 20°C ~ 25°C | 傍晚可能转小雨 |
| 广州 | 雷阵雨 | 25°C ~ 33°C | 出门务必带伞，避开低洼路段 |
| 成都 | 多云 | 18°C ~ 26°C | 空气清新，适合散步 |

当用户询问以上城市时，直接基于数据回答并给出出行建议。
当用户询问其他城市时，诚实告知没有该城市的实时数据。
回答时语气友好、简洁，控制在3句话以内。
"""


# ============================================================
# 4. 定义节点函数（图中可调用的处理单元）
# ============================================================
async def weather_node(state: AgentState) -> dict:
    """
    天气查询节点：
    1. 从 State 中取出 messages（包含系统提示 + 历史对话 + 最新的用户消息）
    2. 调用 LLM 生成回复
    3. 返回 {messages: [AI回复]}，add_messages 自动追加到历史
    """
    # 在消息列表最前面插入系统提示词（每次调用都插在最前面）
    all_messages = [SystemMessage(content=MOCK_WEATHER_PROMPT)] + state["messages"]

    # 调用 LLM
    result = await llm.ainvoke(all_messages)

    # add_messages reducer 会自动把这条 AI 消息追加到历史中
    logger.info(f"天气助手回复完成，长度: {len(result.content)} 字，历史消息数: {len(state['messages'])}")
    return {"messages": [result]}


# ============================================================
# 5. 构建 Graph（节点 + 边 = 可执行工作流）
# ============================================================
builder = StateGraph(AgentState)
builder.add_node("weather", weather_node)
builder.add_edge(START, "weather")
builder.add_edge("weather", END)
graph: CompiledStateGraph = builder.compile()
