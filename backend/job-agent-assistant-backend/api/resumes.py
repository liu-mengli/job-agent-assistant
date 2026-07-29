import asyncio
import os
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, File, UploadFile
from fastapi.responses import FileResponse
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
    """上传 PDF 简历：先存文件并立即返回，后台异步处理 OCR + 向量化"""
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        return ApiResponse(code=400, message="仅支持 PDF 文件")

    from api.agent.graph import get_pool
    pool = get_pool()

    # 1. 删除用户的旧简历（避免新旧共存）
    async with pool.connection() as conn:
        cur = await conn.execute(
            "SELECT id, file_path FROM resume_documents WHERE user_id = %s", (user_id,)
        )
        for row in await cur.fetchall():
            old_id, old_file_path = row[0], row[1]
            await delete_document(pool, old_id)
            await conn.execute("DELETE FROM resume_documents WHERE id = %s", (old_id,))
            if old_file_path:
                old_path = os.path.join(settings.UPLOAD_DIR, old_file_path)
                if os.path.exists(old_path):
                    os.remove(old_path)
            else:
                # 兼容旧记录（无 file_path）：删除目录下任意 .pdf
                for f in os.listdir(settings.UPLOAD_DIR):
                    if f.endswith(".pdf"):
                        os.remove(os.path.join(settings.UPLOAD_DIR, f))
                        break

    # 2. 保存 PDF 文件
    save_name = f"{uuid4().hex}.pdf"
    save_path = os.path.join(settings.UPLOAD_DIR, save_name)
    content = await file.read()
    with open(save_path, "wb") as f:
        f.write(content)

    # 3. 先插入一条 processing 状态的记录，立即返回给前端
    async with pool.connection() as conn:
        cur = await conn.execute(
            "INSERT INTO resume_documents (user_id, filename, chunk_count, status, file_path) "
            "VALUES (%s, %s, 0, 'processing', %s) RETURNING id",
            (user_id, file.filename, save_name),
        )
        row = await cur.fetchone()
        doc_id = row[0]

    logger.info(f"简历上传已接收 user={user_id} file={file.filename} doc_id={doc_id}")

    # 4. 后台异步处理：OCR → 切片 → 向量化 → 入库
    asyncio.create_task(
        _process_resume_background(doc_id, user_id, save_path, file.filename, pool)
    )

    return ApiResponse(
        data={"id": doc_id, "filename": file.filename, "chunk_count": 0, "status": "processing"}
    )


async def _process_resume_background(
    doc_id: int,
    user_id: int,
    save_path: str,
    filename: str,
    pool,
) -> None:
    """后台任务：OCR → 切片 → 向量化 → 入库 → 更新状态 → 注入 checkpoint 通知"""
    from api.agent.graph import get_graph

    try:
        logger.info(f"后台处理开始 doc_id={doc_id} file={filename}")

        loop = asyncio.get_running_loop()
        text = await loop.run_in_executor(None, parse_pdf, save_path)
        if not text.strip():
            await _update_resume_status(pool, doc_id, "error", "PDF 中未检测到文本内容")
            return

        chunks = split_text(text)
        if not chunks:
            await _update_resume_status(pool, doc_id, "error", "文本切片后无内容")
            return

        texts = [c["content"] for c in chunks]
        embeddings = await loop.run_in_executor(None, embed, texts)

        await insert_chunks(pool, doc_id, chunks, embeddings)

        async with pool.connection() as conn:
            await conn.execute(
                "UPDATE resume_documents SET chunk_count = %s, status = 'ready' WHERE id = %s",
                (len(chunks), doc_id),
            )
        logger.info(f"后台处理完成 doc_id={doc_id} file={filename} chunks={len(chunks)}")

        # 向该用户所有已有会话注入简历失效提示
        try:
            graph = get_graph()
            async with pool.connection() as conn:
                cur = await conn.execute(
                    "SELECT session_id FROM sessions WHERE user_id = %s AND agent_type = 'job_advisor'",
                    (user_id,),
                )
                session_ids = [r[0] for r in await cur.fetchall()]

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

    except Exception:
        logger.exception(f"后台处理失败 doc_id={doc_id}")
        await _update_resume_status(pool, doc_id, "error", "服务器处理简历时出错")


async def _update_resume_status(pool, doc_id: int, status: str, error_message: str | None = None) -> None:
    async with pool.connection() as conn:
        await conn.execute(
            "UPDATE resume_documents SET status = %s, error_message = %s WHERE id = %s",
            (status, error_message, doc_id),
        )


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
                "status": getattr(r, "status", "ready"),
                "error_message": getattr(r, "error_message", None),
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

    # 删除磁盘上的文件
    if doc.file_path:
        file_path = os.path.join(settings.UPLOAD_DIR, doc.file_path)
        if os.path.exists(file_path):
            os.remove(file_path)

    await db.delete(doc)
    await db.commit()
    logger.info(f"简历已删除 user={user_id} id={resume_id}")
    return ApiResponse(message="已删除")


@router.get("/resumes/{resume_id}/download")
async def download_resume(
    resume_id: int,
    user_id: int = Depends(get_current_user),
    db=Depends(get_db),
):
    """下载简历 PDF 文件"""
    result = await db.execute(
        select(ResumeDocument).where(
            ResumeDocument.id == resume_id,
            ResumeDocument.user_id == user_id,
        )
    )
    doc = result.scalar()
    if doc is None:
        return JSONResponse(status_code=404, content={"code": 404, "message": "简历不存在"})

    if not doc.file_path:
        return JSONResponse(status_code=404, content={"code": 404, "message": "简历文件不存在"})

    file_path = os.path.join(settings.UPLOAD_DIR, doc.file_path)
    if not os.path.exists(file_path):
        return JSONResponse(status_code=404, content={"code": 404, "message": "简历文件不存在"})

    return FileResponse(
        path=file_path,
        filename=doc.filename,
        media_type="application/pdf",
    )


@router.get("/resume/pdf")
async def download_static_resume():
    """下载固定简历 PDF（路径和文件名由 RESUME_DIR / RESUME_PDF_NAME 配置）"""
    file_path = os.path.join(settings.RESUME_DIR, settings.RESUME_PDF_NAME)
    if not os.path.exists(file_path):
        return JSONResponse(status_code=404, content={"code": 404, "message": "简历文件不存在，请将 PDF 放置于 uploads/resume/ 目录"})
    return FileResponse(
        path=file_path,
        filename=settings.RESUME_PDF_NAME,
        media_type="application/pdf",
    )
