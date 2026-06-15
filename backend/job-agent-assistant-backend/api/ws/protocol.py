import json
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any

from pydantic import BaseModel


class MessageType(StrEnum):
    # 握手
    AUTH_SUCCESS = "auth.success"
    # 聊天
    CHAT_REQUEST = "chat.request"
    CHAT_STREAM = "chat.stream"
    CHAT_DONE = "chat.done"
    # 心跳
    PING = "ping"
    PONG = "pong"
    # 异常
    ERROR = "error"


class WSMessage(BaseModel):
    """WebSocket 统一消息协议"""
    type: MessageType
    id: str | None = None
    payload: Any = None

    def json(self) -> str:
        return json.dumps(
            {"type": self.type.value, "id": self.id, "payload": self.payload},
            ensure_ascii=False,
        )


def system_message(msg_type: MessageType, payload: Any = None) -> WSMessage:
    """快速构造系统消息"""
    return WSMessage(type=msg_type, payload=payload)


def stream_chunk(content: str) -> WSMessage:
    """快速构造流式输出片段"""
    return WSMessage(type=MessageType.CHAT_STREAM, payload={"content": content})
