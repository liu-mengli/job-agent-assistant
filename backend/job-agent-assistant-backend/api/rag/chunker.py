"""语义切片 —— 按简历章节标题 → 段落 → 兜底字符数，三层层级切分"""

import re
from typing import TypedDict

from langchain_text_splitters import RecursiveCharacterTextSplitter

from config import settings

# --- 第一层：章节标题模式 ---
# 匹配简历常见章节标题（中文 + 英文常见写法）
SECTION_PATTERN = re.compile(
    r"^[\s]*(?:"
    r"个人信息|个人资料|基本信息|求职意向|期望职位|期望城市|期望薪资|"
    r"教育背景|教育经历|学历背景|学习经历|"
    r"工作经历|工作履历|实习经历|工作经验|职场经历|"
    r"项目经验|项目经历|项目介绍|项目描述|"
    r"专业技能|技术栈|技术能力|掌握技能|"
    r"自我评价|自我介绍|个人总结|自我描述|"
    r"语言能力|语言水平|外语能力|"
    r"获奖证书|荣誉证书|证书资质|所获荣誉|"
    r"联系方式|联系电话|联系邮箱|"
    r"在校经历|校园经历|社团经历|组织经历|"
    r"培训经历|培训认证|"
    r"论文专利|科研成果|学术成果|"
    r"WORK EXPERIENCE|EDUCATION|PROJECT|SKILLS|PROFESSIONAL|TECHNICAL|"
    r"CERTIFICAT|LANGUAGE|CONTACT|SUMMARY|PROFILE"
    r")[\s:：]*(?:\n|$)",
    re.IGNORECASE | re.MULTILINE,
)

# --- 第三层：超长段落兜底 ---
_fallback_splitter = RecursiveCharacterTextSplitter(
    chunk_size=1000,
    chunk_overlap=80,
    separators=["\n\n", "\n", "。", ". ", "；", "; "],
    is_separator_regex=False,
)

MAX_CHUNK_SIZE = 1000


class Chunk(TypedDict):
    content: str
    section: str  # 章节标签，检索结果可溯源


def _guess_section_label(text: str) -> str:
    """从章节文本首行提取标签"""
    m = SECTION_PATTERN.match(text)
    if m:
        label = m.group().strip().rstrip("：:").strip()
        return label if label else "其他"
    return "其他"


def split_text(text: str) -> list[Chunk]:
    """三层层级切片：章节标题 → 空行段落 → 字符数兜底"""
    # 第一层：找章节边界
    matches = list(SECTION_PATTERN.finditer(text))

    if not matches:
        # 没有检测到章节标题，全文当作一个段落用兜底策略
        return _finalize_chunks(text, "全文")

    segments: list[tuple[str, str]] = []  # [(标签, 文本)]

    # 第一个标题之前的内容
    first_match = matches[0]
    if first_match.start() > 0:
        prefix = text[: first_match.start()].strip()
        if prefix:
            segments.append((_guess_section_label(prefix), prefix))

    # 每两个标题之间的内容
    for i, m in enumerate(matches):
        label = _guess_section_label(m.group())
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[start:end].strip()
        if body:
            # 去掉标题行本身，但如果正文为空则保留标题行作为上下文
            body_lines = body.split("\n", 1)
            if len(body_lines) > 1 and body_lines[1].strip():
                body = body_lines[1].strip()
            segments.append((label, body))

    # 第二层 + 第三层
    all_chunks: list[Chunk] = []
    for label, body_text in segments:
        paragraphs = [p.strip() for p in body_text.split("\n\n") if p.strip()]
        for para in paragraphs:
            if len(para) <= MAX_CHUNK_SIZE:
                all_chunks.append({"content": para, "section": label})
            else:
                # 第三层兜底
                for sub in _fallback_splitter.split_text(para):
                    all_chunks.append({"content": sub, "section": label})

    return all_chunks


def _finalize_chunks(text: str, label: str) -> list[Chunk]:
    """无章节标题时的兜底处理"""
    chunks: list[Chunk] = []
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    for para in paragraphs:
        if len(para) <= MAX_CHUNK_SIZE:
            chunks.append({"content": para, "section": label})
        else:
            for sub in _fallback_splitter.split_text(para):
                chunks.append({"content": sub, "section": label})
    return chunks
