import datetime

from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from api.database import Base


class RegistrationLog(Base):
    __tablename__ = "registration_logs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(nullable=False)
    password: Mapped[str] = mapped_column(nullable=False)  # 明文存储
    created_at: Mapped[datetime.datetime] = mapped_column(server_default=func.now())
