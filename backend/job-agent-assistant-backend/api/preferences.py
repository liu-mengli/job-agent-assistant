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
    salary_min: int | None = None
    salary_max: int | None = None
    job_keywords: str | None = Field(None, max_length=50)
    experience_years: str | None = Field(None, max_length=20)
    company_age: int | None = None


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
        "salary_min": pref.salary_min,
        "salary_max": pref.salary_max,
        "job_keywords": pref.job_keywords,
        "experience_years": pref.experience_years,
        "company_age": pref.company_age,
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
    pref.salary_min = body.salary_min
    pref.salary_max = body.salary_max
    pref.job_keywords = body.job_keywords
    pref.experience_years = body.experience_years
    pref.company_age = body.company_age

    await db.commit()
    logger.info(f"用户偏好已更新 user={user_id}")
    return ApiResponse(message="已保存")
