import json
from uuid import uuid4

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from langchain_core.messages import HumanMessage, AIMessage, AIMessageChunk

from api.agent.graph import graph
from api.log import logger
from api.security import decode_access_token
from api.ws.lock import agent_lock
from api.ws.manager import manager
from api.ws.protocol import MessageType, stream_chunk, system_message

router = APIRouter()


@router.websocket("/ws/chat")
async def websocket_chat(ws: WebSocket, token: str = Query(...)):
    ws_id = uuid4().hex[:8]

    # 1. 握手前校验 JWT
    try:
        user_id = decode_access_token(token)
    except Exception:
        logger.bind(request_id=ws_id).warning("WS 握手失败：Token 无效")
        await ws.close(code=4003, reason="Token 无效或已过期")
        return

    # 2. contextualize 让整个 WS 连接生命周期的日志都带 ws_id
    with logger.contextualize(request_id=ws_id):
        await manager.connect(user_id, ws)
        await manager.send_system(MessageType.AUTH_SUCCESS, user_id, payload={"user_id": user_id})
        logger.info(f"WS 连接建立 user={user_id} online={manager.online_count}")

        try:
            while True:
                raw = await ws.receive_text()

                # 3. JSON 反序列化
                try:
                    body = json.loads(raw)
                except json.JSONDecodeError:
                    logger.warning("WS 收到非 JSON 消息")
                    await manager.send_system(MessageType.ERROR, user_id, payload={"detail": "消息格式错误，需要 JSON"})
                    continue

                msg_type = body.get("type")
                payload = body.get("payload")

                # 4. 按消息类型分发
                if msg_type == MessageType.PING.value:
                    await manager.send_system(MessageType.PONG, user_id)

                elif msg_type == MessageType.CHAT_REQUEST.value:
                    content = payload.get("content", "") if payload else ""
                    raw_history = payload.get("messages", []) if payload else []

                    # --- 并发保护：同一用户同一时间只跑一个 Agent ---
                    if not await agent_lock.try_acquire(user_id):
                        logger.info(f"Agent 正忙，拒绝新请求: {content[:30]}...")
                        await manager.send_system(
                            MessageType.CHAT_BUSY, user_id,
                            payload={"detail": "正在处理上一条消息，请稍后再试。"},
                        )
                        continue

                    try:
                        logger.info(f"收到聊天消息: {content[:30]}... history_len={len(raw_history)}")

                        # 将前端传来的历史消息转为 LangChain 消息对象
                        history = []
                        for m in raw_history:
                            role = m.get("role", "")
                            content = m.get("content", "")
                            if not role or not content:
                                continue
                            if role == "user":
                                history.append(HumanMessage(content=content))
                            elif role == "assistant":
                                history.append(AIMessage(content=content))
                        # 追加本次用户输入
                        history.append(HumanMessage(content=content))

                        # 流式调用 Graph，stream_mode="messages" 抓取每个 token
                        # 用 send_json_to 绑定原始 ws，避免连接被顶替后 token 串到新 tab
                        streaming_ok = True
                        async for msg, _ in graph.astream(
                            {"messages": history},
                            stream_mode="messages",
                        ):
                            if isinstance(msg, AIMessageChunk) and msg.content:
                                ok = await manager.send_json_to(stream_chunk(msg.content), ws)
                                if not ok:  # 原始连接已断开（被踢或网络中断）
                                    logger.warning("WS 推送失败，终止流式输出")
                                    streaming_ok = False
                                    break

                        # 仅在流式完整结束时推送完成信号
                        if streaming_ok:
                            await manager.send_system(MessageType.CHAT_DONE, user_id)

                    except Exception:
                        logger.exception("聊天处理异常")
                        await manager.send_system(
                            MessageType.ERROR, user_id,
                            payload={"detail": "服务器处理请求时出错，请稍后重试。"},
                        )
                    finally:
                        agent_lock.release(user_id)

                else:
                    logger.warning(f"未知消息类型: {msg_type}")
                    await manager.send_system(MessageType.ERROR, user_id, payload={"detail": f"未知消息类型: {msg_type}"})

        except WebSocketDisconnect:
            pass
        finally:
            agent_lock.release(user_id)  # 断连时清理锁，防止泄漏
            manager.disconnect(user_id)
            logger.info(f"WS 连接断开 user={user_id} online={manager.online_count}")
