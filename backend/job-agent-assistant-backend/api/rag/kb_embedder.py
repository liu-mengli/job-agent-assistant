"""知识库 Embedding 模型 —— bge-m3 (1024维)，模块级单例，独立于简历 RAG"""

import os
from config import settings

# 必须在 import sentence_transformers 之前设置
os.environ.setdefault("HF_HOME", settings.HF_HOME)
os.environ.setdefault("HF_HUB_OFFLINE", "1")

import numpy as np
from sentence_transformers import SentenceTransformer

_kb_model = None


def get_kb_model() -> SentenceTransformer:
    global _kb_model
    if _kb_model is None:
        _kb_model = SentenceTransformer(
            settings.KB_EMBEDDING_MODEL,
            device=settings.KB_EMBEDDING_DEVICE,
            cache_folder=settings.HF_HOME,
        )
    return _kb_model


def kb_embed(texts: list[str]) -> np.ndarray:
    """将文本列表转为向量矩阵 (N, 1024)，已 L2 归一化"""
    return get_kb_model().encode(texts, normalize_embeddings=True)
