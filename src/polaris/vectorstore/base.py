"""VectorStore 介面 + 共用資料型別。

★ 這是整個「本地先開發、再上雲」設計的核心 ★
- 本地：PgVectorStore（pgvector）
- 雲端：BigQueryStore（BigQuery VECTOR_SEARCH）
兩者都實作同一組方法，所以換後端時呼叫端一行都不用改。
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Document:
    """一段要入庫的文字（法說稿切塊 / 新聞 / 財報段落）。"""
    id: str
    content: str
    embedding: list[float] | None = None
    company: str | None = None
    period: str | None = None              # 例 "2024Q3"，供 Temporal Anchoring
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class SearchResult:
    """一筆檢索結果。"""
    id: str
    content: str
    score: float
    company: str | None = None
    period: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class VectorStore(ABC):
    """向量庫統一介面。新後端只要繼承它、實作這三個方法即可。"""

    @abstractmethod
    def add_documents(self, docs: list[Document]) -> None:
        """批次寫入 / upsert 文件（含向量）。"""

    @abstractmethod
    def search(
        self,
        query_embedding: list[float],
        top_k: int = 8,
        *,
        filters: dict[str, Any] | None = None,
    ) -> list[SearchResult]:
        """向量相似度檢索。filters 例：{"company": "2330", "period": "2024Q3"}。"""

    @abstractmethod
    def health_check(self) -> bool:
        """連線是否正常（CI / 啟動自檢用）。"""
