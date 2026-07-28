from fastapi import APIRouter, Depends
from sqlalchemy import select

from api.agent.graph import get_checkpoint_state
from api.agent.sql_graph import get_sql_checkpoint_state
from api.database import get_db
from api.dependencies import get_current_user
from api.log import logger
from api.models.session import Session
from api.schemas.response import ApiResponse

router = APIRouter()


@router.get("/sessions", response_model=ApiResponse)
async def list_sessions(
    user_id: int = Depends(get_current_user),
    agent_type: str = "",
    db=Depends(get_db),
):
    """当前用户的会话列表，可选按 agent_type 过滤（job_advisor / hr / kb）"""
    stmt = select(Session).where(Session.user_id == user_id)
    if agent_type:
        stmt = stmt.where(Session.agent_type == agent_type)
    stmt = stmt.order_by(Session.updated_at.desc())
    result = await db.execute(stmt)
    rows = result.scalars().all()
    return ApiResponse(data={
        "sessions": [
            {
                "session_id": s.session_id,
                "title": s.title,
                "agent_type": s.agent_type,
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

    # 按 agent_type 分发到对应 graph 的 checkpoint
    agent_type = getattr(session, "agent_type", None) or "job_advisor"
    if agent_type == "sql_agent":
        state = await get_sql_checkpoint_state(session_id)
    elif agent_type == "hr":
        from api.agent.hr_graph import get_hr_checkpoint_state
        state = await get_hr_checkpoint_state(session_id)
    elif agent_type == "kb":
        from api.agent.kb_graph import get_kb_checkpoint_state
        state = await get_kb_checkpoint_state(session_id)
    else:
        state = await get_checkpoint_state(session_id)
    messages = []
    if state and "messages" in state:
        for m in state["messages"]:
            role = getattr(m, "type", None) or "unknown"
            # 过滤内部消息：ToolMessage 和 SystemMessage 不展示给前端
            if role in ("tool", "system"):
                continue
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


@router.delete("/sessions/{session_id}", response_model=ApiResponse)
async def delete_session(
    session_id: str,
    user_id: int = Depends(get_current_user),
    db=Depends(get_db),
):
    """永久删除某个会话（sessions 记录 + checkpoint 状态）"""
    result = await db.execute(
        select(Session).where(
            Session.session_id == session_id,
            Session.user_id == user_id,
        )
    )
    session = result.scalar()
    if session is None:
        return ApiResponse(code=404, message="会话不存在")

    # 删除 LangGraph checkpoint 状态（3 张表，按 thread_id = session_id）
    from api.agent.graph import get_pool
    pool = get_pool()
    async with pool.connection() as conn:
        for table in ("checkpoint_writes", "checkpoint_blobs", "checkpoints"):
            await conn.execute(
                f"DELETE FROM {table} WHERE thread_id = %s",
                (session_id,),
            )

    await db.delete(session)
    await db.commit()
    logger.info(f"会话已删除 user={user_id} session={session_id}")
    return ApiResponse(message="已删除")


@router.get("/sessions/{session_id}/jobs", response_model=ApiResponse)
async def get_session_jobs(
    session_id: str,
    user_id: int = Depends(get_current_user),
    db=Depends(get_db),
):
    """获取某个会话的持久化岗位查询结果"""
    import json
    result = await db.execute(
        select(Session).where(
            Session.session_id == session_id,
            Session.user_id == user_id,
        )
    )
    session = result.scalar()
    if session is None:
        return ApiResponse(code=404, message="会话不存在")

    jobs = []
    if session.job_results:
        try:
            jobs = json.loads(session.job_results)
        except json.JSONDecodeError:
            pass
    return ApiResponse(data={"jobs": jobs})
