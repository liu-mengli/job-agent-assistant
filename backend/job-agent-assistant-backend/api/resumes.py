import asyncio
import os
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, File, UploadFile
from langchain_core.messages import AIMessage
from sqlalchemy import delete, select
from starlette.responses import JSONResponse

from api.database import get_db
from api.dependencies import get_current_user
from api.log import logger
from api.models.resume import ResumeDocument
from api.rag.chunker import split_text
from api.rag.embedder import embed
from api.rag.parser import parse_pdf
from api.rag.store import delete_document, insert_chunks
from api.schemas.response import ApiResponse
from config import settings

router = APIRouter()

os.makedirs(settings.UPLOAD_DIR, exist_ok=True)


@router.post("/resumes/upload", response_model=ApiResponse)
async def upload_resume(
    file: UploadFile = File(...),
    user_id: int = Depends(get_current_user),
):
    """上传 PDF 简历：解析 → 切片 → 向量化 → 入库（每用户限 1 份）"""
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        return ApiResponse(code=400, message="仅支持 PDF 文件")

    from api.agent.graph import get_pool
    pool = get_pool()

    # 1. 删除用户的旧简历（数据 + 文件）
    async with pool.connection() as conn:
        cur = await conn.execute(
            "SELECT id FROM resume_documents WHERE user_id = %s", (user_id,)
        )
        for row in await cur.fetchall():
            old_id = row[0]
            await delete_document(pool, old_id)
            await conn.execute("DELETE FROM resume_documents WHERE id = %s", (old_id,))
            # 清理旧磁盘文件
            for f in os.listdir(settings.UPLOAD_DIR):
                if f.endswith(".pdf"):
                    os.remove(os.path.join(settings.UPLOAD_DIR, f))
                    break

    save_name = f"{uuid4().hex}.pdf"
    save_path = os.path.join(settings.UPLOAD_DIR, save_name)

    try:
        content = await file.read()
        with open(save_path, "wb") as f:
            f.write(content)

        loop = asyncio.get_running_loop()
        text = await loop.run_in_executor(None, parse_pdf, save_path)
        if not text.strip():
            if os.path.exists(save_path):
                os.remove(save_path)
            return ApiResponse(code=400, message="PDF 中未检测到文本内容")

        chunks = split_text(text)
        if not chunks:
            if os.path.exists(save_path):
                os.remove(save_path)
            return ApiResponse(code=400, message="文本切片后无内容")

        texts = [c["content"] for c in chunks]
        embeddings = await loop.run_in_executor(None, embed, texts)

        async with pool.connection() as conn:
            cur = await conn.execute(
                "INSERT INTO resume_documents (user_id, filename, chunk_count) "
                "VALUES (%s, %s, %s) RETURNING id",
                (user_id, file.filename, len(chunks)),
            )
            row = await cur.fetchone()
            doc_id = row[0]

        await insert_chunks(pool, doc_id, chunks, embeddings)
        logger.info(f"简历上传完成 user={user_id} file={file.filename} chunks={len(chunks)}")

        # 向该用户所有已有会话的 checkpoint 注入简历失效提示，
        # 防止 LLM 在后续对话中依赖历史里的旧简历检索结果
        try:
            from api.agent.graph import get_graph

            graph = get_graph()
            async with pool.connection() as conn:
                cur = await conn.execute(
                    "SELECT session_id FROM sessions WHERE user_id = %s", (user_id,)
                )
                session_ids = [row[0] for row in await cur.fetchall()]

            notice = AIMessage(
                content=(
                    f"【系统通知】你的简历已于 {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')} 更新。"
                    "对话历史中关于旧简历的内容已失效，如需查询简历相关信息请重新提问，"
                    "我将重新检索最新简历。"
                )
            )
            for sid in session_ids:
                await graph.aupdate_state(
                    {"configurable": {"thread_id": sid}},
                    {"messages": [notice]},
                )
            if session_ids:
                logger.info(f"已向 {len(session_ids)} 个会话注入简历失效提示")
        except Exception:
            logger.exception("注入简历失效提示失败（不影响上传主流程）")

        return ApiResponse(data={"id": doc_id, "filename": file.filename, "chunk_count": len(chunks)})

    except Exception:
        if os.path.exists(save_path):
            os.remove(save_path)
        raise


@router.get("/resumes", response_model=ApiResponse)
async def list_resumes(
    user_id: int = Depends(get_current_user),
    db=Depends(get_db),
):
    """当前用户的简历列表"""
    result = await db.execute(
        select(ResumeDocument)
        .where(ResumeDocument.user_id == user_id)
        .order_by(ResumeDocument.created_at.desc())
    )
    rows = result.scalars().all()
    return ApiResponse(data={
        "resumes": [
            {
                "id": r.id,
                "filename": r.filename,
                "chunk_count": r.chunk_count,
                "created_at": r.created_at.isoformat(),
            }
            for r in rows
        ]
    })


@router.delete("/resumes/{resume_id}")
async def delete_resume(
    resume_id: int,
    user_id: int = Depends(get_current_user),
    db=Depends(get_db),
):
    """删除简历及其全部切片"""
    result = await db.execute(
        select(ResumeDocument).where(
            ResumeDocument.id == resume_id,
            ResumeDocument.user_id == user_id,
        )
    )
    doc = result.scalar()
    if doc is None:
        return JSONResponse(status_code=404, content={"code": 404, "message": "简历不存在"})

    from api.agent.graph import get_pool
    pool = get_pool()
    await delete_document(pool, doc.id)

    await db.delete(doc)
    await db.commit()
    logger.info(f"简历已删除 user={user_id} id={resume_id}")
    return ApiResponse(message="已删除")
