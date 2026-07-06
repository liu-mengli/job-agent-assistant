"""
用户级 Agent 异步锁
===================
按 (user_id, session_id) 隔离，不同会话独立锁，同一用户不同 Tab 可并发跑 Agent。
同一会话同一时间只允许一个 Agent 在运行（streaming）。
"""
import asyncio


class UserAgentLock:
    """按 (user_id, session_id) 隔离的异步锁 + 单条排队"""

    def __init__(self):
        self._locks: dict[tuple[int, str], asyncio.Lock] = {}
        self._pending: dict[tuple[int, str], dict] = {}

    # ---------- 锁操作 ----------

    async def try_acquire(self, user_id: int, session_id: str) -> bool:
        """尝试获取锁，返回 True 表示拿到锁可以执行，False 表示正在忙"""
        key = (user_id, session_id)
        if key not in self._locks:
            self._locks[key] = asyncio.Lock()

        lock = self._locks[key]
        if lock.locked():
            return False
        await lock.acquire()
        return True

    def release(self, user_id: int, session_id: str):
        """释放锁，若锁不存在或未锁定则忽略"""
        key = (user_id, session_id)
        lock = self._locks.get(key)
        if lock and lock.locked():
            lock.release()

    # ---------- 排队操作 ----------

    def enqueue(self, user_id: int, session_id: str, request: dict):
        """存入排队请求，覆盖旧排队（只保留最新一条）"""
        self._pending[(user_id, session_id)] = request

    def dequeue(self, user_id: int, session_id: str) -> dict | None:
        """取出排队请求并清空，无排队返回 None"""
        return self._pending.pop((user_id, session_id), None)

    @property
    def is_pending(self, user_id: int, session_id: str) -> bool:
        """是否有排队中的请求"""
        return (user_id, session_id) in self._pending


# 模块级单例
agent_lock = UserAgentLock()
