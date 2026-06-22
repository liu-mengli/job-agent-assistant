"""
用户级 Agent 异步锁
===================
同一用户同一时间只允许一个 Agent 在运行（streaming）。
如果用户在前端快速点击发送，或网络延迟导致两条消息几乎同时到达：
- 第一条正常执行
- 第二条被排队（覆盖旧排队，只保留最新一条）
- 第一条完成后自动取出排队请求继续处理
"""
import asyncio


class UserAgentLock:
    """按 user_id 隔离的异步锁 + 单条排队"""

    def __init__(self):
        self._locks: dict[int, asyncio.Lock] = {}       # user_id → 协程锁
        self._pending: dict[int, dict] = {}             # user_id → 排队请求（只保留最新）

    # ---------- 锁操作 ----------

    async def try_acquire(self, user_id: int) -> bool:
        """
        尝试获取 user_id 对应的锁（检查 + 获取原子操作）。
        asyncio.Lock 不存在时自动创建。
        返回 True 表示拿到锁可以执行，False 表示正在忙。
        """
        if user_id not in self._locks:
            self._locks[user_id] = asyncio.Lock()

        lock = self._locks[user_id]
        # locked() 不 yield 控制权，acquire() 在未锁定时也不阻塞，
        # 两者之间无 await 点，在 asyncio 单线程模型下是原子的
        if lock.locked():
            return False
        await lock.acquire()
        return True

    def release(self, user_id: int):
        """释放锁，若锁不存在或未锁定则忽略"""
        lock = self._locks.get(user_id)
        if lock and lock.locked():
            lock.release()

    # ---------- 排队操作 ----------

    def enqueue(self, user_id: int, request: dict):
        """存入排队请求，覆盖旧排队（只保留最新一条）"""
        self._pending[user_id] = request

    def dequeue(self, user_id: int) -> dict | None:
        """取出排队请求并清空，无排队返回 None"""
        return self._pending.pop(user_id, None)

    @property
    def is_pending(self, user_id: int) -> bool:
        """是否有排队中的请求"""
        return user_id in self._pending


# 模块级单例
agent_lock = UserAgentLock()
