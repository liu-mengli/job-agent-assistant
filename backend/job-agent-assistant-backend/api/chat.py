import time

from fastapi import APIRouter, Depends
from langchain_core.messages import HumanMessage, AIMessage
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from api.agent.graph import graph
from api.database import get_db
from api.dependencies import get_current_user
from api.log import logger
from api.schemas.response import ApiResponse

router = APIRouter()


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    input: str
    messages: list[ChatMessage] = []  # 前端传来的完整历史


@router.post("/chat", response_model=ApiResponse)
async def chat(
    body: ChatRequest,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """调用 LangGraph 求职助手，支持多轮对话"""
    start = time.time()

    # 将前端传来的完整历史转为 LangChain 消息对象
    history = []
    for m in body.messages:
        if m.role == "user":
            history.append(HumanMessage(content=m.content))
        elif m.role == "assistant":
            history.append(AIMessage(content=m.content))
    # 追加本次用户输入
    history.append(HumanMessage(content=body.input))

    result = await graph.ainvoke({"messages": history})
    reply = result["messages"][-1].content

    elapsed = (time.time() - start) * 1000
    logger.info(f"user={user_id} 提问: {body.input[:30]}... → 回复: {reply[:30]}... 耗时: {elapsed:.0f}ms")

    return ApiResponse(data={"reply": reply})
