"""
共享上下文窗口管理 — 所有 Agent 通用
====================================
1. DeepSeek Prompt Caching 配置
2. 旧 ToolMessage 裁剪（只保留最近 N 条）
3. 超长对话增量摘要（字符数触发，DeepSeek-v4-flash 执行摘要）
"""
from langchain_core.messages import (
    SystemMessage, HumanMessage, AIMessage, ToolMessage,
)
from langchain_openai import ChatOpenAI
from langgraph.graph.message import RemoveMessage

from api.log import logger
from config import settings

# ============================================================
# 摘要专用 LLM（懒加载单例）
# ============================================================
_summarize_llm: ChatOpenAI | None = None


def get_summarize_llm() -> ChatOpenAI:
    global _summarize_llm
    if _summarize_llm is None:
        _summarize_llm = ChatOpenAI(
            model=settings.DEEPSEEK_MODEL,
            api_key=settings.DEEPSEEK_API_KEY,
            base_url=settings.DEEPSEEK_BASE_URL,
            temperature=0,
            request_timeout=15,
            extra_body={"ep_enable_prompt_caching": True},
        )
    return _summarize_llm

# ============================================================
# DeepSeek Prompt Caching 配置
# ============================================================
CACHE_EXTRA_BODY = {"ep_enable_prompt_caching": True}

# ============================================================
# 阈值配置
# ============================================================
CONTEXT_CHAR_THRESHOLD = 24000  # 约 12K tokens（DeepSeek-v4-flash 128K 上下文）
KEEP_RECENT_MESSAGES = 8        # 摘要后保留最近消息数（约 3-4 轮对话）
KEEP_RECENT_TOOL_MESSAGES = 4   # 保留最近 ToolMessage 条数

SUMMARIZE_PROMPT = """你是一个对话摘要器。请用 2-3 句中文总结以下对话的关键信息，提取对后续对话仍然重要的内容（如用户背景、偏好、已讨论的关键结论等）。

{existing}

## 新对话内容
{new_messages}

请直接输出摘要，不要加前缀或标签。"""


def estimate_chars(messages: list) -> int:
    """估算消息列表的总字符数（不含 SystemMessage）"""
    return sum(
        len(getattr(m, "content", "") or "")
        for m in messages
        if not isinstance(m, SystemMessage)
    )


def _extract_conversation_text(messages: list) -> str:
    """从消息列表中提取人类可读的对话文本，每条约 500 字"""
    lines = []
    for m in messages:
        role = getattr(m, "type", None)
        content = (getattr(m, "content", "") or "")[:500]
        if role == "human":
            lines.append(f"用户: {content}")
        elif role == "ai":
            lines.append(f"AI: {content}")
    return "\n".join(lines)


async def manage_context(
    state: dict,
    system_prompt: str,
    summarize_llm,  # ChatOpenAI，用于摘要
) -> tuple[list, list]:
    """构建发送给 LLM 的消息列表，同时产出状态变更。

    返回:
        (messages_for_llm, state_mutations)
        - messages_for_llm: [SystemMessage, ...trimmed messages]
        - state_mutations: 要合并到 node return 的 dict（含 RemoveMessage + conversation_summary）
    """
    msgs = list(state["messages"])
    if not msgs:
        return [SystemMessage(content=system_prompt)], {}

    mutations: dict = {}
    remove_ids: list[str] = []

    # ----------------------------------------------------------
    # 第 1 步：裁剪旧 ToolMessage（只保留最近 KEEP_RECENT_TOOL_MESSAGES 条）
    # ----------------------------------------------------------
    tool_count = 0
    for i in range(len(msgs) - 1, -1, -1):
        if isinstance(msgs[i], ToolMessage):
            tool_count += 1
            if tool_count > KEEP_RECENT_TOOL_MESSAGES:
                remove_ids.append(msgs[i].id)
                msgs.pop(i)

    if remove_ids:
        logger.info(
            f"[Context] 裁剪 {len(remove_ids)} 条旧 ToolMessage，"
            f"保留最近 {KEEP_RECENT_TOOL_MESSAGES} 条"
        )

    # ----------------------------------------------------------
    # 第 2 步：超阈值 → 增量摘要
    # ----------------------------------------------------------
    chars_now = estimate_chars(msgs)
    existing_summary = state.get("conversation_summary", "")

    if chars_now > CONTEXT_CHAR_THRESHOLD:
        non_system = [m for m in msgs if not isinstance(m, SystemMessage)]
        if len(non_system) > KEEP_RECENT_MESSAGES:
            old = non_system[:-KEEP_RECENT_MESSAGES]
            recent = non_system[-KEEP_RECENT_MESSAGES:]

            old_text = _extract_conversation_text(old)
            existing_block = f"## 已有摘要\n{existing_summary}\n" if existing_summary else ""
            prompt = SUMMARIZE_PROMPT.format(
                existing=existing_block,
                new_messages=old_text,
            )

            try:
                from langchain_core.messages import HumanMessage
                resp = await summarize_llm.ainvoke([HumanMessage(content=prompt)])
                new_summary = (resp.content or "").strip()
                logger.info(
                    f"[Context] 增量摘要完成: {chars_now} → "
                    f"压缩 {len(old)} 条旧消息 ({estimate_chars(old)} 字) → "
                    f"摘要 {len(new_summary)} 字，保留 {len(recent)} 条"
                )
            except Exception:
                logger.exception("[Context] 摘要 LLM 调用失败，跳过本次压缩")
                new_summary = existing_summary

            # 标记旧消息删除
            for m in old:
                remove_ids.append(m.id)

            # 原位替换：摘要放在消息列表最前面
            msgs = [SystemMessage(content=f"[历史对话摘要] {new_summary}")] + recent

            mutations["conversation_summary"] = new_summary

    # ----------------------------------------------------------
    # 构建 state_mutations
    # ----------------------------------------------------------
    if remove_ids:
        mutations["messages"] = [RemoveMessage(id=mid) for mid in remove_ids]

    # 组装最终消息列表
    messages_for_llm = [SystemMessage(content=system_prompt)] + msgs

    return messages_for_llm, mutations
