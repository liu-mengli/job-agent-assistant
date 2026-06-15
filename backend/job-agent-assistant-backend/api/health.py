from fastapi import APIRouter
from api.schemas.response import ApiResponse

router = APIRouter()


@router.get("/health", response_model=ApiResponse)
def health_check():
    """健康检查接口"""
    return ApiResponse(data={"status": "OK"})
