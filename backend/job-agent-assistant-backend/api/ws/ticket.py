"""
WS 连接票据
===========
取代原来的 URL 传 JWT 方式，避免 Token 被浏览器历史/Nginx 日志明文记录。

流程：
1. 前端 POST /api/v1/ws/ticket（Header: Bearer <JWT>）→ 拿到一个随机 ticket
2. 前端 ws://.../ws/chat?ticket=xxx → 后端验票 → 得一 user_id → 立即销毁票据
3. ticket 的有效期只有 10 秒，且一票一用，用完即删
"""
import secrets
import time

from api.log import logger


class TicketStore:
    """内存中的一次性票据存储"""

    def __init__(self, ttl: int = 10):
        self._tickets: dict[str, tuple[int, float]] = {}  # ticket → (user_id, expires_at)
        self._ttl = ttl

    def create(self, user_id: int) -> str:
        """生成一张新票据，与 user_id 绑定，ttl 秒后自动过期"""
        self._cleanup()
        ticket = secrets.token_urlsafe(32)
        self._tickets[ticket] = (user_id, time.time() + self._ttl)
        logger.info(f"Ticket 已生成 user={user_id} ttl={self._ttl}s")
        return ticket

    def pop(self, ticket: str) -> int | None:
        """
        验证并消费票据。成功返回 user_id，失败返回 None。
        票据一旦 pop 即从存储中删除（一票一用）。
        """
        self._cleanup()
        entry = self._tickets.pop(ticket, None)
        if entry is None:
            return None
        user_id, expires_at = entry
        if time.time() > expires_at:
            logger.warning(f"Ticket 已过期 user={user_id}")
            return None
        logger.info(f"Ticket 验证通过 user={user_id}")
        return user_id

    def _cleanup(self):
        """清理过期票据（惰性触发：生成或验票时顺便清理）"""
        now = time.time()
        expired = [t for t, (_, exp) in self._tickets.items() if now > exp]
        for t in expired:
            self._tickets.pop(t, None)
        if expired:
            logger.debug(f"清理了 {len(expired)} 张过期票据")


# 模块级单例，ttl=10 秒
ticket_store = TicketStore(ttl=10)
