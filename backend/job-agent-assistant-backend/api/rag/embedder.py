"""本地 Embedding 模型 —— sentence-transformers，模块级单例"""

import os
os.environ.setdefault("HF_HUB_OFFLINE", "1")  # 必须在 import sentence_transformers 之前设置，防止国内网络超时

import numpy as np
from sentence_transformers import SentenceTransformer

from config import settings

_model: SentenceTransformer | None = None


def get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        _model = SentenceTransformer(settings.EMBEDDING_MODEL, device=settings.EMBEDDING_DEVICE)
    return _model


def embed(texts: list[str]) -> np.ndarray:
    """将文本列表转为向量矩阵 (N, 512)"""
    return get_model().encode(texts, normalize_embeddings=True)  # 归一化后余弦相似度 = 内积
