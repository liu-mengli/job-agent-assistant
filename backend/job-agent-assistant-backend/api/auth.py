from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import get_db
from api.dependencies import get_current_user
from api.models.user import User
from api.schemas.response import ApiResponse
from api.security import create_access_token, verify_password

router = APIRouter()


class LoginRequest(BaseModel):
    username: str
    password: str


@router.post("/auth/login", response_model=ApiResponse)
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    """从数据库校验账号密码，返回 Token"""
    result = await db.execute(
        select(User).where(User.username == body.username)
    )
    user = result.scalar_one_or_none()

    if user is None or not verify_password(body.password, user.password):
        return ApiResponse(code=401, message="账号或密码错误")

    token = create_access_token(user.id)
    return ApiResponse(data={"token": token})


@router.get("/auth/me", response_model=ApiResponse)
async def me(user_id: int = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """获取当前登录用户信息（需携带 Bearer Token）"""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    return ApiResponse(data={"id": user.id, "username": user.username})
