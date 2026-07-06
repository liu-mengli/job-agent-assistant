import sys
from contextlib import asynccontextmanager

# Windows 下 psycopg 异步需要 SelectorEventLoop
if sys.platform == "win32":
    import asyncio
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from api.log import logger
from config import settings  # 确保 .env 在所有业务代码之前加载完毕

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from psycopg_pool import AsyncConnectionPool

from api.database import init_db, engine
from api.router import v1_router
from api.schemas.response import ApiResponse


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时：初始化数据库连接，创建表
    logger.info("应用启动，初始化数据库...")
    await init_db()
    logger.info("数据库初始化完成")

    # 创建 psycopg 异步连接池，供 AsyncPostgresSaver + RAG 检索使用
    pool = AsyncConnectionPool(settings.PG_URL, open=False)
    await pool.open()
    logger.info("AsyncConnectionPool 已创建")

    # 创建 resume_chunks 表（向量切片表，由 psycopg 管理）
    from api.rag.store import ensure_table
    await ensure_table(pool)

    # 预热 embedding 模型（首次自动下载 ~100MB）
    from api.rag.embedder import get_model
    get_model()
    logger.info(f"Embedding 模型已加载: {settings.EMBEDDING_MODEL}")

    # 初始化 Graph（含 AsyncPostgresSaver checkpointer + search_resume tool）
    from api.agent.graph import init_graph
    await init_graph(pool)

    yield

    # 关闭时：释放连接池和数据库连接
    logger.info("应用关闭，释放资源...")
    await pool.close()
    await engine.dispose()


# 创建 FastAPI 应用实例
app = FastAPI(title="Job Agent Assistant API", version="0.1.0", lifespan=lifespan)

# RequestId 中间件（必须最先注册，确保 request_id 覆盖所有请求）
from api.middleware import RequestIdMiddleware
app.add_middleware(RequestIdMiddleware)

# 配置 CORS 中间件，允许 Vue3 前端跨域访问
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# 请求参数校验失败（422 → 统一格式）
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = exc.errors()
    detail = "; ".join(f"{e['loc'][-1]}: {e['msg']}" for e in errors)
    logger.warning(f"参数校验失败 {request.method} {request.url.path}: {detail}")
    return JSONResponse(
        status_code=422,
        content=ApiResponse(code=422, message=detail).model_dump(),
    )


# 全局异常处理器，所有未捕获异常统一转换为 ApiResponse 格式
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.exception(f"未处理异常 {request.method} {request.url.path}: {exc}")
    return JSONResponse(
        status_code=500,
        content=ApiResponse(
            code=-1,
            message=str(exc),
        ).model_dump(),
    )


# 挂载 v1 路由聚合模块
app.include_router(v1_router)
