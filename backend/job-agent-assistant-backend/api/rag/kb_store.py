"""知识库向量存取 —— pgvector vector(1024) + 多文档元数据 + BM25 中英文混合检索"""

import numpy as np
from pgvector.psycopg import register_vector_async
from psycopg_pool import AsyncConnectionPool

from api.log import logger
from config import settings

# 简繁转换器（模块级单例，避免重复初始化）
_CC_T2S = None


def _ensure_cc():
    global _CC_T2S
    if _CC_T2S is None:
        from opencc import OpenCC
        _CC_T2S = OpenCC('t2s')


def _bigram_tokenize(text: str) -> str:
    """jieba 中文分词 + ASCII 原样保留，用于 PG tsvector 索引。

    使用 jieba.cut_for_search 分词（召回优先模式，长词同时拆分子词），
    分词前自动将繁体中文转换为简体，消除简繁不匹配问题。
    生成的 token 串供 to_tsvector('simple', ...) 使用。
    """
    import jieba

    _ensure_cc()
    text = _CC_T2S.convert(text)  # type: ignore[union-attr]
    words = jieba.cut_for_search(text)
    return ' '.join(words)

CREATE_KB_CHUNKS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS knowledge_chunks (
    id SERIAL PRIMARY KEY,
    document_id INTEGER REFERENCES knowledge_documents(id) ON DELETE CASCADE,
    document_name TEXT NOT NULL,
    version TEXT NOT NULL DEFAULT '1.0',
    source_file TEXT NOT NULL,
    chunk_index INTEGER NOT NULL,
    content TEXT NOT NULL,
    section TEXT NOT NULL DEFAULT '',
    images JSONB DEFAULT '[]',
    embedding vector(1024) NOT NULL
)
"""

CREATE_KB_CHUNKS_INDEX_SQL = """
CREATE INDEX IF NOT EXISTS idx_knowledge_chunks_doc
ON knowledge_chunks (document_id)
"""


async def ensure_kb_table(pool: AsyncConnectionPool) -> None:
    async with pool.connection() as conn:
        await conn.execute(CREATE_KB_CHUNKS_TABLE_SQL)
        await conn.execute(CREATE_KB_CHUNKS_INDEX_SQL)
        # 迁移：images JSONB 列
        await conn.execute("""
            ALTER TABLE knowledge_chunks ADD COLUMN IF NOT EXISTS images JSONB DEFAULT '[]'
        """)
        # BM25 全文搜索：英文 tsvector（自动生成列 + GIN 索引）
        await conn.execute("""
            ALTER TABLE knowledge_chunks ADD COLUMN IF NOT EXISTS fts tsvector
            GENERATED ALWAYS AS (to_tsvector('simple', content)) STORED
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_knowledge_chunks_fts
            ON knowledge_chunks USING GIN (fts)
        """)
        # BM25 中文分词：bigram tsvector 列 + GIN 索引
        await conn.execute("""
            ALTER TABLE knowledge_chunks ADD COLUMN IF NOT EXISTS fts_zh tsvector
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_knowledge_chunks_fts_zh
            ON knowledge_chunks USING GIN (fts_zh)
        """)
        # 检索质量日志表
        await conn.execute(CREATE_KB_LOGS_TABLE_SQL)
        # 迁移：为已有数据填充 fts_zh（仅对空值行执行）
        cur = await conn.execute(
            "SELECT COUNT(*) FROM knowledge_chunks WHERE fts_zh IS NULL"
        )
        null_count = (await cur.fetchone())[0]
        if null_count > 0:
            cur = await conn.execute(
                "SELECT id, content FROM knowledge_chunks WHERE fts_zh IS NULL"
            )
            rows = await cur.fetchall()
            for row in rows:
                tokenized = _bigram_tokenize(row[1])
                await conn.execute(
                    "UPDATE knowledge_chunks SET fts_zh = to_tsvector('simple', %s) WHERE id = %s",
                    (tokenized, row[0]),
                )
            logger.info(f"[KB] 已迁移 {len(rows)} 行的 fts_zh 中文分词索引")


async def kb_insert_chunks(
    pool: AsyncConnectionPool,
    document_id: int,
    document_name: str,
    version: str,
    source_file: str,
    chunks: list[dict],
    embeddings: np.ndarray,
) -> int:
    """批量写入切片及向量，带文档元数据"""
    import json as _json

    async with pool.connection() as conn:
        await register_vector_async(conn)
        async with conn.cursor() as cur:
            for i, (chunk, emb) in enumerate(zip(chunks, embeddings)):
                vec = emb.astype(np.float32).tolist()
                section = chunk.get("section", "")
                images = _json.dumps(chunk.get("images", []), ensure_ascii=False)
                tokenized = _bigram_tokenize(chunk["content"])
                await cur.execute(
                    "INSERT INTO knowledge_chunks "
                    "(document_id, document_name, version, source_file, chunk_index, content, section, images, embedding, fts_zh) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::vector, to_tsvector('simple', %s))",
                    (document_id, document_name, version, source_file, i, chunk["content"], section, images, vec, tokenized),
                )
    logger.info(f"已写入 {len(chunks)} 个知识库切片，document_id={document_id}")
    return len(chunks)


async def kb_search(
    pool: AsyncConnectionPool,
    query_embedding: np.ndarray,
    top_k: int | None = None,
) -> list[dict]:
    """pgvector 余弦距离检索，返回结果带文档来源标注"""
    if top_k is None:
        top_k = settings.KB_RETRIEVAL_TOP_K

    query_vec = query_embedding.astype(np.float32).tolist()

    async with pool.connection() as conn:
        await register_vector_async(conn)
        cur = await conn.execute(
            "SELECT content, section, document_name, version, source_file, images, "
            "embedding <=> %s::vector AS distance "
            "FROM knowledge_chunks "
            "WHERE embedding <=> %s::vector < %s::float "
            "ORDER BY distance "
            "LIMIT %s::integer",
            (query_vec, query_vec, settings.KB_RETRIEVAL_THRESHOLD, top_k),
        )
        rows = await cur.fetchall()

    return [
        {
            "content": r[0],
            "section": r[1],
            "document_name": r[2],
            "version": r[3],
            "source_file": r[4],
            "images": r[5] if isinstance(r[5], list) else [],
            "distance": float(r[6]),
        }
        for r in rows
    ]


async def kb_bm25_search(
    pool: AsyncConnectionPool,
    query: str,
    top_k: int | None = None,
) -> list[dict]:
    """PG 全文检索（BM25 变体）—— 中英文混合关键词匹配。

    fts 列（英文）：plainto_tsquery (AND 语义) → 精确匹配英文术语/型号/缩写。
    fts_zh 列（中文）：bigram 分词 → to_tsquery (OR 语义) → 宽松匹配中文 token。
    OR 语义避免口语化长改写词因 token 过多导致全部 AND 失败。
    ts_rank 自动加权：命中 token 多的切片排前面。
    """
    if top_k is None:
        top_k = settings.KB_BM25_TOP_K

    # 中文列用 OR 语义：手动构造 'token1' | 'token2' | ...
    tokens = [t for t in _bigram_tokenize(query).split() if t.strip()]
    or_query = " | ".join(tokens) if tokens else query

    async with pool.connection() as conn:
        cur = await conn.execute(
            "SELECT content, section, document_name, version, source_file, images, "
            "GREATEST("
            "  COALESCE(ts_rank(fts, plainto_tsquery('simple', %s)), 0), "
            "  COALESCE(ts_rank(fts_zh, to_tsquery('simple', %s)), 0)"
            ") AS bm25_score "
            "FROM knowledge_chunks "
            "WHERE fts @@ plainto_tsquery('simple', %s) "
            "   OR fts_zh @@ to_tsquery('simple', %s) "
            "ORDER BY bm25_score DESC "
            "LIMIT %s::integer",
            (query, or_query, query, or_query, max(3, top_k // 3)),
        )
        rows = await cur.fetchall()

    return [
        {
            "content": r[0],
            "section": r[1],
            "document_name": r[2],
            "version": r[3],
            "source_file": r[4],
            "images": r[5] if isinstance(r[5], list) else [],
            "bm25_score": float(r[6]),
        }
        for r in rows
    ]


# ------------------------------------------------------------
# 检索质量日志
# ------------------------------------------------------------
CREATE_KB_LOGS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS kb_retrieval_logs (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    original_query TEXT NOT NULL,
    rewritten_queries JSONB DEFAULT '[]',
    dense_hits INTEGER DEFAULT 0,
    bm25_hits INTEGER DEFAULT 0,
    fused_candidates INTEGER DEFAULT 0,
    reranked_candidates INTEGER DEFAULT 0,
    passed_candidates INTEGER DEFAULT 0,
    top_rerank_scores JSONB DEFAULT '[]',
    top_dense_similarities JSONB DEFAULT '[]',
    top_bm25_scores JSONB DEFAULT '[]',
    all_filtered BOOLEAN DEFAULT FALSE,
    latency_ms INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW()
)
"""


async def ensure_kb_logs_table(pool: AsyncConnectionPool) -> None:
    async with pool.connection() as conn:
        await conn.execute(CREATE_KB_LOGS_TABLE_SQL)


async def kb_insert_retrieval_log(
    pool: AsyncConnectionPool,
    user_id: int,
    original_query: str,
    rewritten_queries: list[str],
    dense_hits: int,
    bm25_hits: int,
    fused_candidates: int,
    reranked_candidates: int,
    passed_candidates: int,
    top_rerank_scores: list[float],
    top_dense_similarities: list[float],
    top_bm25_scores: list[float],
    all_filtered: bool,
    latency_ms: int,
) -> int:
    import json

    async with pool.connection() as conn:
        cur = await conn.execute(
            "INSERT INTO kb_retrieval_logs "
            "(user_id, original_query, rewritten_queries, dense_hits, bm25_hits, "
            "fused_candidates, reranked_candidates, passed_candidates, "
            "top_rerank_scores, top_dense_similarities, top_bm25_scores, "
            "all_filtered, latency_ms) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) "
            "RETURNING id",
            (
                user_id,
                original_query,
                json.dumps(rewritten_queries, ensure_ascii=False),
                dense_hits,
                bm25_hits,
                fused_candidates,
                reranked_candidates,
                passed_candidates,
                json.dumps(top_rerank_scores),
                json.dumps(top_dense_similarities),
                json.dumps(top_bm25_scores),
                all_filtered,
                latency_ms,
            ),
        )
        row = await cur.fetchone()
        return row[0] if row else 0


async def kb_get_retrieval_logs(
    pool: AsyncConnectionPool,
    limit: int = 50,
    offset: int = 0,
) -> list[dict]:
    async with pool.connection() as conn:
        cur = await conn.execute(
            "SELECT id, user_id, original_query, rewritten_queries, "
            "dense_hits, bm25_hits, fused_candidates, reranked_candidates, "
            "passed_candidates, top_rerank_scores, top_dense_similarities, "
            "top_bm25_scores, all_filtered, latency_ms, created_at "
            "FROM kb_retrieval_logs "
            "ORDER BY created_at DESC "
            "LIMIT %s::integer OFFSET %s::integer",
            (limit, offset),
        )
        rows = await cur.fetchall()
        return [
            {
                "id": r[0],
                "user_id": r[1],
                "original_query": r[2],
                "rewritten_queries": r[3],
                "dense_hits": r[4],
                "bm25_hits": r[5],
                "fused_candidates": r[6],
                "reranked_candidates": r[7],
                "passed_candidates": r[8],
                "top_rerank_scores": r[9],
                "top_dense_similarities": r[10],
                "top_bm25_scores": r[11],
                "all_filtered": r[12],
                "latency_ms": r[13],
                "created_at": r[14].isoformat() if r[14] else None,
            }
            for r in rows
        ]


async def kb_delete_document(pool: AsyncConnectionPool, document_id: int) -> None:
    async with pool.connection() as conn:
        await conn.execute(
            "DELETE FROM knowledge_chunks WHERE document_id = %s",
            (document_id,),
        )
