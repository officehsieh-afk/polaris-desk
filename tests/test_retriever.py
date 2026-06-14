from polaris.retrieval.rerank import CohereReranker
from polaris.retrieval.retriever import HybridRetriever, build_retriever


def test_retriever_returns_ranked_results():
    retriever = HybridRetriever(top_k=2)

    results = retriever.retrieve("台積電 2025Q1 毛利率")

    assert len(results) > 0
    assert results[0].score > 0
    assert "台積電" in results[0].content


def test_retriever_respects_period_filter():
    retriever = HybridRetriever(top_k=5)

    results = retriever.retrieve("台積電 毛利率", filters={"period": "2025Q1"})

    assert len(results) > 0
    assert all(r.period == "2025Q1" for r in results)


def test_retriever_empty_query_returns_empty_list():
    retriever = HybridRetriever()

    assert retriever.retrieve("") == []
    assert retriever.retrieve("   ") == []


def test_retriever_uses_bm25_keyword_ranking():
    retriever = HybridRetriever(top_k=1)

    results = retriever.retrieve("AI 需求 營收")

    assert len(results) == 1
    assert results[0].id == "stub-2330-2024Q4-revenue"
    assert results[0].metadata["origin"] == "bm25"


def test_retriever_merges_vector_search_results():
    vector_result = type("Result", (), {})()
    vector_result.id = "vector-2454-2025Q1-gm"
    vector_result.content = "聯發科 2025Q1 法說摘要：毛利率與產品組合相關。"
    vector_result.score = 0.91
    vector_result.company = "2454"
    vector_result.period = "2025Q1"
    vector_result.metadata = {"source_id": "vector-2454-2025Q1-gm"}

    class FakeStore:
        def __init__(self):
            self.calls = []

        def search(self, query_embedding, top_k=8, *, filters=None):
            self.calls.append((query_embedding, top_k, filters))
            return [vector_result]

    store = FakeStore()
    retriever = HybridRetriever(
        top_k=3,
        store=store,
        embedding_fn=lambda query: [0.1, 0.2, 0.3],
    )

    results = retriever.retrieve("聯發科 2025Q1 毛利率", filters={"period": "2025Q1"})

    assert store.calls == [([0.1, 0.2, 0.3], 3, {"period": "2025Q1"})]
    assert results[0].id == "vector-2454-2025Q1-gm"
    assert results[0].metadata["origin"] == "vector"


def test_retriever_deduplicates_bm25_and_vector_results():
    vector_result = type("Result", (), {})()
    vector_result.id = "stub-2330-2025Q1-gm"
    vector_result.content = "台積電 2025Q1 法說摘要：毛利率受到匯率影響。"
    vector_result.score = 0.99
    vector_result.company = "2330"
    vector_result.period = "2025Q1"
    vector_result.metadata = {"source_id": "stub-2330-2025Q1-gm"}

    class FakeStore:
        def search(self, query_embedding, top_k=8, *, filters=None):
            return [vector_result]

    retriever = HybridRetriever(
        top_k=5,
        store=FakeStore(),
        embedding_fn=lambda query: [1.0],
    )

    results = retriever.retrieve("台積電 2025Q1 毛利率")

    ids = [result.id for result in results]
    assert ids.count("stub-2330-2025Q1-gm") == 1
    merged = next(result for result in results if result.id == "stub-2330-2025Q1-gm")
    assert merged.score == 0.99
    assert merged.metadata["retrieval_channels"] == ["bm25", "vector"]


# --- build_retriever：一鍵組裝 3 路 + graceful degrade（token-free）---------

def _patch_keys(monkeypatch, *, gemini="", cohere=""):
    """把兩支金鑰打成指定值（預設清空 → 0 外呼）。"""
    from polaris.llm import gemini as gemini_mod
    from polaris.retrieval import rerank as rerank_mod

    monkeypatch.setattr(gemini_mod.settings, "gemini_api_key", gemini)
    monkeypatch.setattr(rerank_mod.settings, "cohere_api_key", cohere)


def test_build_retriever_bm25_only_without_keys(monkeypatch):
    _patch_keys(monkeypatch)  # 兩支金鑰皆空

    retriever = build_retriever()

    # 無金鑰 → 不接 Gemini 向量、不接 Cohere rerank（0 外呼）
    assert retriever.embedding_fn is None
    assert retriever.reranker is None
    # BM25 仍可用，檢索照常有結果
    results = retriever.retrieve("AI 需求 營收")
    assert results[0].id == "stub-2330-2024Q4-revenue"
    assert "cohere_rerank" not in results[0].metadata.get("retrieval_channels", [])


def test_build_retriever_wires_cohere_when_key_present(monkeypatch):
    _patch_keys(monkeypatch, cohere="test-cohere-key")

    retriever = build_retriever()

    assert isinstance(retriever.reranker, CohereReranker)
    assert retriever.reranker.model == "rerank-v4.0"
    # 仍未建真 client（延遲到第一次 rerank）
    assert retriever.reranker.client is None


def test_build_retriever_wires_gemini_embedding_when_available(monkeypatch):
    _patch_keys(monkeypatch)

    class _FakeClient:
        def embed(self, text):
            return [0.1, 0.2, 0.3]

    fake = _FakeClient()
    # active_llm 在 build_retriever 內延遲 import，故 patch 來源模組屬性
    monkeypatch.setattr("polaris.llm.gemini.active_llm", lambda: fake)

    retriever = build_retriever()

    assert retriever.embedding_fn == fake.embed


def test_build_retriever_respects_top_k(monkeypatch):
    _patch_keys(monkeypatch)

    assert build_retriever(top_k=3).top_k == 3
    # 未指定 → 取 settings.top_k（預設 8）
    from polaris.config import settings

    assert build_retriever().top_k == settings.top_k
