from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from api.database import Base


class Session(Base):
    """用户会话索引表。

    隐式映射关系：
    - sessions.session_id ←→ checkpoints.thread_id（同一 UUID，代码层保证一致）
    - 由 ws/chat.py 的 _upsert_session() 和 graph.astream(config={"thread_id": session_id}) 共用
    - 不设外键约束：checkpoint 表由 AsyncPostgresSaver.setup() 独立管理，防止 LangGraph 升级时断裂
    - agent_type 区分不同 Agent 页面（job_advisor / hr / kb）
    """

    __tablename__ = "sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    session_id: Mapped[str] = mapped_column(String(36), unique=True, nullable=False)
    agent_type: Mapped[str] = mapped_column(String(20), default="job_advisor", nullable=False)
    title: Mapped[str] = mapped_column(String(100), default="新对话")
    job_results: Mapped[str | None] = mapped_column(String, nullable=True)  # JSON 岗位查询结果
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
