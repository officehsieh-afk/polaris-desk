"""向量庫抽象層 —— 本地→雲端的核心。

一個介面（base.VectorStore）、兩個實作（pgvector / bigquery）、一個工廠（factory）。
呼叫端永遠只用 `get_vector_store()`，不直接 new 任何實作。
"""
from .base import Document, SearchResult, VectorStore
from .factory import get_vector_store

__all__ = ["Document", "SearchResult", "VectorStore", "get_vector_store"]
