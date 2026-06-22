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

    async def send_json(self, message, user_id: int) -> bool:
        """向指定用户发送消息（按 user_id 查找连接），返回 True 表示发送成功"""
        ws = self._connections.get(user_id)
        if ws is None:
            return False
        return await self._send_to_ws(message, ws, user_id)

    async def send_json_to(self, message, ws: WebSocket) -> bool:
        """向指定 WebSocket 对象发送消息（连接被顶替后不会发错对象）"""
        return await self._send_to_ws(message, ws, user_id=None)

    async def _send_to_ws(self, message, ws: WebSocket, user_id: int | None) -> bool:
        """底层发送，user_id 为 None 时不断开连接"""
        try:
            data = message if isinstance(message, str) else message.json()
            await ws.send_text(data)
            return True
        except Exception:
            if user_id is not None:
                self.disconnect(user_id)
            return False

    async def send_system(self, msg_type, user_id: int, payload=None):
        from api.ws.protocol import system_message
        await self.send_json(system_message(msg_type, payload), user_id)

    @property
    def online_count(self) -> int:
        return len(self._connections)


manager = ConnectionManager()
