"""BigQueryColpaliStore 測試：注入 fake client，0 GCP 外呼。

驗 VECTOR_SEARCH(COSINE) 於 colpali_pages、filter 對映、結果→SearchResult、origin=colpali。
"""
from __future__ import annotations

from polaris.config import Settings
from polaris.vectorstore.colpali_store import BigQueryColpaliStore

QE = [0.1] * 8  # 測試用短向量（真環境 128，由 schema 守）


def make_settings(**overrides) -> Settings:
    return Settings(_env_file=None, **overrides)


class FakeBQJob:
    def __init__(self, rows=None):
        self._rows = rows or []

    def result(self):
        return self._rows


class FakeBQClient:
    def __init__(self, rows=None):
        self.queries: list[str] = []
        self._rows = rows or []

    def query(self, sql, job_config=None):
        self.queries.append(sql)
        return FakeBQJob(self._rows)


def _row():
    return {
        "page_id": "pg-2330-2025Q3-9",
        "ticker": "2330",
        "fiscal_period": "2025Q3",
        "doc_type": "presentation",
        "source_file": "2330_..._presentation.pdf",
        "page_num": 9,
        "published_at": "2025-10-16",
        "distance": 0.25,
    }


def test_search_emits_vector_search_cosine_on_colpali_pages():
    client = FakeBQClient(rows=[_row()])
    store = BigQueryColpaliStore(make_settings(), client=client)
    store.search(QE, top_k=5)
    sql = client.queries[0]
    assert "VECTOR_SEARCH" in sql
    assert "colpali_pages" in sql
    assert "COSINE" in sql


def test_search_maps_row_to_searchresult_with_colpali_origin():
    client = FakeBQClient(rows=[_row()])
    store = BigQueryColpaliStore(make_settings(), client=client)
    [res] = store.search(QE, top_k=5)
    assert res.id == "pg-2330-2025Q3-9"
    assert res.company == "2330"
    assert res.period == "2025Q3"
    assert res.metadata["origin"] == "colpali"
    assert res.metadata["page_num"] == 9
    assert res.metadata["source_file"].endswith(".pdf")
    # 無文字層 → snippet 用可讀的頁參照，含頁碼供接地
    assert "9" in res.content and "2330" in res.content
    # cosine 距離 → 相似度（越大越像）
    assert abs(res.score - 0.75) < 1e-9


def test_search_filters_by_company_and_period_only_no_viewer():
    client = FakeBQClient(rows=[])
    store = BigQueryColpaliStore(make_settings(), client=client)
    store.search(QE, top_k=5, filters={"company": "2330", "period": "2025Q3", "viewer": "someone"})
    sql = client.queries[0]
    assert "ticker = @ticker" in sql
    assert "fiscal_period = @fiscal_period" in sql
    # colpali_pages 無 owner 欄 → 不得出現 viewer/owner 過濾
    assert "owner" not in sql and "viewer" not in sql
