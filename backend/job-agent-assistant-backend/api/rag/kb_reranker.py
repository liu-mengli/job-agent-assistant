"""知识库 Reranker 模型 —— bge-reranker-v2-m3，模块级单例"""
import os
from config import settings

os.environ.setdefault("HF_HOME", settings.HF_HOME)
os.environ.setdefault("HF_HUB_OFFLINE", "1")

from sentence_transformers import CrossEncoder

_reranker_model = None


def get_reranker_model() -> CrossEncoder:
    global _reranker_model
    if _reranker_model is None:
        _reranker_model = CrossEncoder(
            settings.KB_RERANKER_MODEL,
            device=settings.KB_EMBEDDING_DEVICE,
            cache_folder=settings.HF_HOME,
        )
    return _reranker_model


def kb_rerank(
    query: str,
    candidates: list[dict],
    top_k: int = 5,
) -> list[dict]:
    """用 Cross-Encoder 对 Dense 检索结果精排。

    Args:
        query: 用户原始问题（用于交叉注意力匹配）。
        candidates: Dense 检索的候选结果列表，每项含 content / section / document_name / distance 等。
        top_k: 返回 top-k 条精排结果。

    Returns:
        精排后的结果列表（原 dict 中追加 rerank_score 字段）。
    """
    model = get_reranker_model()
    pairs = [(query, doc["content"]) for doc in candidates]
    scores = model.predict(pairs)
    for doc, score in zip(candidates, scores):
        doc["rerank_score"] = float(score)
    ranked = sorted(candidates, key=lambda d: d["rerank_score"], reverse=True)
    return ranked[:top_k]
