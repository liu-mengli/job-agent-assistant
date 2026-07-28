import json
import re
from uuid import uuid4

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, Depends
from langchain_core.messages import HumanMessage, AIMessageChunk

from sqlalchemy import select

from api.agent.graph import get_graph
from api.agent.hr_graph import get_hr_graph
from api.agent.sql_graph import get_sql_graph
from api.database import async_session
from api.dependencies import get_current_user
from api.log import logger
from api.models.session import Session
from api.schemas.response import ApiResponse
from api.ws.lock import agent_lock
from api.ws.manager import manager
from api.ws.protocol import MessageType, stream_chunk, system_message
from api.ws.ticket import ticket_store

router = APIRouter()

UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")


async def _upsert_session(user_id: int, session_id: str, content: str, agent_type: str = "job_advisor") -> None:
    """写入或更新会话索引记录（在 LLM 回复成功后调用）"""
    async with async_session() as db:
        result = await db.execute(
            select(Session).where(Session.session_id == session_id)
        )
        existing = result.scalar()
        if existing:
            from sqlalchemy import func
            existing.updated_at = func.now()
        else:
            title = content[:30] + ("..." if len(content) > 30 else "")
            db.add(Session(user_id=user_id, session_id=session_id, title=title, agent_type=agent_type))
        await db.commit()


async def _save_job_results(session_id: str, jobs: list) -> None:
    """持久化岗位查询结果到 sessions 表"""
    import json
    try:
        async with async_session() as db:
            result = await db.execute(
                select(Session).where(Session.session_id == session_id)
            )
            session = result.scalar()
            if session:
                session.job_results = json.dumps(jobs, ensure_ascii=False)
                await db.commit()
    except Exception:
        logger.exception("持久化岗位结果失败")


# ============================================================
# HTTP 端点：换取 WS 连接票据
# ============================================================
@router.post("/ws/ticket", response_model=ApiResponse)
async def create_ws_ticket(user_id: int = Depends(get_current_user)):
    """用 JWT 换取一次性 WS 连接票据（10 秒有效，用完即删）"""
    ticket = ticket_store.create(user_id)
    return ApiResponse(data={"ticket": ticket})


# ============================================================
# WS 端点
# ============================================================
@router.websocket("/ws/chat")
async def websocket_chat(
    ws: WebSocket,
    ticket: str = Query(...),
    session_id: str = Query(...),
):
    ws_id = uuid4().hex[:8]

    # 必须先 accept，否则连接断开时 receive_text 会抛 RuntimeError
    await ws.accept()

    # 校验 session_id 格式
    if not UUID_RE.match(session_id):
        logger.bind(request_id=ws_id).warning(f"WS 握手失败：session_id 格式无效 {session_id}")
        await ws.close(code=4003, reason="session_id 必须为标准 UUIDv4 格式")
        return

    # 1. 握手前校验票据（一票一用，pop 后立即作废）
    user_id = ticket_store.pop(ticket)
    if user_id is None:
        logger.bind(request_id=ws_id).warning("WS 握手失败：ticket 无效或已过期")
        await ws.close(code=4003, reason="ticket 无效或已过期")
        return

    # 2. contextualize 让整个 WS 连接生命周期的日志都带 request_id + session_id
    with logger.contextualize(request_id=ws_id, session_id=session_id):
        await manager.connect(user_id, session_id, ws)
        await manager.send_system(MessageType.AUTH_SUCCESS, user_id, session_id, payload={"user_id": user_id, "session_id": session_id})
        logger.info(f"WS 连接建立 user={user_id} session={session_id} online={manager.online_count}")

        try:
            while True:
                raw = await ws.receive_text()

                # 3. JSON 反序列化
                try:
                    body = json.loads(raw)
                except json.JSONDecodeError:
                    logger.warning("WS 收到非 JSON 消息")
                    await manager.send_system(MessageType.ERROR, user_id, session_id, payload={"detail": "消息格式错误，需要 JSON"})
                    continue

                msg_type = body.get("type")
                payload = body.get("payload")

                # 4. 按消息类型分发
                if msg_type == MessageType.PING.value:
                    await manager.send_system(MessageType.PONG, user_id, session_id)

                elif msg_type == MessageType.CHAT_REQUEST.value:
                    content = payload.get("content", "") if payload else ""
                    agent_type = payload.get("agent_type", "job_advisor") if payload else "job_advisor"

                    # --- 并发保护：同一会话同一时间只跑一个 Agent ---
                    if not await agent_lock.try_acquire(user_id, session_id):
                        logger.info(f"Agent 正忙，拒绝新请求: {content[:30]}...")
                        await manager.send_system(
                            MessageType.CHAT_BUSY, user_id, session_id,
                            payload={"detail": "正在处理上一条消息，请稍后再试。"},
                        )
                        continue

                    try:
                        logger.info(f"收到聊天消息: {content[:30]}...")

                        # 只需传入当前消息，LangGraph 通过 checkpointer
                        # 自动从 PG 恢复历史并 add_messages 合并
                        streaming_ok = True
                        tool_started = False
                        if agent_type == "hr":
                            graph = get_hr_graph()
                        elif agent_type == "kb":
                            from api.agent.kb_graph import get_kb_graph
                            graph = get_kb_graph()
                        elif agent_type == "sql_agent":
                            graph = get_sql_graph()
                        else:
                            graph = get_graph()
                        async for msg, _ in graph.astream(
                            {"messages": [HumanMessage(content=content)], "user_id": user_id},
                            stream_mode="messages",
                            config={"configurable": {"thread_id": session_id}},
                        ):
                            # 检测 LLM 决定调用工具，通知前端
                            if not tool_started and hasattr(msg, "tool_calls") and msg.tool_calls:
                                tool_started = True
                                if agent_type == "kb":
                                    tool_hint = "（正在检索知识库...）\n\n"
                                elif agent_type == "hr":
                                    tool_hint = "（正在检索简历...）\n\n"
                                elif agent_type == "sql_agent":
                                    tool_hint = "（正在查询数据库...）\n\n"
                                else:
                                    tool_hint = "（正在检索...）\n\n"
                                await manager.send_json_to(stream_chunk(tool_hint), ws)

                            if isinstance(msg, AIMessageChunk) and msg.content:
                                ok = await manager.send_json_to(stream_chunk(msg.content), ws)
                                if not ok:
                                    logger.warning("WS 推送失败，终止流式输出")
                                    streaming_ok = False
                                    break

                        # 流式结束：立即通知前端停止 loading
                        if streaming_ok:
                            await _upsert_session(user_id, session_id, content, agent_type)
                            await manager.send_system(MessageType.CHAT_DONE, user_id, session_id)

                            # 结构化输出异步提取（不阻塞前端，延迟推送）
                            try:
                                final_state = await graph.aget_state(
                                    {"configurable": {"thread_id": session_id}}
                                )
                                if final_state and final_state.values:
                                    structured = final_state.values.get("structured_content")
                                    sql_jobs = final_state.values.get("sql_jobs")
                                    logger.info(
                                        f"结构化输出合并: structured_jobs={len((structured.get('jobs') or [])) if isinstance(structured, dict) else 'N/A'}, "
                                        f"sql_jobs={len(sql_jobs) if sql_jobs else 'None'}"
                                    )
                                    if sql_jobs:
                                        merged_jobs = sql_jobs[:10]
                                        if isinstance(structured, dict):
                                            structured = {**structured, "jobs": merged_jobs, "all_jobs": sql_jobs}
                                        else:
                                            structured = {"response_type": "browse", "jobs": merged_jobs, "all_jobs": sql_jobs}
                                    if sql_jobs:
                                        await _save_job_results(session_id, sql_jobs)

                                    if structured and isinstance(structured, dict) and structured.get("response_type"):
                                        await manager.send_system(
                                            MessageType.CHAT_STRUCTURED, user_id, session_id,
                                            payload=structured,
                                        )
                            except Exception:
                                logger.exception("获取结构化输出失败")

                    except Exception:
                        logger.exception("聊天处理异常")
                        await manager.send_system(
                            MessageType.ERROR, user_id, session_id,
                            payload={"detail": "服务器处理请求时出错，请稍后重试。"},
                        )
                    finally:
                        agent_lock.release(user_id, session_id)

                else:
                    logger.warning(f"未知消息类型: {msg_type}")
                    await manager.send_system(MessageType.ERROR, user_id, session_id, payload={"detail": f"未知消息类型: {msg_type}"})

        except (WebSocketDisconnect, RuntimeError):
            pass
        finally:
            agent_lock.release(user_id, session_id)  # 断连时清理锁，防止泄漏
            manager.disconnect(user_id, session_id, ws)
            logger.info(f"WS 连接断开 user={user_id} session={session_id} online={manager.online_count}")
