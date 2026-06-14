"""檢索層（@R3）：BM25 + 向量語意 + Cohere Rerank 混合檢索。"""
from __future__ import annotations

from .rerank import (
    DEFAULT_RERANK_MODEL,
    CohereReranker,
    Reranker,
    active_reranker,
    cohere_available,
)
from .retriever import EmbeddingFn, HybridRetriever, build_retriever

__all__ = [
    "HybridRetriever",
    "build_retriever",
    "EmbeddingFn",
    "Reranker",
    "CohereReranker",
    "active_reranker",
    "cohere_available",
    "DEFAULT_RERANK_MODEL",
]
