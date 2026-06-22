"""
LangGraph 求职助手 Agent
========================
用 Mock 岗位数据演示 Agent 的核心机制：
1. State  —— add_messages 自动拼接多轮对话历史
2. Node   —— LLM 调用节点（ainvoke / astream 统一用 astream 循环）
3. Edge   —— 节点连接方向
4. Graph  —— HTTP 用 ainvoke 一次性返回，WS 用 astream(stream_mode) 逐 token 推送
"""
from typing import Annotated

from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.graph.state import CompiledStateGraph
from typing_extensions import TypedDict

from api.log import logger
from config import settings


# ============================================================
# 工具函数：清洗 DeepSeek 响应中可能混入的 Unicode 代理字符
# ============================================================
def sanitize(text: str) -> str:
    """清洗文本中的非法代理字符（surrogate），防止 JSON 序列化/终端输出时崩溃"""
    return text.encode("utf-8", errors="replace").decode("utf-8")


# ============================================================
# 1. 定义 State
# ============================================================
class AgentState(TypedDict):
    messages: Annotated[list, add_messages]  # 多轮对话消息历史


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
# 3. Mock 岗位数据
# ============================================================
MOCK_JOB_PROMPT = """
你是一个专业的求职顾问 AI，掌握以下招聘岗位数据（仅限这 18 个岗位）。
当用户询问时，请基于数据回答，并给出求职建议。

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
"""

# 预清洗一次 prompt（消除 .py 文件保存时可能混入的代理字符）
MOCK_JOB_PROMPT = sanitize(MOCK_JOB_PROMPT)


# ============================================================
# 4. 节点函数
# ============================================================
async def job_advisor_node(state: AgentState) -> dict:
    """
    求职顾问节点：
    1. 从 State 中取出 messages（历史对话 + 最新用户消息）
    2. 在最前面插入系统提示词
    3. 清洗所有消息内容后调用 LLM
    4. 返回 {"messages": [AI回复]}，add_messages 自动追加到历史
    """
    full_messages = [SystemMessage(content=MOCK_JOB_PROMPT)] + state["messages"]

    # 清洗所有消息内容，防止代理字符导致 JSON 序列化崩溃
    safe_messages = []
    for m in full_messages:
        clean = sanitize(m.content)
        if isinstance(m, SystemMessage):
            safe_messages.append(SystemMessage(content=clean))
        elif isinstance(m, HumanMessage):
            safe_messages.append(HumanMessage(content=clean))
        elif isinstance(m, AIMessage):
            safe_messages.append(AIMessage(content=clean))
        else:
            logger.warning(f"未知消息类型 {type(m).__name__}，跳过")

    # 用 astream 逐 token 调用 LLM，收集完整回复
    # Graph 层通过 stream_mode="messages" 抓取每个 token 用于 WS 推送
    full_reply = ""
    async for chunk in llm.astream(safe_messages):
        if chunk.content:  # DeepSeek 偶有 content 为 None 的 chunk
            full_reply += chunk.content

    # state["messages"] 是节点输入（不含本条回复），+1 才是本轮后的总数
    logger.info(
        f"求职助手回复完成，长度: {len(full_reply)} 字，"
        f"本轮后消息总数: {len(state['messages']) + 1}"
    )
    return {"messages": [AIMessage(content=full_reply)]}


# ============================================================
# 5. 构建 Graph
# ============================================================
builder = StateGraph(AgentState)
builder.add_node("job_advisor", job_advisor_node)
builder.add_edge(START, "job_advisor")
builder.add_edge("job_advisor", END)
graph: CompiledStateGraph = builder.compile()
