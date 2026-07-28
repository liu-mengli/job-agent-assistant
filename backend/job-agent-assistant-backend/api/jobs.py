import json
import re
from datetime import date

from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy import text

from api.database import get_db
from api.dependencies import get_current_user
from api.log import logger
from api.schemas.response import ApiResponse

router = APIRouter()


def _parse_company_info(raw: str) -> str:
    """从 公司基本信息 中提取公司名称（第一个非空词段）"""
    if not raw:
        return ""
    # 去掉 HTML 标签和多余空白
    clean = re.sub(r"<[^>]+>", " ", raw)
    clean = re.sub(r"\s+", " ", clean).strip()
    parts = clean.split()
    # 公司名通常是前 1-3 个词（后面是融资/规模/行业）
    if not parts:
        return ""
    # 取前几个词直到遇到融资/规模关键词
    stop_words = {"不需要融资", "已上市", "未融资", "天使轮", "A轮", "B轮", "C轮", "D轮",
                  "0-20人", "20-99人", "100-499人", "500-999人", "1000-9999人", "10000人以上",
                  "互联网", "计算机软件", "基金", "企业服务"}
    name_parts = []
    for p in parts:
        if p in stop_words:
            break
        name_parts.append(p)
    return "".join(name_parts) if name_parts else parts[0]


@router.post("/jobs/upload-json", response_model=ApiResponse)
async def upload_jobs_json(
    file: UploadFile = File(...),
    user_id: int = Depends(get_current_user),
    db=Depends(get_db),
):
    """上传 JSON 岗位文件，批量入库。重复岗位（同 title + url）更新状态为 update"""
    if not file.filename or not file.filename.lower().endswith(".json"):
        return ApiResponse(code=400, message="仅支持 JSON 文件")

    try:
        raw = await file.read()
        data = json.loads(raw)
        if not isinstance(data, list):
            return ApiResponse(code=400, message="JSON 必须是岗位数组")
    except json.JSONDecodeError as e:
        return ApiResponse(code=400, message=f"JSON 解析失败: {e}")

    today = date.today()
    new_count = 0
    update_count = 0

    for item in data:
        title = (item.get("职位") or "").strip()
        url = (item.get("页面网址") or "").strip()
        if not title:
            continue

        salary_range = (item.get("薪资范围") or "").strip()
        city = (item.get("城市") or "").strip()
        experience = (item.get("工作经验") or "").strip()
        education = (item.get("学历要求") or "").strip()
        benefits = (item.get("福利待遇") or "").strip()
        description = (item.get("职位描述") or "").strip()
        keywords = (item.get("职位关键词") or "").strip()
        company_info = _parse_company_info(item.get("公司基本信息") or "")
        company_link = (item.get("公司详情链接") or "").strip()
        address = (item.get("地图地址") or "").strip()
        established_date = (item.get("成立日期") or "").strip()
        registered_capital = (item.get("注册资金") or "").strip()

        # 查重（title + url）
        result = await db.execute(
            text("SELECT id FROM job_listings WHERE title = :t AND url = :u"),
            {"t": title, "u": url},
        )
        existing = result.fetchone()

        if existing:
            # 更新已有记录
            await db.execute(
                text("""
                    UPDATE job_listings SET
                      salary_range = :sr, city = :c, experience = :e, education = :ed,
                      benefits = :b, description = :d, keywords = :k, company_name = :cn,
                      company_link = :cl, address = :a, established_date = :est,
                      registered_capital = :rc, status = 'update', upload_date = :ud
                    WHERE id = :id
                """),
                {"sr": salary_range, "c": city, "e": experience, "ed": education,
                 "b": benefits, "d": description, "k": keywords, "cn": company_info,
                 "cl": company_link, "a": address, "est": established_date,
                 "rc": registered_capital, "ud": today, "id": existing[0]},
            )
            update_count += 1
        else:
            # 新增
            await db.execute(
                text("""
                    INSERT INTO job_listings
                      (title, salary_range, city, experience, education, benefits,
                       description, keywords, company_name, company_link, address,
                       established_date, registered_capital, url, status, upload_date)
                    VALUES
                      (:t, :sr, :c, :e, :ed, :b, :d, :k, :cn, :cl, :a,
                       :est, :rc, :u, 'new', :ud)
                """),
                {"t": title, "sr": salary_range, "c": city, "e": experience,
                 "ed": education, "b": benefits, "d": description, "k": keywords,
                 "cn": company_info, "cl": company_link, "a": address,
                 "est": established_date, "rc": registered_capital, "u": url, "ud": today},
            )
            new_count += 1

    await db.commit()
    logger.info(f"岗位入库完成 user={user_id} new={new_count} update={update_count}")
    return ApiResponse(data={"new": new_count, "update": update_count, "total": len(data)})
