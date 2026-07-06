"""LangGraph Tool：search_resume —— 检索用户简历中与 query 最相关的内容"""

from langchain_core.tools import tool

from api.rag.embedder import embed
from api.rag.store import search


def _make_search(user_id: int, pool):
    @tool
    async def search_resume(query: str) -> str:
        """搜索用户上传的简历。当用户要求「分析简历」「看看我的履历」「根据我的背景推荐」时调用。
        参数 query: 自然语言查询，如「教育背景」「Python 项目经验」"""
        if not query.strip():
            return "未提供查询内容。"

        q_embedding = embed([query])[0]
        chunks = await search(pool, q_embedding, user_id)

        if not chunks:
            return "简历中未找到与您问题相关的内容。"

        return "\n\n---\n\n".join(chunks)

    return search_resume
