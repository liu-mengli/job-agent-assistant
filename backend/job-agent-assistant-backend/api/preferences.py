from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from api.database import get_db
from api.dependencies import get_current_user
from api.log import logger
from api.models.preference import UserPreference
from api.schemas.response import ApiResponse
from sqlalchemy import select

router = APIRouter()


class PreferenceRequest(BaseModel):
    city: str | None = Field(None, max_length=50)
    work_mode: str | None = Field(None, max_length=20)
    salary_min: int | None = None
    salary_max: int | None = None
    industry: str | None = Field(None, max_length=50)
    company_size: str | None = Field(None, max_length=20)
    tech_stack: str | None = Field(None, max_length=500)
    deal_breakers: str | None = Field(None, max_length=500)
    experience_years: int | None = None
    job_status: str | None = Field(None, max_length=50)


@router.get("/preferences", response_model=ApiResponse)
async def get_preferences(
    user_id: int = Depends(get_current_user),
    db=Depends(get_db),
):
    """获取当前用户的求职偏好"""
    result = await db.execute(
        select(UserPreference).where(UserPreference.user_id == user_id)
    )
    pref = result.scalar()
    if pref is None:
        return ApiResponse(data=None)

    return ApiResponse(data={
        "city": pref.city,
        "work_mode": pref.work_mode,
        "salary_min": pref.salary_min,
        "salary_max": pref.salary_max,
        "industry": pref.industry,
        "company_size": pref.company_size,
        "tech_stack": pref.tech_stack,
        "deal_breakers": pref.deal_breakers,
        "experience_years": pref.experience_years,
        "job_status": pref.job_status,
    })


@router.put("/preferences", response_model=ApiResponse)
async def save_preferences(
    body: PreferenceRequest,
    user_id: int = Depends(get_current_user),
    db=Depends(get_db),
):
    """保存或更新当前用户的求职偏好"""
    result = await db.execute(
        select(UserPreference).where(UserPreference.user_id == user_id)
    )
    pref = result.scalar()

    if pref is None:
        pref = UserPreference(user_id=user_id)
        db.add(pref)

    pref.city = body.city
    pref.work_mode = body.work_mode
    pref.salary_min = body.salary_min
    pref.salary_max = body.salary_max
    pref.industry = body.industry
    pref.company_size = body.company_size
    pref.tech_stack = body.tech_stack
    pref.deal_breakers = body.deal_breakers
    pref.experience_years = body.experience_years
    pref.job_status = body.job_status

    await db.commit()
    logger.info(f"用户偏好已更新 user={user_id}")
    return ApiResponse(message="已保存")
