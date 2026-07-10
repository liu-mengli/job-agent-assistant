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
    title: str = ""
    company: str = ""
    salary: str = ""
    experience: str = ""
    match_score: Optional[int] = None  # 0-100, 仅 full_recommendation 模式
    reason: str = ""


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
