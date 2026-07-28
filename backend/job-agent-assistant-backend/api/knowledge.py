import asyncio
import os
from uuid import uuid4

from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy import select
from starlette.responses import JSONResponse

from api.database import get_db
from api.dependencies import get_current_user
from api.log import logger
from api.models.knowledge_document import KnowledgeDocument
from api.rag.doc_parser import parse_doc, parse_doc_with_images
from api.rag.kb_chunker import split_manual, assign_images_to_chunks
from api.rag.kb_embedder import kb_embed
from api.rag.kb_store import kb_delete_document, kb_insert_chunks
from api.schemas.response import ApiResponse
from config import settings

router = APIRouter()

os.makedirs(settings.KB_UPLOAD_DIR, exist_ok=True)

ALLOWED_EXTENSIONS = {".doc", ".docx"}


@router.post("/knowledge/upload", response_model=ApiResponse)
async def upload_knowledge(
    file: UploadFile = File(...),
    user_id: int = Depends(get_current_user),
):
    """上传知识库文档（.doc/.docx）：存文件并立即返回，后台异步解析 + 切片 + 向量化"""
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        return ApiResponse(code=400, message="仅支持 .doc / .docx 文件")

    from api.agent.graph import get_pool
    pool = get_pool()

    # 保存文件
    save_name = f"{uuid4().hex}{ext}"
    save_path = os.path.join(settings.KB_UPLOAD_DIR, save_name)
    content = await file.read()
    with open(save_path, "wb") as f:
        f.write(content)

    # 插入 processing 状态记录
    async with pool.connection() as conn:
        cur = await conn.execute(
            "INSERT INTO knowledge_documents (document_name, version, source_file, chunk_count, status) "
            "VALUES (%s, '1.0', %s, 0, 'processing') RETURNING id",
            (file.filename, file.filename),
        )
        row = await cur.fetchone()
        doc_id = row[0]

    logger.info(f"知识库文档上传已接收 file={file.filename} doc_id={doc_id}")

    asyncio.create_task(
        _process_knowledge_background(doc_id, save_path, file.filename, pool)
    )

    return ApiResponse(
        data={"id": doc_id, "document_name": file.filename, "version": "1.0", "status": "processing"}
    )


async def _process_knowledge_background(
    doc_id: int,
    save_path: str,
    filename: str,
    pool,
) -> None:
    """后台任务：DOC 解析 → SOP 切片 → bge-m3 向量化 → 入库 → 更新状态"""
    try:
        logger.info(f"知识库后台处理开始 doc_id={doc_id} file={filename}")

        loop = asyncio.get_running_loop()

        # 1. DOC 解析 + 图片提取
        images_dir = os.path.join(settings.KB_UPLOAD_DIR, "images", str(doc_id))
        text, section_images = await loop.run_in_executor(
            None, parse_doc_with_images, save_path, images_dir,
        )
        if not text.strip():
            await _update_kb_status(pool, doc_id, "error", "文档中未检测到文本内容")
            return

        # 2. SOP 切片
        chunks = split_manual(text)
        if not chunks:
            await _update_kb_status(pool, doc_id, "error", "文本切片后无内容")
            return

        # 3. 关联图片到切片
        if section_images:
            chunks = assign_images_to_chunks(chunks, section_images)
            # 将图片文件名转为完整 URL 路径
            for c in chunks:
                if c.get("images"):
                    c["images"] = [
                        f"/static/kb-images/{doc_id}/{img}"
                        for img in c["images"]
                    ]

        # 4. 注入文档信息到切片正文（型号/版本写入 embedding，方便按型号检索）
        file_header = f"文档：{filename}\n"
        for c in chunks:
            c["content"] = file_header + c["content"]

        # 5. bge-m3 向量化
        texts = [c["content"] for c in chunks]
        embeddings = await loop.run_in_executor(None, kb_embed, texts)

        # 6. 入库
        await kb_insert_chunks(pool, doc_id, filename, "1.0", filename, chunks, embeddings)

        # 7. 更新状态
        async with pool.connection() as conn:
            await conn.execute(
                "UPDATE knowledge_documents SET chunk_count = %s, status = 'ready' WHERE id = %s",
                (len(chunks), doc_id),
            )
        logger.info(f"知识库后台处理完成 doc_id={doc_id} file={filename} chunks={len(chunks)}")

    except Exception:
        logger.exception(f"知识库后台处理失败 doc_id={doc_id}")
        await _update_kb_status(pool, doc_id, "error", "服务器处理文档时出错")


async def _update_kb_status(pool, doc_id: int, status: str, error_message: str | None = None) -> None:
    async with pool.connection() as conn:
        await conn.execute(
            "UPDATE knowledge_documents SET status = %s, error_message = %s WHERE id = %s",
            (status, error_message, doc_id),
        )


@router.get("/knowledge", response_model=ApiResponse)
async def list_knowledge(
    user_id: int = Depends(get_current_user),
    db=Depends(get_db),
):
    """知识库文档列表（共享资源，所有认证用户可查看）"""
    result = await db.execute(
        select(KnowledgeDocument).order_by(KnowledgeDocument.created_at.desc())
    )
    rows = result.scalars().all()
    return ApiResponse(data={
        "documents": [
            {
                "id": r.id,
                "document_name": r.document_name,
                "version": r.version,
                "source_file": r.source_file,
                "chunk_count": r.chunk_count,
                "status": r.status,
                "error_message": r.error_message,
                "created_at": r.created_at.isoformat(),
            }
            for r in rows
        ]
    })


@router.get("/knowledge/logs")
async def get_retrieval_logs(
    limit: int = 50,
    offset: int = 0,
    user_id: int = Depends(get_current_user),
):
    """检索质量日志列表（最近优先），可用于离线评估命中率、MRR、分数分布等。

    每条记录包含：原始查询、改写查询、各阶段命中数（Dense/BM25/融合/精排/过滤后）、
    top-3 分数、是否全部被过滤、检索耗时。
    """
    from api.agent.graph import get_pool
    from api.rag.kb_store import kb_get_retrieval_logs

    pool = get_pool()
    logs = await kb_get_retrieval_logs(pool, limit=min(limit, 200), offset=offset)

    # 汇总统计
    total = len(logs)
    hit_count = sum(1 for log in logs if log["passed_candidates"] > 0)
    avg_latency = sum(log["latency_ms"] for log in logs) / total if total > 0 else 0
    all_filtered_count = sum(1 for log in logs if log["all_filtered"])

    return ApiResponse(data={
        "logs": logs,
        "summary": {
            "total": total,
            "hit_rate": f"{hit_count}/{total} ({hit_count/total*100:.1f}%)" if total > 0 else "N/A",
            "all_filtered_rate": f"{all_filtered_count}/{total} ({all_filtered_count/total*100:.1f}%)" if total > 0 else "N/A",
            "avg_latency_ms": round(avg_latency),
        },
    })


@router.delete("/knowledge/{doc_id}")
async def delete_knowledge(
    doc_id: int,
    user_id: int = Depends(get_current_user),
    db=Depends(get_db),
):
    """删除知识库文档及其全部切片"""
    result = await db.execute(
        select(KnowledgeDocument).where(KnowledgeDocument.id == doc_id)
    )
    doc = result.scalar()
    if doc is None:
        return JSONResponse(status_code=404, content={"code": 404, "message": "文档不存在"})

    from api.agent.graph import get_pool
    pool = get_pool()
    await kb_delete_document(pool, doc.id)

    await db.delete(doc)
    await db.commit()
    logger.info(f"知识库文档已删除 id={doc_id}")
    return ApiResponse(message="已删除")
