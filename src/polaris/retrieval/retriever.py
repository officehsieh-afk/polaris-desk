"""4-way 混合檢索骨架（@R3）。

PRD：BM25 關鍵字 + Embedding 語意 + ColPali 多模態 + Cohere Rerank 重排。
W1 先做 1–2 路能撈到東西，W2 補齊 4 路 + rerank。
注意：檢索只透過 VectorStore 介面拿資料，不直接碰 DB ——
這樣本地(pgvector) / 雲端(bigquery) 對檢索層是透明的。
"""
from __future__ import annotations

from dataclasses import dataclass

from ..vectorstore import SearchResult, get_vector_store


@dataclass
class HybridRetriever:
    top_k: int = 8

    def __post_init__(self) -> None:
        self.store = get_vector_store()      # 自動拿到本地或雲端後端

    def retrieve(self, query: str, *, filters: dict | None = None) -> list[SearchResult]:
        # TODO(@R3) W1：先做向量檢索
        #   1) 用 GeminiClient.embed(query) 取得查詢向量
        #   2) self.store.search(query_vec, self.top_k, filters=filters)
        # TODO(@R3) W2：加 BM25 + ColPali + Cohere Rerank，合併重排
        #   - Cohere Rerank：client.v2.rerank(model="rerank-v4.0", ...)（最新；或 rerank-v3.5）
        #   - ColPali：vidore/colqwen2-v1.0（Qwen2-VL，較新）或 vidore/colpali-v1.3；需 GPU + bfloat16
        #     ※ 見 TD-01：gemini-embedding-2 本身已多模態，ColPali 可能變「加分」而非必要
        raise NotImplementedError("HybridRetriever.retrieve 待 R3 實作")
