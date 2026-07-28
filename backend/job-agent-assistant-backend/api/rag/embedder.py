"""本地 Embedding 模型 —— sentence-transformers，模块级单例（简历 RAG — bge-small）"""

import os
from config import settings

# 必须在 import sentence_transformers 之前设置，否则 huggingface_hub 不会读取
os.environ.setdefault("HF_HOME", settings.HF_HOME)
os.environ.setdefault("HF_HUB_OFFLINE", "1")

import numpy as np
from sentence_transformers import SentenceTransformer

_model = None


def get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        _model = SentenceTransformer(
            settings.EMBEDDING_MODEL,
            device=settings.EMBEDDING_DEVICE,
            cache_folder=settings.HF_HOME,
        )
    return _model


def embed(texts: list[str]) -> np.ndarray:
    """将文本列表转为向量矩阵 (N, 512)"""
    return get_model().encode(texts, normalize_embeddings=True)
