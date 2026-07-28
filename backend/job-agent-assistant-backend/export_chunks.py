import asyncio, selectors
from config import settings
from psycopg_pool import AsyncConnectionPool

OUTPUT = "e:/Python项目/job-agent-assistant/kb_chunks_export.md"

async def main():
    pool = AsyncConnectionPool(settings.PG_URL, min_size=1, max_size=2, open=False)
    await pool.open()
    try:
        async with pool.connection() as conn:
            cur = await conn.execute('''
                SELECT id, document_name, section, chunk_index, content, source_file
                FROM knowledge_chunks ORDER BY document_name, chunk_index
            ''')
            rows = await cur.fetchall()

            doc_names = sorted(set(r[1] for r in rows))

            with open(OUTPUT, 'w', encoding='utf-8') as f:
                f.write('# 知识库切片导出\n\n')
                f.write(f'**总切片数**: {len(rows)}\n')
                f.write(f'**文档数**: {len(doc_names)}\n')
                for dn in doc_names:
                    f.write(f'- {dn}\n')
                f.write('\n---\n\n')

                for r in rows:
                    doc_name = r[1] or 'N/A'
                    section = r[2] or 'N/A'
                    chunk_id = r[0]
                    idx = r[3]
                    content = r[4] or ''
                    source = r[5] or 'N/A'

                    f.write(f'## 切片 #{idx} (ID={chunk_id})\n\n')
                    f.write(f'- **文档**: {doc_name}\n')
                    f.write(f'- **章节**: {section}\n')
                    f.write(f'- **来源文件**: {source}\n')
                    f.write(f'- **内容长度**: {len(content)} 字\n\n')
                    f.write('```\n')
                    f.write(content)
                    f.write('\n```\n\n')
                    f.write('---\n\n')

            print(f'OK: {len(rows)} chunks written to {OUTPUT}')

    finally:
        await pool.close()

asyncio.run(main(), loop_factory=lambda: asyncio.SelectorEventLoop(selectors.SelectSelector()))
