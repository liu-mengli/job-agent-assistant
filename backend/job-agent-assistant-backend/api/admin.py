from fastapi import APIRouter, Depends
from sqlalchemy import text

from api.database import get_db, _cleanup_user_data
from api.dependencies import get_current_admin
from api.schemas.response import ApiResponse

router = APIRouter()


@router.get("/admin/users", response_model=ApiResponse)
async def list_users(
    admin_id: int = Depends(get_current_admin),
    db=Depends(get_db),
):
    """管理员查看所有普通用户列表（含明文密码，从注册日志读取）"""
    result = await db.execute(
        text(
            "SELECT u.id, u.username, u.role, r.password "
            "FROM users u "
            "LEFT JOIN registration_logs r ON r.username = u.username "
            "WHERE u.role IS NULL OR u.role != 'admin' "
            "ORDER BY u.id"
        )
    )
    users = [
        {
            "id": row[0],
            "username": row[1],
            "password": row[3] or "(注册日志缺失)",
            "role": row[2] or "user",
        }
        for row in result.fetchall()
    ]
    return ApiResponse(data={"users": users})


@router.delete("/admin/users/{user_id}", response_model=ApiResponse)
async def delete_user(
    user_id: int,
    admin_id: int = Depends(get_current_admin),
    db=Depends(get_db),
):
    """管理员删除普通用户及其所有关联数据"""
    if user_id == admin_id:
        return ApiResponse(code=400, message="不能删除自己的账号")

    # 检查目标用户是否存在且非管理员
    result = await db.execute(
        text("SELECT id, role FROM users WHERE id = :uid"), {"uid": user_id}
    )
    row = result.fetchone()
    if row is None:
        return ApiResponse(code=404, message="用户不存在")
    if row[1] == "admin":
        return ApiResponse(code=400, message="不能删除管理员账号")

    await _cleanup_user_data(db, user_id)
    await db.execute(text("DELETE FROM users WHERE id = :uid"), {"uid": user_id})
    await db.commit()

    return ApiResponse(message="已删除用户及其所有关联数据")
