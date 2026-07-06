"""向量存取与检索 —— pgvector 原生 vector(512) + <=> 余弦距离"""

import numpy as np
from pgvector.psycopg import register_vector_async
from psycopg_pool import AsyncConnectionPool

from api.log import logger
from config import settings

CREATE_CHUNKS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS resume_chunks (
    id SERIAL PRIMARY KEY,
    document_id INTEGER REFERENCES resume_documents(id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL,
    content TEXT NOT NULL,
    section TEXT NOT NULL DEFAULT '',
    embedding vector(512) NOT NULL
)
"""

ADD_SECTION_COLUMN_SQL = """
ALTER TABLE resume_chunks ADD COLUMN IF NOT EXISTS section TEXT NOT NULL DEFAULT ''
"""


async def ensure_table(pool: AsyncConnectionPool) -> None:
    async with pool.connection() as conn:
        await conn.execute(CREATE_CHUNKS_TABLE_SQL)
        await conn.execute(ADD_SECTION_COLUMN_SQL)


async def insert_chunks(
    pool: AsyncConnectionPool,
    document_id: int,
    chunks: list[dict],
    embeddings: np.ndarray,
) -> int:
    """批量写入切片及其向量（pgvector 原生格式）"""
    async with pool.connection() as conn:
        await register_vector_async(conn)
        async with conn.cursor() as cur:
            for i, (chunk, emb) in enumerate(zip(chunks, embeddings)):
                vec = emb.astype(np.float32).tolist()
                section = chunk.get("section", "")
                await cur.execute(
                    "INSERT INTO resume_chunks (document_id, chunk_index, content, section, embedding) "
                    "VALUES (%s, %s, %s, %s, %s::vector)",
                    (document_id, i, chunk["content"], section, vec),
                )
    logger.info(f"已写入 {len(chunks)} 个切片，document_id={document_id}")
    return len(chunks)


async def search(
    pool: AsyncConnectionPool,
    query_embedding: np.ndarray,
    user_id: int,
    top_k: int | None = None,
) -> list[str]:
    """pgvector 原生余弦距离检索，<=> 在归一化向量上等价于 1 - 余弦相似度"""
    if top_k is None:
        top_k = settings.RETRIEVAL_TOP_K

    query_vec = query_embedding.astype(np.float32).tolist()

    async with pool.connection() as conn:
        await register_vector_async(conn)
        cur = await conn.execute(
            "SELECT rc.content, rc.section, rc.embedding <=> %s::vector AS distance "
            "FROM resume_chunks rc "
            "JOIN resume_documents rd ON rc.document_id = rd.id "
            "WHERE rd.user_id = %s "
            "AND rc.embedding <=> %s::vector < %s::float "
            "ORDER BY distance "
            "LIMIT %s::integer",
            (user_id, query_vec, query_vec, settings.RETRIEVAL_THRESHOLD, top_k),
        )
        rows = await cur.fetchall()

    # 拼接章节标签到结果中，LLM 可溯源
    return [f"【{row[1]}】{row[0]}" if row[1] else row[0] for row in rows]


async def delete_document(pool: AsyncConnectionPool, document_id: int) -> None:
    async with pool.connection() as conn:
        await conn.execute(
            "DELETE FROM resume_chunks WHERE document_id = %s",
            (document_id,),
        )
