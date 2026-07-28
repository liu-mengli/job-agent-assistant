"""
从知识库切片中提取技术名词术语表（中英对照）

一次性运行脚本。用 LLM 从 41 个切片中提取术语，按分类整理，
输出到 api/rag/kb_terminology.json，供 Query 改写 Prompt 注入使用。
"""
import asyncio
import json
import selectors
from pathlib import Path

from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI

from config import settings


TERMINOLOGY_PROMPT = """你是一个技术文档分析器。从以下 SOP 技术手册中提取所有技术名词，按类别整理中英文对照。

## 分类
1. **页面/模块名称**：如 Run Page → 生產執行操作頁面、User Page → 作業員操作頁面
2. **功能/参数名称**：如 Yield Control → 良率控制設定、Offset Setting → 各軸位置修正設定
3. **硬件/组件名称**：如 Front Arm → 前手臂、Rotator、Trolley、Cobra
4. **操作/动作名称**：如 Save → 儲存、Alignment Start → 原點校正開始、Lot Done → 清除總計
5. **模式/状态名称**：如 On Line/Normal、UnInitial、Ready、Cycle
6. **缩写/代号**：如 SLT、UPH、TLC、EMG、PM、Lidar

## 提取规则
- 英文术语如果在文档中有对应的中文翻译→给出中英对照
- 如果仅有英文或仅有中文→只填对应字段，另一侧留空字符串
- 优先提取：文档标题、章节标题、按钮名称、参数栏位名、表格列名
- 每个术语不超过 30 个字符
- 同一术语的不同表述合并为一条（如「Yield Control」和「Yield Control (良率控制設定)」→ en: Yield Control, zh: 良率控制設定）

## 输出格式
返回纯 JSON 数组，不要 markdown 包裹，不要额外文字：
[
  {{"category": "页面/模块", "en": "Run Page", "zh": "生產執行操作頁面"}},
  {{"category": "页面/模块", "en": "User Page", "zh": "作業員操作頁面"}}
]

## 文档内容
{content}"""


async def main():
    from psycopg_pool import AsyncConnectionPool

    pool = AsyncConnectionPool(settings.PG_URL, min_size=1, max_size=2, open=False)
    await pool.open()

    try:
        # 读取所有切片
        async with pool.connection() as conn:
            cur = await conn.execute(
                "SELECT section, content FROM knowledge_chunks ORDER BY chunk_index"
            )
            rows = await cur.fetchall()

        # 拼接文档内容（优先用章节标题+摘要）
        parts = []
        for section, content in rows:
            section_clean = section or ""
            content_clean = (content or "")[:800]  # 每段取前800字，控制总长度
            parts.append(f"## {section_clean}\n{content_clean}")

        doc_text = "\n\n".join(parts)
        print(f"文档总长度: {len(doc_text)} 字")

        # 调用 LLM 提取
        llm = ChatOpenAI(
            model=settings.DEEPSEEK_MODEL,
            api_key=settings.DEEPSEEK_API_KEY,
            base_url=settings.DEEPSEEK_BASE_URL,
            temperature=0,
            request_timeout=60,
        )

        prompt = TERMINOLOGY_PROMPT.format(content=doc_text)
        response = await llm.ainvoke([HumanMessage(content=prompt)])

        text = (response.content or "").strip()
        # 处理可能的 markdown 包裹
        if text.startswith("```"):
            parts_md = text.split("```")
            text = parts_md[1] if len(parts_md) >= 2 else text
            if text.startswith("json"):
                text = text[4:]

        terms = json.loads(text)
        print(f"提取术语数: {len(terms)}")

        # 分类统计
        from collections import Counter
        cat_counts = Counter(t["category"] for t in terms)
        for cat, count in cat_counts.most_common():
            print(f"  {cat}: {count}")

        # 保存
        out_path = Path(__file__).parent / "api" / "rag" / "kb_terminology.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump({"terms": terms, "document": "3200 Optimized User Manual V1.2.doc", "total": len(terms)}, f, ensure_ascii=False, indent=2)
        print(f"\n术语表已保存: {out_path}")

        # 打印前10条供验证
        print("\n前10条预览:")
        for t in terms[:10]:
            print(f"  [{t['category']}] {t['en']} → {t['zh']}")

    finally:
        await pool.close()


if __name__ == "__main__":
    asyncio.run(main(), loop_factory=lambda: asyncio.SelectorEventLoop(selectors.SelectSelector()))
