"""向量庫工廠 —— 呼叫端唯一入口。

用法：
    from polaris.vectorstore import get_vector_store
    store = get_vector_store()        # 依 .env 的 VECTOR_BACKEND 自動回對的實作
    store.search(query_embedding, top_k=8)

切換本地 / 雲端：只改 .env 的 VECTOR_BACKEND，這裡與呼叫端都不用動。
"""
from __future__ import annotations

from ..config import settings as default_settings
from .base import VectorStore
from .bigquery_store import BigQueryStore
from .pgvector_store import PgVectorStore

_REGISTRY: dict[str, type[VectorStore]] = {
    "pgvector": PgVectorStore,
    "bigquery": BigQueryStore,
}


def get_vector_store(settings=None) -> VectorStore:
    s = settings or default_settings
    backend = s.vector_backend.lower()
    try:
        cls = _REGISTRY[backend]
    except KeyError:
        raise ValueError(
            f"未知的 VECTOR_BACKEND: {backend!r}，可選 {sorted(_REGISTRY)}"
        ) from None
    return cls(s)
