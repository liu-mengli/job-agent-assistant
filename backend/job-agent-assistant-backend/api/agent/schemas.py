"""
结构化响应 Pydantic 模型
======================
format_response_node 使用 with_structured_output(method="json_mode") 时，
LangChain 会自动将模型 schema 注入 prompt 引导 LLM 输出对应 JSON。
"""

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class JobItem(BaseModel):
    model_config = ConfigDict(extra="ignore")

    rank: int = 0
    title: Optional[str] = None
    company: Optional[str] = None
    salary: Optional[str] = None
    experience: Optional[str] = None
    match_score: Optional[int] = None  # 0-100, 仅 full_recommendation 模式
    reason: Optional[str] = None
    company_years: Optional[str] = None  # 公司成立年限，如 "5.3" 或 "-"


class SkillComparison(BaseModel):
    model_config = ConfigDict(extra="ignore")

    requirement: str = ""
    match_level: Literal["match", "partial", "missing"] = "match"
    your_status: str = ""
    note: str = ""


class StructuredResponse(BaseModel):
    """所有响应类型的超集，字段全可选 + ignore extra，兼容 DeepSeek json_mode"""

    model_config = ConfigDict(extra="ignore")

    response_type: Literal[
        "greeting",
        "browse",
        "full_recommendation",
        "match_analysis",
        "resume_optimization",
        "resume_analysis",
        "skill_analysis",
        "project_analysis",
        "kb_text",
        "general",
    ] = "general"

    # 共用
    summary: Optional[str] = None
    content: Optional[str] = None

    # browse / full_recommendation
    jobs: Optional[list[JobItem]] = None
    assessment: Optional[str] = None
    next_steps: Optional[str] = None

    # match_analysis
    overall_match: Optional[int] = None
    match_summary: Optional[str] = None
    skill_comparisons: Optional[list[SkillComparison]] = None
    strengths: Optional[list[str]] = None
    weaknesses: Optional[list[str]] = None
    application_advice: Optional[str] = None

    # resume_optimization
    highlights: Optional[list[dict]] = None        # [{original, suggestion}]
    keywords_to_add: Optional[list[dict]] = None    # [{keyword, importance: core|nice}]
    improvements: Optional[list[dict]] = None       # [{current, suggestion}]
    to_remove: Optional[list[str]] = None
    example_revision: Optional[dict] = None         # {before, after}

    # greeting / self-intro
    greeting_short: Optional[str] = None
    greeting_standard: Optional[str] = None
    self_intro: Optional[str] = None
    advantage_lines: Optional[list[str]] = None

    # resume_analysis
    basic_info: Optional[dict] = None
    skill_matrix: Optional[list[dict]] = None
    projects: Optional[list[dict]] = None
    positioning: Optional[str] = None

    # general / fallback
    suggestions: Optional[list[str]] = None
    guidance_tip: Optional[str] = None


# ------------------------------------------------------------
# 快速提取：从 LLM 回复文本末尾提取 JSON
# ------------------------------------------------------------
import re as _re

_JSON_TAIL_RE = _re.compile(r'\n?\{\s*"response_type"\s*:', _re.DOTALL)


def extract_structured_json(text: str) -> StructuredResponse | None:
    """从 LLM 回复末尾提取结构化 JSON（快速路径，避免二次 LLM 调用）。

    主 LLM 常在回复末尾附带 JSON 数据块，可直接解析为 StructuredResponse，
    无需再调用 format LLM。提取失败返回 None，由调用方走 LLM 回退。
    """
    from api.log import logger

    m = _JSON_TAIL_RE.search(text)
    if not m:
        return None
    json_str = text[m.start():].strip()
    # 去掉 markdown 代码块包裹（开头的 ```json 和结尾的 ```）
    if json_str.startswith("```"):
        json_str = json_str.split("```", 1)[-1]  # 去掉开头的 ```
    json_str = json_str.lstrip("json").strip()  # 去掉可能的 json 标记
    if json_str.endswith("```"):
        json_str = json_str.rsplit("```", 1)[0]  # 去掉结尾的 ```
    # 只取第一个完整的 JSON 对象
    import json as _json
    decoder = _json.JSONDecoder()
    try:
        data, end = decoder.raw_decode(json_str)
    except _json.JSONDecodeError as e:
        logger.warning(f"[FastExtract] JSON 解析失败: {e}，原始文本: {json_str[:200]}")
        return None
    try:
        return StructuredResponse(**data)
    except Exception as e:
        logger.warning(f"[FastExtract] Pydantic 校验失败: {e}")
        return None
