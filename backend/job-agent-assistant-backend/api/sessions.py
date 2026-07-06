from fastapi import APIRouter, Depends
from sqlalchemy import select

from api.agent.graph import get_checkpoint_state
from api.database import get_db
from api.dependencies import get_current_user
from api.log import logger
from api.models.session import Session
from api.schemas.response import ApiResponse

router = APIRouter()


@router.get("/sessions", response_model=ApiResponse)
async def list_sessions(
    user_id: int = Depends(get_current_user),
    db=Depends(get_db),
):
    """当前用户的所有会话，按更新时间倒序"""
    result = await db.execute(
        select(Session)
        .where(Session.user_id == user_id)
        .order_by(Session.updated_at.desc())
    )
    rows = result.scalars().all()
    return ApiResponse(data={
        "sessions": [
            {
                "session_id": s.session_id,
                "title": s.title,
                "created_at": s.created_at.isoformat(),
                "updated_at": s.updated_at.isoformat(),
            }
            for s in rows
        ]
    })


@router.get("/sessions/{session_id}", response_model=ApiResponse)
async def get_session_messages(
    session_id: str,
    user_id: int = Depends(get_current_user),
    db=Depends(get_db),
):
    """获取某个会话的完整消息历史（从 checkpoint 反序列化）"""
    # 校验会话归属
    result = await db.execute(
        select(Session).where(
            Session.session_id == session_id,
            Session.user_id == user_id,
        )
    )
    session = result.scalar()
    if session is None:
        return ApiResponse(code=404, message="会话不存在")

    # 从 checkpoint 读取状态
    state = await get_checkpoint_state(session_id)
    messages = []
    if state and "messages" in state:
        for m in state["messages"]:
            role = getattr(m, "type", None) or "unknown"
            content = getattr(m, "content", "")
            if role == "human":
                role = "user"
            elif role == "ai":
                role = "assistant"
            messages.append({"role": role, "content": content})

    logger.info(f"user={user_id} 读取会话 {session_id}，消息数: {len(messages)}")
    return ApiResponse(data={
        "session_id": session_id,
        "title": session.title,
        "messages": messages,
    })
