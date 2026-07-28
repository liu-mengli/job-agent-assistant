from fastapi import WebSocket


class ConnectionManager:
    """管理活跃 WebSocket 连接，按 (user_id, session_id) 索引"""

    def __init__(self):
        self._connections: dict[tuple[int, str], WebSocket] = {}

    async def connect(self, user_id: int, session_id: str, ws: WebSocket):
        # 旧连接不主动踢除，让它自然超时断开，避免连锁重连
        key = (user_id, session_id)
        self._connections[key] = ws

    def disconnect(self, user_id: int, session_id: str, ws: WebSocket):
        """仅在字典中的连接与 ws 是同一对象时才移除（防止僵尸连接误删）"""
        key = (user_id, session_id)
        if self._connections.get(key) is ws:
            self._connections.pop(key, None)

    def is_connected(self, user_id: int, session_id: str) -> bool:
        return (user_id, session_id) in self._connections

    async def send_json(self, message, user_id: int, session_id: str) -> bool:
        """向指定会话发送消息，返回 True 表示发送成功"""
        ws = self._connections.get((user_id, session_id))
        if ws is None:
            return False
        return await self._send_to_ws(message, ws, user_id, session_id)

    async def send_json_to(self, message, ws: WebSocket) -> bool:
        """向指定 WebSocket 对象发送消息（连接被顶替后不会发错对象）"""
        return await self._send_to_ws(message, ws, user_id=None, session_id=None)

    async def _send_to_ws(self, message, ws: WebSocket, user_id: int | None, session_id: str | None) -> bool:
        """底层发送，user_id/session_id 为 None 时不断开连接"""
        try:
            data = message if isinstance(message, str) else message.json()
            await ws.send_text(data)
            return True
        except Exception:
            if user_id is not None and session_id is not None:
                self.disconnect(user_id, session_id, ws)
            return False

    async def send_system(self, msg_type, user_id: int, session_id: str, payload=None):
        from api.ws.protocol import system_message
        await self.send_json(system_message(msg_type, payload), user_id, session_id)

    @property
    def online_count(self) -> int:
        return len(self._connections)


manager = ConnectionManager()
