"""
LangGraph SQL Agent —— 结构化岗位查询
=======================================
用户自然语言 → LLM 生成 SELECT → 校验（只读/白名单/无 user_id）→ 执行 → 失败重试一轮 → 结果解释 + 结构化输出

两种调用方式：
1. 独立模式：前端 WS 发送 agent_type='sql_agent'
2. 子 Agent 模式：求职 Agent 的 delegate_to_sql_agent 工具内部 ainvoke
"""

import re
from typing import Annotated

from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.graph.state import CompiledStateGraph
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool
from pydantic import BaseModel, Field
from typing_extensions import TypedDict

from api.agent.schemas import StructuredResponse, JobItem
from api.log import logger
from config import settings

_pool: AsyncConnectionPool | None = None


def get_pool() -> AsyncConnectionPool:
    if _pool is None:
        raise RuntimeError("Pool 尚未初始化")
    return _pool


# ============================================================
# State
# ============================================================
class SQLAgentState(TypedDict):
    messages: Annotated[list, add_messages]
    user_id: int
    sql_query: str | None
    sql_error: str | None
    retry_count: int
    query_results: list[dict] | None
    structured_content: dict | None


# ============================================================
# LLM
# ============================================================
SQL_GENERATOR_PROMPT = """你是一个 PostgreSQL 查询生成器。根据用户的自然语言描述，生成一条针对 job_listings 表的只读 SELECT 语句。

## 表结构（job_listings）

| 列名 | 类型 | 含义 | 示例值 |
|------|------|------|--------|
| id | INTEGER | 主键 | 1 |
| title | TEXT | 职位名称 | 「AI Agent 研发工程师」 |
| salary_range | TEXT | 薪资范围 | 「15-25K」「10-15K」「面议」 |
| city | TEXT | 工作城市 | 「苏州」 |
| experience | TEXT | 经验要求 | 「1-3年」「3-5年」「经验不限」「在校/应届」「1年以内」「5-10年」 |
| education | TEXT | 学历要求 | 「本科」「硕士」「大专」「学历不限」 |
| benefits | TEXT | 福利（长文本） | 「五险一金 年终奖 ...」 |
| description | TEXT | 职位描述（长文本） | |
| keywords | TEXT | 技术关键词 | 「Python JAVA C++ RAG FastAPI」 |
| company_name | TEXT | 公司名称 | 「北觅科技」 |
| url | TEXT | 岗位链接 | |
| established_date | TEXT | 公司成立日期 | 「2023-11-24」可为空 |
| status | TEXT | 数据状态 | 「new」= 新入库，「update」= 更新 |
| upload_date | DATE | 数据上传日期 | 「2026-07-21」 |

## 强制约束（必须严格遵守，每条 SQL 都要加）

**所有查询必须加以下 WHERE 条件，只查当天新数据：**
```sql
WHERE status = 'new' AND upload_date = CURRENT_DATE
```
其他筛选条件（城市、薪资、经验等）用 AND 追加在此条件之后。

## 数据解析规则

### 关键原则：WHERE 条件中绝不要直接 CAST(experience AS INTEGER) 或 CAST(salary_range AS INTEGER)
salary_range 和 experience 列中有非数值文本（「面议」「经验不限」「学历不限」等），直接 CAST 会报错。
**必须在 CAST 前用 NULLIF 或正则过滤掉非数值行，或把解析逻辑放到子查询/CTE 中用 CASE WHEN 安全处理。**

### salary_range → 数值工资（用在 CTE/子查询中，然后外层 WHERE）
salary_range 是文本格式，如「15-25K」「10K-15K」「面议」。安全提取：
```sql
WITH parsed AS (
  SELECT *,
    CASE WHEN salary_range ~ '^[0-9]+'
      THEN CAST(split_part(salary_range, '-', 1) AS INTEGER) * 1000
    END AS salary_min
  FROM job_listings
)
SELECT * FROM parsed WHERE ...
```
**过滤薪资时，对于「面议」等无法解析的值，salary_min 为 NULL，不要让它们被错误排除。**

### experience → 年份（用在 CTE 中，同时提取上下限）
```sql
CASE
  WHEN experience = '经验不限' OR experience IS NULL THEN NULL
  WHEN experience = '在校/应届' THEN 0
  WHEN experience = '1年以内' THEN 1
  WHEN experience ~ '^[0-9]+-[0-9]+' THEN CAST(split_part(experience, '-', 1) AS INTEGER)
  ELSE NULL
END AS exp_min_years,
CASE
  WHEN experience = '经验不限' OR experience IS NULL THEN NULL
  WHEN experience = '在校/应届' THEN 1
  WHEN experience = '1年以内' THEN 1
  WHEN experience ~ '^[0-9]+-[0-9]+' THEN CAST(regexp_replace(split_part(experience, '-', 2), '[^0-9]', '', 'g') AS INTEGER)
  ELSE NULL
END AS exp_max_years
```
**「经验不限」的岗位 exp_min/exp_max 都为 NULL，在 WHERE 条件中应允许通过（IS NULL OR ...）。**

### education → 学历匹配
education 的值为「学历不限」「大专」「本科」「硕士」。匹配时用 `=` 精确匹配，但「学历不限」要允许通过：
```sql
AND (education = '本科' OR education = '学历不限')
```

## 查询条件优先级（必须严格遵守）

1. **用户当前提问中明确指定的条件**——优先级最高，不能被偏好覆盖
2. **用户偏好设置**——如果查询未指定该维度，使用偏好中的默认值
3. **对话历史上下文**——仅在前两级都没有指定时使用

## 安全约束（必须严格遵守）

- 只允许 SELECT 语句
- 只允许查询 job_listings 表（不允许关联其他表）
- WHERE 条件中绝对不能出现 user_id
- **必须包含 WHERE status = 'new' AND upload_date = CURRENT_DATE**，不限制返回条数

## 生成原则

1. **必须使用 CTE（WITH 子句）做薪资/经验解析**，不要在主查询里直接 CAST
2. 关键字搜索使用 `title ILIKE '%关键字%' OR keywords ILIKE '%关键字%'`
3. 多个条件用 AND 连接，但**不要过于严格**——宁可多返回结果让用户筛选
4. **经验筛选规则**（用户偏好设了经验年限时，按以下映射匹配，只保留对应的 experience 值）：
   | 用户经验 | 匹配 experience 值 |
   |---------|------------------|
   | 在校/应届 | `experience IN ('在校/应届', '1年以内', '经验不限')` |
   | 1年以内 | `experience IN ('1年以内', '1-3年', '经验不限')` |
   | 1-3年 | `experience IN ('1-3年', '3-5年', '经验不限')` |
   | 3-5年 | `experience IN ('1-3年', '3-5年', '经验不限')` |
   | 5-10年 | `experience IN ('3-5年', '5-10年', '经验不限')` |
   | 10年以上 | `experience IN ('5-10年', '10年以上', '经验不限')` |
   未设置时不加经验筛选。

5. **薪资筛选规则**（用户提到期望薪资时）：
   - 只提取 salary_max 用于筛选：`CASE WHEN salary_range ~ '^[0-9]+' THEN CAST(regexp_replace(split_part(salary_range, '-', 2), '[^0-9]', '', 'g') AS INTEGER) * 1000 END AS salary_max`
   - 筛选条件：`AND (salary_max IS NULL OR salary_max >= {用户最低薪资})`
     含义：岗位薪资上限能覆盖用户的最低期望，面议的保留

6. **薪资范围筛选规则**（用户提到薪资范围如13K-16K时）：
   - 提取 salary_min 和 salary_max，筛选岗位薪资与用户期望有交集：
     `AND (salary_max IS NULL OR (salary_min <= {用户上限} AND salary_max >= {用户下限}))`
   - 简单处理：只用用户下限过滤 `AND (salary_max IS NULL OR salary_max >= {用户下限})`

7. **公司成立年限筛选规则**（用户偏好设了 company_age 时）：
   - established_date 是文本字段，值为空或空白时跳过该记录
   - 解析：`CAST(NULLIF(established_date, '') AS DATE)`
   - 计算成立年限：`(CURRENT_DATE - CAST(established_date AS DATE))::float / 365.0`
   - 筛选条件：`AND established_date IS NOT NULL AND established_date != '' AND (CURRENT_DATE - CAST(established_date AS DATE))::float / 365.0 > {company_age}`
   - 未设置 company_age 时不加此筛选
   - CTE 中提取：`(CURRENT_DATE - CAST(NULLIF(established_date, '') AS DATE))::float / 365.0 AS company_years`，NULL 时前端显示「-」

8. 无条件查询时只加强制约束：`WHERE status = 'new' AND upload_date = CURRENT_DATE`，不额外加筛选条件
9. 不限制返回条数（不要加 LIMIT）
10. SELECT 默认输出列（在 CTE 外层）：title, salary_range, city, experience, education, company_name, keywords, description（前120字符）, url, 以及 company_years

## 输出格式

用 JSON 格式输出：
```json
{"sql": "SELECT ... FROM job_listings WHERE status = 'new' AND upload_date = CURRENT_DATE ...", "explanation": "这段 SQL 查询了当天新入库的岗位..."}
```"""


class SQLOutput(BaseModel):
    sql: str = Field(description="生成的 PostgreSQL SELECT 查询语句")
    explanation: str = Field(description="对这条 SQL 的简短解释")


sql_llm = ChatOpenAI(
    model=settings.DEEPSEEK_MODEL,
    api_key=settings.DEEPSEEK_API_KEY,
    base_url=settings.DEEPSEEK_BASE_URL,
    temperature=0,
    request_timeout=30,
    extra_body={"ep_enable_prompt_caching": True},
)

sql_structured_llm = sql_llm.with_structured_output(SQLOutput, method="json_mode")

# 格式化 LLM（用于最终自然语言总结）
format_llm = ChatOpenAI(
    model=settings.DEEPSEEK_MODEL,
    api_key=settings.DEEPSEEK_API_KEY,
    base_url=settings.DEEPSEEK_BASE_URL,
    temperature=0,
    request_timeout=15,
    extra_body={"ep_enable_prompt_caching": True},
).with_structured_output(StructuredResponse, method="json_mode")


# ============================================================
# 辅助：读取用户偏好，注入 prompt
# ============================================================
async def _get_preferences_for_sql(user_id: int) -> str:
    """读取用户偏好，格式化为 SQL 查询条件的默认值提示"""
    try:
        async with _pool.connection() as conn:
            cur = await conn.execute(
                "SELECT city, salary_min, salary_max, job_keywords, experience_years, company_age "
                "FROM user_preferences WHERE user_id = %s",
                (user_id,),
            )
            row = await cur.fetchone()
            if not row:
                return ""
            cols = [c.name for c in cur.description] if cur.description else []
            pref = dict(zip(cols, row)) if cols else {}

        parts = []
        if pref.get("city"):
            parts.append(f"期望城市={pref['city']}")
        if pref.get("salary_min") or pref.get("salary_max"):
            parts.append(f"期望薪资={pref.get('salary_min', '')}-{pref.get('salary_max', '')}元/月")
        if pref.get("job_keywords"):
            parts.append(f"岗位关键字={pref['job_keywords']}")
        if pref.get("experience_years"):
            parts.append(f"工作经验={pref['experience_years']}")
        if pref.get("company_age"):
            parts.append(f"公司成立至少={pref['company_age']}年")

        if not parts:
            return ""
        return "\n".join(parts)
    except Exception:
        logger.exception("读取用户偏好失败")
        return ""


# ============================================================
# SQL 校验
# ============================================================
_SQL_FENCE_RE = re.compile(r"```(?:sql)?\s*\n?(.*?)\n?```", re.DOTALL | re.IGNORECASE)
_DANGEROUS_KEYWORDS = re.compile(
    r"\b(DELETE|UPDATE|INSERT|DROP|ALTER|CREATE|TRUNCATE|GRANT|REVOKE|EXECUTE|EXEC)\b",
    re.IGNORECASE,
)


def validate_sql(sql: str) -> tuple[str | None, str]:
    """校验 SQL 是否安全。返回 (error, cleaned_sql)"""
    # 去掉 markdown 代码块
    m = _SQL_FENCE_RE.match(sql.strip())
    cleaned = m.group(1).strip() if m else sql.strip()

    # 必须以 SELECT 或 WITH 开头（允许 CTE）
    upper = cleaned.upper().lstrip()
    if not (upper.startswith("SELECT") or upper.startswith("WITH")):
        return "只允许 SELECT 查询语句", cleaned

    # 不能包含危险关键字
    dangerous = _DANGEROUS_KEYWORDS.findall(cleaned)
    if dangerous:
        return f"SQL 包含禁止的关键字: {', '.join(dangerous)}", cleaned

    # 禁止多语句
    if ";" in cleaned.rstrip(";"):
        return "不允许执行多条 SQL 语句", cleaned

    # 禁止用户ID注入
    if re.search(r"\buser_id\b", cleaned, re.IGNORECASE):
        return "SQL 中不允许出现 user_id，请移除该条件", cleaned

    # 只允许 job_listings 表（CTE 别名除外）
    cte_names = set(re.findall(r'\bWITH\s+(\w+)\s+AS\s*\(', cleaned, re.IGNORECASE))
    table_refs = re.findall(
        r'\b(?:FROM|JOIN|INTO|UPDATE|TABLE)\s+["]?(\w+)', cleaned, re.IGNORECASE
    )
    if not table_refs:
        return "未检测到有效的 FROM 子句", cleaned
    for t in table_refs:
        tl = t.lower()
        if tl != "job_listings" and tl not in {n.lower() for n in cte_names}:
            return f"只允许查询 job_listings 表，不允许访问: {t}", cleaned

    return None, cleaned


# ============================================================
# 节点
# ============================================================
async def sql_generator_node(state: SQLAgentState) -> dict:
    """LLM 生成 SQL"""
    user_id = state.get("user_id", 0)

    # 构建偏好提示
    pref_text = await _get_preferences_for_sql(user_id)
    pref_block = f"\n\n## 用户偏好（查询未指定条件时作为默认值）\n{pref_text}" if pref_text else ""

    # 构建错误反馈（重试时）
    error_block = ""
    if state.get("sql_error"):
        error_block = (
            f"\n\n## 上一次查询出错，请修正！\n"
            f"错误信息：{state['sql_error']}\n"
            f"上次生成的 SQL：{state.get('sql_query', '')}\n"
            f"请分析错误原因并重新生成正确的 SQL。"
        )

    system = SQL_GENERATOR_PROMPT + pref_block + error_block

    # 取最近一条用户消息作为查询输入
    user_query = ""
    for m in reversed(state["messages"]):
        if isinstance(m, HumanMessage) and m.content:
            user_query = m.content
            break

    full_msgs = [SystemMessage(content=system), HumanMessage(content=user_query)]

    try:
        result: SQLOutput = await sql_structured_llm.ainvoke(full_msgs)
        logger.info(f"SQL Agent 生成 SQL:\n{result.sql}")
        return {
            "sql_query": result.sql,
            "sql_error": None,
            "retry_count": state.get("retry_count", 0) + 1,
        }
    except Exception as e:
        logger.exception("SQL 生成失败")
        return {
            "sql_query": None,
            "sql_error": f"SQL 生成失败: {e}",
            "retry_count": state.get("retry_count", 0) + 1,
        }


async def sql_validator_node(state: SQLAgentState) -> dict:
    """校验 SQL 安全性"""
    sql = state.get("sql_query")
    if not sql:
        return {"sql_error": "未生成有效的 SQL 语句"}

    error, cleaned = validate_sql(sql)
    if error:
        logger.warning(f"SQL 校验失败: {error}\nSQL: {sql}")
        return {"sql_error": error, "sql_query": cleaned}

    return {"sql_query": cleaned, "sql_error": None}


async def sql_executor_node(state: SQLAgentState) -> dict:
    """执行 SQL 查询"""
    sql = state.get("sql_query")
    if not sql:
        return {"sql_error": "没有可执行的 SQL"}

    try:
        async with _pool.connection() as conn:
            cur = await conn.execute(sql)
            rows = await cur.fetchall()
            cols = [c.name for c in cur.description] if cur.description else []
            results = [dict(zip(cols, row)) for row in rows]

        logger.info(f"SQL 执行成功，返回 {len(results)} 行")
        return {"query_results": results, "sql_error": None}
    except Exception as e:
        logger.warning(f"SQL 执行失败: {e}\nSQL: {sql}")
        return {"sql_error": str(e), "query_results": None}


async def sql_format_response_node(state: SQLAgentState) -> dict:
    """将查询结果格式化为结构化输出 + 自然语言总结"""
    error = state.get("sql_error")
    results = state.get("query_results")

    if error and not results:
        # 查询完全失败
        return {
            "structured_content": {
                "response_type": "general",
                "summary": f"抱歉，岗位查询失败：{error}",
                "jobs": [],
            }
        }

    if not results:
        return {
            "structured_content": {
                "response_type": "browse",
                "summary": "未找到匹配的岗位，请尝试放宽搜索条件。",
                "jobs": [],
            }
        }

    # 构建 jobs 数组
    jobs: list[dict] = []
    for idx, r in enumerate(results):
        cy = r.get("company_years")
        company_years = f"{cy:.1f}" if isinstance(cy, (int, float)) else "-"
        jobs.append({
            "rank": idx + 1,
            "title": r.get("title", ""),
            "company": r.get("company_name", ""),
            "salary": r.get("salary_range", ""),
            "experience": r.get("experience", ""),
            "company_years": company_years,
        })

    summary = f"共找到 {len(results)} 个匹配岗位"

    # 用 LLM 生成自然语言总结
    try:
        job_lines = []
        for r in results[:10]:
            job_lines.append(
                f"- {r.get('title','')} | {r.get('company_name','')} | "
                f"{r.get('salary_range','')} | {r.get('experience','')} | {r.get('education','')}"
            )
        job_text = "\n".join(job_lines)
        result = await format_llm.ainvoke([
            HumanMessage(content=(
                f"你是岗位查询结果总结器。根据以下 {len(results)} 条岗位数据，"
                f"生成一段简洁的中文总结（1-3句），描述这些岗位的整体特征"
                f"（如薪资范围、经验要求分布、涉及的技术方向等）。\n\n{job_text}"
            ))
        ])
        if result.summary:
            summary = result.summary
    except Exception:
        pass

    return {
        "structured_content": {
            "response_type": "browse",
            "summary": summary,
            "jobs": jobs,
        }
    }


# ============================================================
# 条件路由
# ============================================================
def sql_route_after_validator(state: SQLAgentState) -> str:
    if state.get("sql_error"):
        return "format_response"
    return "sql_executor"


def sql_route_after_executor(state: SQLAgentState) -> str:
    if state.get("sql_error") and state.get("retry_count", 0) < 2:
        logger.info("SQL 执行失败，进入重试")
        return "sql_generator"
    return "format_response"


# ============================================================
# 构建 Graph
# ============================================================
sql_builder = StateGraph(SQLAgentState)
sql_builder.add_node("sql_generator", sql_generator_node)
sql_builder.add_node("sql_validator", sql_validator_node)
sql_builder.add_node("sql_executor", sql_executor_node)
sql_builder.add_node("format_response", sql_format_response_node)

sql_builder.add_edge(START, "sql_generator")
sql_builder.add_edge("sql_generator", "sql_validator")
sql_builder.add_conditional_edges("sql_validator", sql_route_after_validator, {
    "sql_executor": "sql_executor",
    "format_response": "format_response",
})
sql_builder.add_conditional_edges("sql_executor", sql_route_after_executor, {
    "sql_generator": "sql_generator",
    "format_response": "format_response",
})
sql_builder.add_edge("format_response", END)

_sql_graph: CompiledStateGraph | None = None


# ============================================================
# 暴露接口
# ============================================================
def get_sql_graph() -> CompiledStateGraph:
    if _sql_graph is None:
        raise RuntimeError("SQL Graph 尚未初始化，请在 lifespan 中先调用 init_sql_graph()")
    return _sql_graph


async def get_sql_checkpoint_state(thread_id: str) -> dict | None:
    if _sql_graph is None:
        return None
    config = {"configurable": {"thread_id": thread_id}}
    tup = await _sql_graph.checkpointer.aget_tuple(config)
    if tup is None:
        return None
    return tup.checkpoint.get("channel_values", {})


async def init_sql_graph(pool: AsyncConnectionPool) -> None:
    global _sql_graph, _pool
    from psycopg import AsyncConnection
    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

    _pool = pool

    setup_conn = await AsyncConnection.connect(settings.PG_URL, autocommit=True)
    try:
        temp_saver = AsyncPostgresSaver(conn=setup_conn)
        await temp_saver.setup()
    finally:
        await setup_conn.close()

    _sql_graph = sql_builder.compile(checkpointer=AsyncPostgresSaver(conn=pool))  # type: ignore[arg-type]
    logger.info("SQL Graph 已初始化（SQL 生成/校验/执行 + 结构化输出）")
