"""本地向量庫實作：Postgres + pgvector（W1–W2 用）。

@R4：W1 把這三個方法填起來。重相依（psycopg）採延遲 import，
所以還沒安裝 / 還沒接 DB 時，骨架與測試仍可運行。
"""
from __future__ import annotations

from typing import Any

from .base import Document, SearchResult, VectorStore


class PgVectorStore(VectorStore):
    def __init__(self, settings) -> None:
        self.settings = settings
        self._conn = None  # 延遲連線

    def _connect(self):
        """延遲建立連線（第一次用到才連）。"""
        if self._conn is None:
            import psycopg  # 延遲 import
            self._conn = psycopg.connect(self.settings.database_url)
        return self._conn

    def add_documents(self, docs: list[Document]) -> None:
        # TODO(@R4)：INSERT ... ON CONFLICT (id) DO UPDATE，寫入 chunks 表
        #   embedding 欄位型別 VECTOR(768)，見 scripts/init_pgvector.sql
        raise NotImplementedError("PgVectorStore.add_documents 待 R4 W1 實作")

    def search(
        self,
        query_embedding: list[float],
        top_k: int = 8,
        *,
        filters: dict[str, Any] | None = None,
    ) -> list[SearchResult]:
        # TODO(@R4)：SELECT ... ORDER BY embedding <=> %s LIMIT %s（cosine 近似）
        #   filters 轉成 WHERE company=... AND period=...
        raise NotImplementedError("PgVectorStore.search 待 R4 W1 實作")

    def health_check(self) -> bool:
        # TODO(@R4)：SELECT 1
        raise NotImplementedError("PgVectorStore.health_check 待 R4 W1 實作")
