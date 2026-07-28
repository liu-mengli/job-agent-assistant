from fastapi import APIRouter
from api.health import router as health_router
from api.auth import router as auth_router
from api.ws.chat import router as ws_router
from api.chat import router as chat_router
from api.sessions import router as sessions_router
from api.resumes import router as resumes_router
from api.preferences import router as preferences_router
from api.knowledge import router as knowledge_router
from api.jobs import router as jobs_router
from api.admin import router as admin_router

# 汇总所有 v1 子路由
v1_router = APIRouter(prefix="/api/v1")
v1_router.include_router(health_router)
v1_router.include_router(auth_router)
v1_router.include_router(ws_router)
v1_router.include_router(chat_router)
v1_router.include_router(sessions_router)
v1_router.include_router(resumes_router)
v1_router.include_router(preferences_router)
v1_router.include_router(knowledge_router)
v1_router.include_router(jobs_router)
v1_router.include_router(admin_router)
