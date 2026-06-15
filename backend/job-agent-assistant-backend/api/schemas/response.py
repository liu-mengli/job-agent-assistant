from typing import Any

from pydantic import BaseModel


class ApiResponse(BaseModel):
    """统一响应格式，所有接口返回值都用它包装"""
    code: int = 0
    data: Any = None
    message: str = "ok"
