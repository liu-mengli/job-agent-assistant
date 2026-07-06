"""PDF 文本提取 —— PyMuPDF 提取 + easyocr 图片型 PDF 回退"""

import pymupdf

from api.log import logger

_ocr_reader = None


def _get_reader():
    """懒加载 easyocr Reader（首次调用自动下载模型 ~200MB）"""
    global _ocr_reader
    if _ocr_reader is None:
        import os
        from config import settings

        # 注入代理（如有配置）
        if settings.HTTP_PROXY:
            os.environ["HTTP_PROXY"] = settings.HTTP_PROXY
        if settings.HTTPS_PROXY:
            os.environ["HTTPS_PROXY"] = settings.HTTPS_PROXY

        import easyocr
        _ocr_reader = easyocr.Reader(["ch_sim", "en"], gpu=False)
        logger.info("easyocr Reader 已就绪")
    return _ocr_reader


def parse_pdf(file_path: str) -> str:
    """读取 PDF 文件，优先提取内嵌文本，无文字时回退 OCR"""
    import time

    doc = pymupdf.open(file_path)
    page_count = len(doc)
    pages_text = []
    ocr_pages = 0

    for page in doc:
        text = page.get_text().strip()
        if text:
            pages_text.append(text)
        else:
            ocr_pages += 1
            t0 = time.time()
            reader = _get_reader()
            pix = page.get_pixmap(dpi=200)
            img_bytes = pix.tobytes("png")
            results = reader.readtext(img_bytes, detail=0)
            ocr_text = "\n".join(results).strip()
            elapsed = time.time() - t0
            if ocr_text:
                logger.info(f"OCR 第 {page.number + 1}/{page_count} 页完成 ({elapsed:.0f}s, {len(ocr_text)} 字)")
            pages_text.append(ocr_text)

    doc.close()

    all_text = "\n\n".join(t for t in pages_text if t)
    if ocr_pages > 0:
        logger.info(f"PDF 解析完成: {page_count} 页, {ocr_pages} 页 OCR, {len(all_text)} 字")
    else:
        logger.info(f"PDF 解析完成: {page_count} 页, {len(all_text)} 字（纯文字提取）")
    return all_text
