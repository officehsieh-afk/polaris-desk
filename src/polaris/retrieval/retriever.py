"""4-way 混合檢索（@R3）。

低成本、確定性優先；外呼路全部 opt-in：
- 不設任何 key 也能跑（預設只走 BM25，0 外呼）
- BM25 keyword ranking 永遠可用
- 向量語意：透過可注入的 embedding_fn + VectorStore.search 介面接入（路 2）
- Cohere Rerank（rerank-v4.0）：注入 reranker 即啟用，對候選重排（路 3，見 rerank.py）
- 回傳 SearchResult，讓 Writer 後續可以接 citation
- ColPali：待 R4 POC 上線再補（路 4）
"""
from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from rank_bm25 import BM25Okapi

from ..config import settings
from ..vectorstore import SearchResult, VectorStore, get_vector_store
from .rerank import Reranker, active_reranker


EmbeddingFn = Callable[[str], list[float]]


_FALLBACK_CORPUS = [
    SearchResult(
        id="stub-2330-2025Q1-gm",
        content="台積電 2025Q1 法說摘要：毛利率受到匯率、產品組合與產能利用率影響。",
        score=0.0,
        company="2330",
        period="2025Q1",
        metadata={"source_id": "stub-2330-2025Q1-gm", "origin": "keyword_fallback"},
    ),
    SearchResult(
        id="stub-2330-2024Q4-revenue",
        content="台積電 2024Q4 法說摘要：營收成長主要來自高效能運算與 AI 相關需求。",
        score=0.0,
        company="2330",
        period="2024Q4",
        metadata={"source_id": "stub-2330-2024Q4-revenue", "origin": "keyword_fallback"},
    ),
    SearchResult(
        id="stub-2317-2025Q1-segment",
        content="鴻海 2025Q1 法說摘要：營收組成涵蓋消費智能、雲端網路、電腦終端與元件。",
        score=0.0,
        company="2317",
        period="2025Q1",
        metadata={"source_id": "stub-2317-2025Q1-segment", "origin": "keyword_fallback"},
    ),
]


def _token_list(text: str) -> list[str]:
    """Tokenize mixed Chinese/English finance text for deterministic BM25.

    The CJK branch adds short n-grams so queries like ``毛利率`` still match
    longer chunks such as ``毛利率受到匯率影響``.
    """
    tokens: list[str] = []
    for match in re.findall(r"[A-Za-z0-9]+|[\u4e00-\u9fff]+", text.lower()):
        if re.fullmatch(r"[\u4e00-\u9fff]+", match):
            if len(match) <= 4:
                tokens.append(match)
            for size in (2, 3):
                tokens.extend(match[i : i + size] for i in range(len(match) - size + 1))
        else:
            tokens.append(match)
    return tokens


def _matches_filters(result: SearchResult, filters: dict | None) -> bool:
    if not filters:
        return True
    for key, value in filters.items():
        if value is None:
            continue
        if key == "company" and result.company != value:
            return False
        if key == "period" and result.period != value:
            return False
    return True


def _copy_result(result: SearchResult, *, score: float, origin: str) -> SearchResult:
    metadata = dict(result.metadata)
    metadata["origin"] = origin
    metadata["retrieval_channels"] = [origin]
    return SearchResult(
        id=result.id,
        content=result.content,
        score=score,
        company=result.company,
        period=result.period,
        metadata=metadata,
    )


def _normalize_vector_result(result: SearchResult) -> SearchResult:
    metadata = dict(result.metadata)
    metadata["origin"] = "vector"
    metadata["retrieval_channels"] = ["vector"]
    return SearchResult(
        id=result.id,
        content=result.content,
        score=float(result.score),
        company=result.company,
        period=result.period,
        metadata=metadata,
    )


def _merge_results(results: list[SearchResult]) -> list[SearchResult]:
    merged: dict[str, SearchResult] = {}
    for result in results:
        existing = merged.get(result.id)
        if existing is None:
            merged[result.id] = result
            continue

        channels = list(existing.metadata.get("retrieval_channels", []))
        for channel in result.metadata.get("retrieval_channels", []):
            if channel not in channels:
                channels.append(channel)

        winner = result if result.score > existing.score else existing
        metadata: dict[str, Any] = dict(winner.metadata)
        metadata["retrieval_channels"] = channels
        merged[result.id] = SearchResult(
            id=winner.id,
            content=winner.content,
            score=winner.score,
            company=winner.company,
            period=winner.period,
            metadata=metadata,
        )
    return list(merged.values())


@dataclass
class HybridRetriever:
    top_k: int = 8
    store: VectorStore | None = None
    embedding_fn: EmbeddingFn | None = None
    reranker: Reranker | None = None

    def __post_init__(self) -> None:
        if self.store is None:
            self.store = get_vector_store()

    def _bm25_search(self, query: str, filters: dict | None) -> list[SearchResult]:
        candidates = [item for item in _FALLBACK_CORPUS if _matches_filters(item, filters)]
        query_tokens = _token_list(query)
        if not candidates or not query_tokens:
            return []

        corpus_tokens = [
            _token_list(f"{item.id} {item.company or ''} {item.period or ''} {item.content}")
            for item in candidates
        ]
        bm25 = BM25Okapi(corpus_tokens)
        bm25_scores = list(bm25.get_scores(query_tokens))
        raw_scores: list[float] = []
        for item_tokens, bm25_score in zip(corpus_tokens, bm25_scores, strict=True):
            overlap_score = len(set(query_tokens) & set(item_tokens)) / max(len(query_tokens), 1)
            raw_scores.append(float(bm25_score) if bm25_score > 0 else overlap_score)

        max_score = max(raw_scores) if raw_scores else 0.0

        ranked: list[SearchResult] = []
        for item, score in zip(candidates, raw_scores, strict=True):
            if score <= 0:
                continue
            normalized_score = (score / max_score) * 0.5 if max_score else 0.0
            ranked.append(_copy_result(item, score=normalized_score, origin="bm25"))
        return ranked

    def _vector_search(self, query: str, filters: dict | None) -> list[SearchResult]:
        if self.embedding_fn is None or self.store is None:
            return []
        try:
            query_embedding = self.embedding_fn(query)
            if not query_embedding:
                return []
            results = self.store.search(query_embedding, self.top_k, filters=filters)
        except Exception:  # noqa: BLE001 - vector backend is optional in D3; BM25 stays available
            return []
        return [_normalize_vector_result(result) for result in results]

    def _by_score(self, merged: list[SearchResult]) -> list[SearchResult]:
        merged.sort(key=lambda r: r.score, reverse=True)
        return merged[: self.top_k]

    def _apply_rerank(self, query: str, merged: list[SearchResult]) -> list[SearchResult]:
        """第 3 路：用注入的 reranker（Cohere `rerank-v4.0`）重排候選。

        沒注入 reranker → 維持原本分數排序。rerank 失敗（含外呼錯誤）一律
        graceful fallback 回分數排序，不可讓檢索掛掉（鏡像 ``_vector_search``）。
        """
        if self.reranker is None or not merged:
            return self._by_score(merged)
        try:
            reranked = self.reranker.rerank(query, merged, top_k=self.top_k)
        except Exception:  # noqa: BLE001 - rerank 是強化路，壞了退分數排序即可
            return self._by_score(merged)
        return reranked[: self.top_k]

    def retrieve(self, query: str, *, filters: dict | None = None) -> list[SearchResult]:
        """Retriever：BM25 keyword + optional vector + optional Cohere rerank。

        Vector / rerank 都是 opt-in（``embedding_fn`` / ``reranker``），所以本地
        測試與個人開發預設不會誤花 API 額度。BM25 永遠可用。
        """
        query = (query or "").strip()
        if not query:
            return []

        merged = _merge_results([
            *self._bm25_search(query, filters),
            *self._vector_search(query, filters),
        ])
        return self._apply_rerank(query, merged)


def build_retriever(*, top_k: int | None = None) -> HybridRetriever:
    """組裝可直接用的 3 路檢索器：BM25 + Gemini 向量 + Cohere rerank。

    外呼路全部 graceful degrade（demo / CI 無金鑰也能跑、0 外呼）：
    - 有 ``GEMINI_API_KEY`` → 接 Gemini embedding（向量路）；否則 embedding_fn=None，
      只走 BM25。**不**產假向量（假向量會毒化檢索，鏡像 ingestion 的誠實原則）。
    - 有 ``COHERE_API_KEY`` → 接 Cohere rerank（第 3 路）；否則退分數排序。

    與 ingestion 的差異：ingestion 無金鑰要誠實失敗（不可入假向量）；檢索無金鑰則
    降級 BM25 即可——BM25 永遠可用，檢索仍有結果。
    """
    from ..llm.gemini import active_llm  # 延遲 import，無金鑰時不建 Gemini client

    client = active_llm()
    embedding_fn = client.embed if client is not None else None
    return HybridRetriever(
        top_k=settings.top_k if top_k is None else top_k,
        embedding_fn=embedding_fn,
        reranker=active_reranker(),
    )
