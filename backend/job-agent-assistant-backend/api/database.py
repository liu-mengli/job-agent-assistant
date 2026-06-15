from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

from config import settings

# 异步引擎（echo=True 可在开发时打印 SQL）
engine = create_async_engine(settings.DATABASE_URL, echo=settings.DEBUG)

# 异步会话工厂
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


# 所有 ORM 模型继承这个基类
class Base(DeclarativeBase):
    pass


async def get_db():
    """FastAPI 依赖注入：每次请求获取一个数据库会话"""
    async with async_session() as session:
        yield session


async def init_db():
    """应用启动时创建所有表，并初始化默认管理员"""
    import api.models  # noqa: F401 确保所有模型被注册到 Base.metadata

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # 插入默认管理员账号（admin / 123456）
    from api.security import hash_password
    from api.models.user import User

    async with async_session() as session:
        existing = await session.get(User, 1)
        if existing is None:
            session.add(User(username="admin", password=hash_password("123456")))
            await session.commit()
