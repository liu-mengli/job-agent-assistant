"""SOP 技术手册切片 —— 每个页面/章节作为一个完整切片"""

import re
from typing import TypedDict

from config import settings


class KBChunk(TypedDict):
    content: str
    section: str
    images: list[str]  # 该切片关联的图片文件名列表

# --- 页面/章节标题模式 ---
# 编号式：4. Engineer Page 或 4.10 Position Check
_NUMBERED_SECTION_RE = re.compile(r"^[\s]*(\d+[\.\、](?:\d+)?)\s+(.+)$")
# 命名式：Yield Control (良率控制設定)、安全概要
_NAMED_SECTION_RE = re.compile(
    r"^[\s]*(?:"
    r"\d+\.\d*\s+|"
    r"安全概要|主畫面|主要操作介面|"
    r"Yield Control|良率控制|"
    r"Offset\s*Setting|各軸位置修正|"
    r"Device Setting|測試設備|Tester Setup|Site Setting|"
    r"Event\s*Log|事件記錄|"
    r"Contact\s*Setting|手測與壓貨|"
    r"Tray\s*File|料盤資料|"
    r"Category\s*Setup|分類設定|"
    r"Interface\s*File|通訊介面|"
    r"Speed\s*Setting|速度設定|"
    r"Timer\s*Setting|時間設定|"
    r"Motor\s*Monitor|馬達監視|"
    r"IO\s*Monitor|IO\s*監視|"
    r"Device\s*Setup|Position\s*Check|點位確認|"
    r"Pin1\s*Check|Pin1\s*功能|"
    r"SLT\s*Test\s*Program|"
    r"Auto\s*Alignment|自動位置校正|"
    r"PM\s*Schedule|保養排程|"
    r"Run\s*Page|生產執行|"
    r"User\s*Page|作業員操作|"
    r"Setup\s*Page|設定工程師|"
    r"Engineer\s*Page|系統工程師|"
    r"使用手冊|操作手冊|"
    r"Lidar|Cobra|溫度控制|"
    r"Parament|參數設定"
    r")[\s]*[\(（].*[\)）]?",
    re.IGNORECASE,
)

MAX_CHUNK_SIZE = 800   # 目标每切片最大字数，超过按段落二次拆分
MIN_CHUNK_CHARS = 40

# 自然语言信号检测
_PUNCT_RE = re.compile(r"[，。、：；！？「」『』（）【】《》—…]")
_COMMON_WORD_RE = re.compile(
    r"(操作|設定|測試|功能|使用|顯示|系統|模式|狀態|自動|手動|"
    r"按鈕|畫面|檢查|確認|選擇|執行|處理|控制|資料|參數|裝置|"
    r"設備|輸入|輸出|啟動|停止|錯誤|訊息|記錄|管理|生產|程式|"
    r"溫度|速度|壓力|每個|所有|進行|是否|可以|必須|需要|如果|"
    r"目前|不會|儀器|注意|警告|危險|電源|安全|保護|維護|校正|"
    r"元件|產品|手臂|位置|頁面|離開|儲存|清除|忽略|關閉|開啟)"
)


def _is_garbled(text: str) -> bool:
    if not text:
        return True
    signal_count = len(_PUNCT_RE.findall(text)) + len(_COMMON_WORD_RE.findall(text))
    return signal_count < 2


def _is_section_header(text: str) -> str | None:
    """检测文本是否为章节/页面标题，返回标签名"""
    text = text.strip()
    if not text or len(text) > 200:
        return None

    m = _NUMBERED_SECTION_RE.match(text)
    if m:
        return f"{m.group(1)} {m.group(2)}"

    m = _NAMED_SECTION_RE.match(text)
    if m:
        label = m.group().strip().rstrip("：:").strip()
        if len(label) >= 3:
            return label

    return None


def split_manual(text: str) -> list[KBChunk]:
    """按页面/章节切片：检测章节标题 → 收集页面内容 → 一个页面对应一个切片"""
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    if not paragraphs:
        return []

    # 第一遍：找到所有章节标题位置，追踪父章节层级
    pages: list[tuple[str, str, int, int]] = []
    current_chapter = "全文"
    current_label = "全文"
    current_start = 0

    for i, para in enumerate(paragraphs):
        label = _is_section_header(para)
        if label:
            if i > current_start:
                pages.append((current_chapter, current_label, current_start, i))
            # 章级别标题（编号 1. / 2. / 10. …），更新父章节
            if re.match(r"^\d+\.\s", label):
                current_chapter = label
            elif current_label == "全文":
                # 第一个标题若未识别为章级别，仍设为父章节以防"全文"
                current_chapter = label
            current_label = label
            current_start = i + 1

    if current_start < len(paragraphs):
        pages.append((current_chapter, current_label, current_start, len(paragraphs)))

    # 第二遍：每页生成一个切片，子章节注入父章节上下文
    all_chunks: list[KBChunk] = []
    for chapter, label, start, end in pages:
        page_text = "\n\n".join(paragraphs[start:end])
        if not page_text or _is_garbled(page_text):
            continue
        if len(label) > 80:
            label = label[:80] + "..."

        if label == "全文":
            all_chunks.append({"content": page_text, "section": label, "images": []})
        elif chapter == label or chapter == "全文":
            # 章标题自身的内容，或父章节未知，保持原样
            all_chunks.append({"content": f"{label}\n{page_text}", "section": label, "images": []})
        else:
            # 子章节：注入父章节上下文
            section = f"{chapter} > {label}"
            content = f"{chapter}\n{label}\n{page_text}"
            all_chunks.append({"content": content, "section": section, "images": []})

    # 第三遍：超长切片按段落二次拆分
    result: list[KBChunk] = []
    for chunk in all_chunks:
        if len(chunk["content"]) <= MAX_CHUNK_SIZE:
            result.append(chunk)
        else:
            result.extend(_split_oversized(chunk))
    return result


def _split_oversized(chunk: KBChunk) -> list[KBChunk]:
    """将超长切片按段落边界拆分为 400-800 字的子切片"""
    paras = [p.strip() for p in chunk["content"].split("\n\n") if p.strip()]
    if len(paras) <= 1:
        return [chunk]

    sub_chunks: list[KBChunk] = []
    current = ""
    for para in paras:
        if len(current) + len(para) > MAX_CHUNK_SIZE and len(current) >= MIN_CHUNK_CHARS:
            sub_chunks.append({"content": current.strip(), "section": chunk["section"], "images": []})
            current = para
        else:
            current = f"{current}\n\n{para}" if current else para

    if len(current.strip()) >= MIN_CHUNK_CHARS:
        sub_chunks.append({"content": current.strip(), "section": chunk["section"], "images": []})
    elif sub_chunks:
        # 尾部剩余文本太短，合并到最后一个子切片
        sub_chunks[-1]["content"] += "\n\n" + current

    return sub_chunks if sub_chunks else [chunk]


def assign_images_to_chunks(
    chunks: list[KBChunk],
    section_images: dict[str, list[str]],
) -> list[KBChunk]:
    """将提取的图片按章节映射分配到对应切片。

    匹配策略：
    - 按 chunk.section（如 "Engineer Page > Position Check"）拆分层级
    - 父章节（Engineer Page → "4. Engineer Page"）和子章节（Position Check → "4.10 Position Check"）
      分别去 section_images 中匹配
    - 同一章节下的图片只分配给该章节的第一个 chunk（去重）
    """
    # 构建章节→已分配标记
    assigned: set[str] = set()

    for chunk in chunks:
        images: list[str] = []
        section = chunk.get("section", "")

        for part in section.split(" > "):
            part = part.strip()
            if not part:
                continue
            # 精确匹配
            if part in section_images:
                imgs = section_images[part]
            else:
                # 模糊匹配：section_images 的 key 可能是 "4. Engineer Page" 而 chunk 中是 "Engineer Page"
                imgs = []
                for key, val in section_images.items():
                    if part in key or key.endswith(part):
                        imgs = val
                        break

            # 同一章节的图只分配给第一个 chunk
            if part not in assigned:
                assigned.add(part)
                images.extend(imgs)

        if images:
            chunk["images"] = images

    total = sum(len(c.get("images", [])) for c in chunks)
    from api.log import logger
    logger.info(f"图片切片关联完成: {total} 张图片已分配到 {sum(1 for c in chunks if c.get('images'))} 个切片")
    return chunks
