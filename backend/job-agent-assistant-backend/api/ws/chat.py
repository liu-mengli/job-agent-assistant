import asyncio
import json
from uuid import uuid4

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query

from api.log import logger
from api.security import decode_access_token
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
                    logger.info(f"收到聊天消息: {content[:20]}...")
                    reply = f"收到消息：{content}。当前在线：{manager.online_count} 人。Agent 模块接入后我会更智能。"
                    for i in range(0, len(reply), 3):
                        await manager.send_json(stream_chunk(reply[i:i + 3]), user_id)
                        await asyncio.sleep(0.05)
                    await manager.send_system(MessageType.CHAT_DONE, user_id)

                else:
                    logger.warning(f"未知消息类型: {msg_type}")
                    await manager.send_system(MessageType.ERROR, user_id, payload={"detail": f"未知消息类型: {msg_type}"})

        except WebSocketDisconnect:
            pass
        finally:
            manager.disconnect(user_id)
            logger.info(f"WS 连接断开 user={user_id} online={manager.online_count}")
