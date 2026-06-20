"""第 4 路視覺檢索的雲端後端：只讀 polaris_core.colpali_pages（128 維 cosine）。

- ColPali 頁向量已由 R4 入庫（5701 頁，patch 池化成單一 128 維）；本類別只**讀**。
- 無 owner/confidential 欄 → 不做 viewer ACL filter（與 chunks 不同）。
- 表內無文字層 → SearchResult.content 用可讀頁參照（含頁碼）供引用接地。
- client 注入式 seam（同 BigQueryStore）：測試注入 fake client → 0 GCP 外呼。
"""
from __future__ import annotations

from typing import Any

from .base import SearchResult

#: 介面 filter 鍵 → colpali_pages 欄名（無 viewer：此表無 owner 欄）。
_FILTER_COLUMNS = {
    "company": "ticker",
    "period": "fiscal_period",
    "doc_type": "doc_type",
}


class BigQueryColpaliStore:
    """colpali_pages 的 128 維 cosine 檢索（只讀）。"""

    def __init__(self, settings, *, client=None) -> None:
        self.settings = settings
        self._client = client

    def _get_client(self):
        if self._client is None:
            from google.cloud import bigquery
            self._client = bigquery.Client(project=self.settings.gcp_project)
        return self._client

    @property
    def _table(self) -> str:
        return f"{self.settings.gcp_project}.{self.settings.bq_dataset}.colpali_pages"

    def search(
        self,
        query_embedding: list[float],
        top_k: int = 8,
        *,
        filters: dict[str, Any] | None = None,
    ) -> list[SearchResult]:
        params: dict[str, Any] = {"qe": query_embedding, "k": top_k}
        clauses = []
        for key, column in _FILTER_COLUMNS.items():
            if filters and filters.get(key) is not None:
                clauses.append(f"{column} = @{column}")
                params[column] = filters[key]
        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""

        sql = f"""
        SELECT base.page_id, base.ticker, base.fiscal_period, base.doc_type,
               base.source_file, base.page_num, base.published_at, distance
        FROM VECTOR_SEARCH(
            (SELECT * FROM `{self._table}` {where}),
            'embedding',
            (SELECT @qe AS embedding),
            top_k => @k,
            distance_type => 'COSINE'
        )
        ORDER BY distance
        """
        rows = self._run_query(sql, params)
        return [self._to_result(row) for row in rows]

    @staticmethod
    def _to_result(row: dict) -> SearchResult:
        ticker = row.get("ticker")
        period = row.get("fiscal_period")
        page_num = row.get("page_num")
        source_file = row.get("source_file")
        # 無文字層 → 可讀頁參照當 snippet（接地要頁碼）
        content = f"{ticker} {period} 第 {page_num} 頁圖表（{source_file}）"
        published = row.get("published_at")
        return SearchResult(
            id=row["page_id"],
            content=content,
            score=1.0 - float(row["distance"]),
            company=ticker,
            period=period,
            metadata={
                "origin": "colpali",
                "retrieval_channels": ["colpali"],
                "page_num": page_num,
                "source_file": source_file,
                "doc_type": row.get("doc_type"),
                "published_at": (
                    published.isoformat() if hasattr(published, "isoformat") else published
                ),
            },
        )

    def _run_query(self, sql: str, params: dict[str, Any]) -> list[dict]:
        client = self._get_client()
        job_config = self._build_job_config(params)
        return [dict(row) for row in client.query(sql, job_config=job_config).result()]

    @staticmethod
    def _build_job_config(params: dict[str, Any]):
        try:
            from google.cloud import bigquery
        except ImportError:
            return None
        qp = []
        for name, value in params.items():
            if isinstance(value, list):
                qp.append(bigquery.ArrayQueryParameter(name, "FLOAT64", value))
            elif isinstance(value, int):
                qp.append(bigquery.ScalarQueryParameter(name, "INT64", value))
            else:
                qp.append(bigquery.ScalarQueryParameter(name, "STRING", value))
        return bigquery.QueryJobConfig(query_parameters=qp)

    def health_check(self) -> bool:
        try:
            self._get_client().query("SELECT 1").result()
        except Exception:  # noqa: BLE001
            return False
        return True
