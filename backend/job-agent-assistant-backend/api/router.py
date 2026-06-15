from fastapi import APIRouter
from api.health import router as health_router
from api.auth import router as auth_router
from api.ws.chat import router as ws_router

# 汇总所有 v1 子路由
v1_router = APIRouter(prefix="/api/v1")
v1_router.include_router(health_router)
v1_router.include_router(auth_router)
v1_router.include_router(ws_router)
