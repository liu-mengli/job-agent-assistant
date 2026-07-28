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


async def _cleanup_user_data(session, user_id: int) -> None:
    """删除用户关联的所有数据：会话 + checkpoint + 简历 + 偏好 + 注册日志"""
    import os
    from sqlalchemy import text

    # 1. 获取用户所有会话的 session_id，用于清理 checkpoint
    result = await session.execute(
        text("SELECT session_id FROM sessions WHERE user_id = :uid"), {"uid": user_id}
    )
    session_ids = [row[0] for row in result.fetchall()]

    # 2. 清理 checkpoint（按 thread_id = session_id）
    if session_ids:
        for table in ("checkpoint_writes", "checkpoint_blobs", "checkpoints"):
            await session.execute(
                text(f"DELETE FROM {table} WHERE thread_id = ANY(:sids)"),
                {"sids": session_ids},
            )

    # 3. 删除会话记录
    await session.execute(text("DELETE FROM sessions WHERE user_id = :uid"), {"uid": user_id})

    # 4. 删除简历切片 + 磁盘文件
    result = await session.execute(
        text("SELECT id, file_path FROM resume_documents WHERE user_id = :uid"), {"uid": user_id}
    )
    resume_rows = result.fetchall()
    for row in resume_rows:
        doc_id, file_path = row[0], row[1]
        await session.execute(text("DELETE FROM resume_chunks WHERE document_id = :did"), {"did": doc_id})
        if file_path:
            disk_path = os.path.join("uploads/resumes", file_path)
            if os.path.exists(disk_path):
                os.remove(disk_path)
    await session.execute(text("DELETE FROM resume_documents WHERE user_id = :uid"), {"uid": user_id})

    # 5. 删除用户偏好
    await session.execute(text("DELETE FROM user_preferences WHERE user_id = :uid"), {"uid": user_id})

    # 6. 删除注册日志
    await session.execute(text("DELETE FROM registration_logs WHERE username = (SELECT username FROM users WHERE id = :uid)"), {"uid": user_id})


async def init_db():
    """应用启动时创建所有表，并初始化默认管理员"""
    import api.models  # noqa: F401 确保所有模型被注册到 Base.metadata

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # 为已有 sessions 表补充 agent_type 列（SQLAlchemy create_all 不修改已有表）
        await conn.run_sync(
            lambda c: c.exec_driver_sql(
                "ALTER TABLE sessions ADD COLUMN IF NOT EXISTS agent_type "
                "VARCHAR(20) NOT NULL DEFAULT 'job_advisor'"
            )
        )
        # 为已有 resume_documents 表补充 file_path 列
        await conn.run_sync(
            lambda c: c.exec_driver_sql(
                "ALTER TABLE resume_documents ADD COLUMN IF NOT EXISTS file_path "
                "VARCHAR(500)"
            )
        )
        # 偏好表精简：industry → job_keywords，删除 work_mode / deal_breakers
        await conn.run_sync(
            lambda c: c.exec_driver_sql(
                "ALTER TABLE user_preferences ADD COLUMN IF NOT EXISTS job_keywords VARCHAR(50)"
            )
        )
        await conn.run_sync(
            lambda c: c.exec_driver_sql(
                "DO $$ BEGIN"
                " IF EXISTS (SELECT 1 FROM information_schema.columns"
                " WHERE table_name='user_preferences' AND column_name='industry') THEN"
                " UPDATE user_preferences SET job_keywords = industry WHERE job_keywords IS NULL;"
                " ALTER TABLE user_preferences DROP COLUMN industry;"
                " END IF;"
                " END $$"
            )
        )
        await conn.run_sync(
            lambda c: c.exec_driver_sql(
                "ALTER TABLE user_preferences DROP COLUMN IF EXISTS work_mode"
            )
        )
        await conn.run_sync(
            lambda c: c.exec_driver_sql(
                "ALTER TABLE user_preferences DROP COLUMN IF EXISTS deal_breakers"
            )
        )
        # 偏好表：experience_years int → varchar，新增 company_age，删除废弃列
        await conn.run_sync(
            lambda c: c.exec_driver_sql(
                "ALTER TABLE user_preferences ADD COLUMN IF NOT EXISTS company_age INTEGER"
            )
        )
        await conn.run_sync(
            lambda c: c.exec_driver_sql(
                "ALTER TABLE user_preferences ALTER COLUMN experience_years TYPE VARCHAR(20)"
            )
        )
        await conn.run_sync(
            lambda c: c.exec_driver_sql(
                "ALTER TABLE user_preferences DROP COLUMN IF EXISTS company_size"
            )
        )
        await conn.run_sync(
            lambda c: c.exec_driver_sql(
                "ALTER TABLE user_preferences DROP COLUMN IF EXISTS tech_stack"
            )
        )
        await conn.run_sync(
            lambda c: c.exec_driver_sql(
                "ALTER TABLE user_preferences DROP COLUMN IF EXISTS job_status"
            )
        )
        # sessions 表补充 job_results 列（持久化岗位查询结果）
        await conn.run_sync(
            lambda c: c.exec_driver_sql(
                "ALTER TABLE sessions ADD COLUMN IF NOT EXISTS job_results TEXT"
            )
        )
        # 启用 pgvector 扩展（job_listings / resume_chunks / knowledge_chunks 依赖 vector 类型）
        await conn.run_sync(
            lambda c: c.exec_driver_sql("CREATE EXTENSION IF NOT EXISTS vector")
        )
        # job_listings 表 — 非 ORM 模型，手动建表
        await conn.run_sync(
            lambda c: c.exec_driver_sql(
                "CREATE TABLE IF NOT EXISTS job_listings ("
                "  id SERIAL PRIMARY KEY,"
                "  title VARCHAR(500) NOT NULL,"
                "  salary_range VARCHAR(100),"
                "  city VARCHAR(100),"
                "  experience VARCHAR(100),"
                "  education VARCHAR(100),"
                "  benefits TEXT,"
                "  description TEXT,"
                "  keywords VARCHAR(500),"
                "  company_name VARCHAR(500),"
                "  company_link VARCHAR(500),"
                "  address VARCHAR(500),"
                "  established_date VARCHAR(200),"
                "  registered_capital VARCHAR(200),"
                "  url VARCHAR(500),"
                "  embedding vector(512),"
                "  status VARCHAR(20) DEFAULT 'new',"
                "  upload_date DATE DEFAULT CURRENT_DATE"
                ")"
            )
        )
        # job_listings 表补充 status / upload_date 列，加唯一索引防重复
        await conn.run_sync(
            lambda c: c.exec_driver_sql(
                "ALTER TABLE job_listings ADD COLUMN IF NOT EXISTS status VARCHAR(20) DEFAULT 'new'"
            )
        )
        await conn.run_sync(
            lambda c: c.exec_driver_sql(
                "ALTER TABLE job_listings ADD COLUMN IF NOT EXISTS upload_date DATE DEFAULT CURRENT_DATE"
            )
        )
        # 已有数据：更新日期和状态
        await conn.run_sync(
            lambda c: c.exec_driver_sql(
                "UPDATE job_listings SET upload_date = '2026-07-21', status = 'new' "
                "WHERE upload_date IS NULL OR status IS NULL"
            )
        )

    # 插入默认管理员账号
    from api.security import hash_password
    from api.models.user import User

    async with async_session() as session:
        # 确保 role 列存在（旧表迁移）
        from sqlalchemy import text
        await session.execute(
            text("ALTER TABLE users ADD COLUMN IF NOT EXISTS role VARCHAR(20) DEFAULT 'user'")
        )
        await session.commit()

        # 仅首次启动时创建默认管理员账号
        admin_accounts = [
            ("admin", "qqnanwang"),
            ("admin1", "qqnanwang"),
            ("admin2", "qqnanwang"),
        ]
        for uname, pwd in admin_accounts:
            existing = await session.execute(
                text("SELECT id FROM users WHERE username = :uname"), {"uname": uname}
            )
            if existing.scalar() is None:
                session.add(User(username=uname, password=hash_password(pwd), role="admin"))
        await session.commit()
