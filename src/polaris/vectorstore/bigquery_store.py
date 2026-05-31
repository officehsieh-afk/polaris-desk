"""雲端向量庫實作：BigQuery VECTOR_SEARCH（W2 Day 10 之後切換用）。

@R4：W2 把這三個方法填起來。介面與 PgVectorStore 完全相同，
所以切換時呼叫端不用改 —— 只改 .env 的 VECTOR_BACKEND=bigquery。
"""
from __future__ import annotations

from typing import Any

from .base import Document, SearchResult, VectorStore


class BigQueryStore(VectorStore):
    def __init__(self, settings) -> None:
        self.settings = settings
        self._client = None  # 延遲建立

    def _get_client(self):
        if self._client is None:
            from google.cloud import bigquery  # 延遲 import
            self._client = bigquery.Client(project=self.settings.gcp_project)
        return self._client

    def add_documents(self, docs: list[Document]) -> None:
        # TODO(@R4)：load_table_from_json / MERGE 進 `{dataset}.chunks`
        raise NotImplementedError("BigQueryStore.add_documents 待 R4 W2 實作")

    def search(
        self,
        query_embedding: list[float],
        top_k: int = 8,
        *,
        filters: dict[str, Any] | None = None,
    ) -> list[SearchResult]:
        # TODO(@R4)：用 VECTOR_SEARCH(TABLE ..., 'embedding', ...) 查 top_k
        raise NotImplementedError("BigQueryStore.search 待 R4 W2 實作")

    def health_check(self) -> bool:
        # TODO(@R4)：client.query("SELECT 1").result()
        raise NotImplementedError("BigQueryStore.health_check 待 R4 W2 實作")
