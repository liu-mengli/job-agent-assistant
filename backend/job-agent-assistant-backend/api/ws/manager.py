from fastapi import WebSocket


class ConnectionManager:
    """管理活跃 WebSocket 连接，按 user_id 索引"""

    def __init__(self):
        self._connections: dict[int, WebSocket] = {}

    async def connect(self, user_id: int, ws: WebSocket):
        # 重复连接时先清理旧连接，避免僵尸连接泄漏
        old = self._connections.pop(user_id, None)
        if old:
            try:
                await old.close(code=1001, reason="新连接顶替")
            except Exception:
                pass

        await ws.accept()
        self._connections[user_id] = ws

    def disconnect(self, user_id: int):
        self._connections.pop(user_id, None)

    def is_connected(self, user_id: int) -> bool:
        return user_id in self._connections

    async def send_json(self, message, user_id: int):
        """向指定用户发送消息（带异常保护）"""
        ws = self._connections.get(user_id)
        if ws is None:
            return
        try:
            data = message if isinstance(message, str) else message.json()
            await ws.send_text(data)
        except Exception:
            self.disconnect(user_id)

    async def send_system(self, msg_type, user_id: int, payload=None):
        from api.ws.protocol import system_message
        await self.send_json(system_message(msg_type, payload), user_id)

    @property
    def online_count(self) -> int:
        return len(self._connections)


manager = ConnectionManager()
