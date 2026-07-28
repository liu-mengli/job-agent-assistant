from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from api.database import Base


class UserPreference(Base):
    """用户求职偏好 —— 每用户一行"""

    __tablename__ = "user_preferences"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, unique=True, index=True)

    city: Mapped[str | None] = mapped_column(String(50), nullable=True)
    salary_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    salary_max: Mapped[int | None] = mapped_column(Integer, nullable=True)
    job_keywords: Mapped[str | None] = mapped_column(String(50), nullable=True)
    experience_years: Mapped[str | None] = mapped_column(String(20), nullable=True)  # 下拉选项
    company_age: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 公司最低成立年限

    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
