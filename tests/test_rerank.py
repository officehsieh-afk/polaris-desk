"""第 3 路檢索：Cohere Rerank（`client.v2.rerank`, `rerank-v4.0`）。

全程 token=0：注入 fake client / fake reranker，不碰真 Cohere API（憲法成本紀律、
NFR-W-002 精神）。涵蓋三層：
- CohereReranker 轉接層（呼叫形態、結果對應、接地註記）
- active_reranker / cohere_available 的「無金鑰 = 不外呼」開關
- HybridRetriever 串接（委派、graceful fallback、不影響舊行為）
"""
from __future__ import annotations

import types

import pytest

from polaris.retrieval.rerank import (
    DEFAULT_RERANK_MODEL,
    CohereReranker,
    active_reranker,
    cohere_available,
)
from polaris.retrieval.retriever import HybridRetriever
from polaris.vectorstore import SearchResult


def _sr(id: str, content: str, *, score: float = 0.0, company=None, period=None, **meta) -> SearchResult:
    return SearchResult(
        id=id, content=content, score=score, company=company, period=period, metadata=dict(meta)
    )


class _FakeCohereClient:
    """模擬 cohere.ClientV2.rerank：記下呼叫並依預設順序回 relevance_score。"""

    def __init__(self, order: list[tuple[int, float]]):
        self._order = order  # [(documents 內的 index, relevance_score), ...]
        self.calls: list[dict] = []

    def rerank(self, *, model, query, documents, top_n=None):
        self.calls.append(
            {"model": model, "query": query, "documents": list(documents), "top_n": top_n}
        )
        results = [
            types.SimpleNamespace(index=idx, relevance_score=score) for idx, score in self._order
        ]
        if top_n is not None:
            results = results[:top_n]
        return types.SimpleNamespace(results=results)


# --- CohereReranker 轉接層 ---------------------------------------------------

def test_cohere_reranker_reorders_and_annotates():
    docs = [
        _sr("a", "台積電 2025Q1 毛利率受匯率影響", retrieval_channels=["bm25"], origin="bm25"),
        _sr("b", "鴻海 2025Q1 營收組成涵蓋雲端網路", retrieval_channels=["vector"], origin="vector"),
    ]
    # fake 判定 documents[1]（"b"）最相關，其次 documents[0]
    client = _FakeCohereClient(order=[(1, 0.92), (0, 0.40)])
    reranker = CohereReranker(client=client)

    out = reranker.rerank("台積電 毛利率", docs, top_k=2)

    # 用 spec 指定的模型 + 純字串 documents 呼叫
    assert DEFAULT_RERANK_MODEL == "rerank-v4.0"
    assert client.calls[0]["model"] == "rerank-v4.0"
    assert client.calls[0]["query"] == "台積電 毛利率"
    assert client.calls[0]["documents"] == [docs[0].content, docs[1].content]
    assert client.calls[0]["top_n"] == 2

    # 依 relevance 重排：b 在前
    assert [r.id for r in out] == ["b", "a"]
    assert out[0].score == pytest.approx(0.92)
    assert out[0].metadata["reranked"] is True
    assert out[0].metadata["rerank_model"] == "rerank-v4.0"
    assert out[0].metadata["rerank_score"] == pytest.approx(0.92)
    # 原檢索通道保留 + 標記第三路（接地 / provenance）
    assert "vector" in out[0].metadata["retrieval_channels"]
    assert "cohere_rerank" in out[0].metadata["retrieval_channels"]


def test_cohere_reranker_truncates_to_top_k():
    docs = [_sr(c, c) for c in ("a", "b", "c")]
    client = _FakeCohereClient(order=[(2, 0.9), (0, 0.8), (1, 0.1)])
    reranker = CohereReranker(client=client)

    out = reranker.rerank("q", docs, top_k=2)

    assert client.calls[0]["top_n"] == 2
    assert [r.id for r in out] == ["c", "a"]


def test_cohere_reranker_noops_without_documents():
    client = _FakeCohereClient(order=[])
    reranker = CohereReranker(client=client)

    assert reranker.rerank("q", [], top_k=5) == []
    # 空 query 直接原樣返回，不外呼
    passthrough = reranker.rerank("   ", [_sr("a", "a")], top_k=5)
    assert [r.id for r in passthrough] == ["a"]
    assert client.calls == []


# --- 開關：無金鑰 = 不外呼（CI token=0）---------------------------------------

def test_cohere_available_and_active_reranker_off_without_key(monkeypatch):
    from polaris.retrieval import rerank as rr

    monkeypatch.setattr(rr.settings, "cohere_api_key", "")
    assert cohere_available() is False
    assert active_reranker() is None

    # `.env` 佔位字串（# 開頭）視同未設定
    monkeypatch.setattr(rr.settings, "cohere_api_key", "# 必填：你的 Cohere 金鑰")
    assert cohere_available() is False
    assert active_reranker() is None


def test_active_reranker_present_with_key_but_lazy(monkeypatch):
    from polaris.retrieval import rerank as rr

    monkeypatch.setattr(rr.settings, "cohere_api_key", "test-key-123")
    reranker = active_reranker()

    assert isinstance(reranker, CohereReranker)
    assert reranker.model == "rerank-v4.0"
    # 建構時**不**真的建 cohere client（延遲到第一次 rerank 才 import / 建立）
    assert reranker.client is None


# --- HybridRetriever 串接 ----------------------------------------------------

def test_hybrid_retriever_delegates_to_reranker():
    captured: dict = {}

    class FixedReranker:
        def rerank(self, query, results, *, top_k):
            captured["query"] = query
            captured["n_candidates"] = len(results)
            captured["top_k"] = top_k
            return [_sr("reranked-top", "x", score=1.0, reranked=True)]

    retriever = HybridRetriever(top_k=5, reranker=FixedReranker())
    out = retriever.retrieve("台積電 2025Q1 毛利率")

    assert captured["query"] == "台積電 2025Q1 毛利率"
    assert captured["n_candidates"] >= 1  # BM25 至少撈到候選餵進 rerank
    assert captured["top_k"] == 5
    assert [r.id for r in out] == ["reranked-top"]


def test_hybrid_retriever_falls_back_when_reranker_raises():
    class BoomReranker:
        def rerank(self, query, results, *, top_k):
            raise RuntimeError("cohere down")

    retriever = HybridRetriever(top_k=5, reranker=BoomReranker())
    out = retriever.retrieve("台積電 2025Q1 毛利率")

    # rerank 失敗不致命：退回 BM25 分數排序（降冪），檢索照常有結果
    assert len(out) >= 1
    scores = [r.score for r in out]
    assert scores == sorted(scores, reverse=True)
    assert out[0].metadata["origin"] == "bm25"


def test_hybrid_retriever_truncates_reranker_output_defensively():
    class GreedyReranker:
        def rerank(self, query, results, *, top_k):
            # 故意回超過 top_k（轉接層理應已截，retriever 再保險一次）
            return [_sr(f"r{i}", "x", score=float(10 - i)) for i in range(5)]

    retriever = HybridRetriever(top_k=2, reranker=GreedyReranker())
    out = retriever.retrieve("台積電 2025Q1 毛利率")
    assert len(out) == 2


def test_hybrid_retriever_without_reranker_is_unchanged():
    retriever = HybridRetriever(top_k=1)
    out = retriever.retrieve("AI 需求 營收")

    assert out[0].id == "stub-2330-2024Q4-revenue"
    assert out[0].metadata["origin"] == "bm25"
    assert "cohere_rerank" not in out[0].metadata.get("retrieval_channels", [])
