from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from api.security import decode_access_token

security = HTTPBearer()


async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> int:
    """从请求头提取 Bearer Token，解析并返回 user_id；无效则返回 401"""
    try:
        return decode_access_token(credentials.credentials)["user_id"]
    except Exception:
        raise HTTPException(status_code=401, detail="Token 无效或已过期")


async def get_current_admin(credentials: HTTPAuthorizationCredentials = Depends(security)) -> int:
    """从请求头提取 Bearer Token，解析并校验管理员角色，返回 user_id"""
    try:
        payload = decode_access_token(credentials.credentials)
        if payload.get("role") != "admin":
            raise HTTPException(status_code=403, detail="需要管理员权限")
        return payload["user_id"]
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=401, detail="Token 无效或已过期")
