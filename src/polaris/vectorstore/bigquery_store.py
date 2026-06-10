"""雲端向量庫實作：BigQuery VECTOR_SEARCH（Q-03 預設後端）。

介面與 PgVectorStore 完全相同 —— 切換只改 .env 的 ``VECTOR_BACKEND``。

- **client 注入式 seam**（同 Deep Research ``search`` / Slack ``transport``
  套路）：測試注入 fake client → CI 0 GCP 外呼、0 金鑰；真環境延遲
  import ``google.cloud.bigquery``。
- **寫入保護（憲法 III / SOP §3.4）**：``add_documents`` 預設拒寫
  ``polaris_core``（共用 canonical 唯讀）；一般開發者寫自己的
  ``polaris_dev_<name>``。經 PM 同意的 ingestion 帳號（R1/R4）設
  ``BQ_ALLOW_CORE_WRITE=1`` 解鎖 —— 這是 client 端防呆，**不取代** server
  端 ACL（ACL 變更一律走 SOP §7 PR）。
- 維度 768 / 距離 cosine，與 pgvector fallback 兩端一致（憲法 §Additional）。
"""
from __future__ import annotations

import json
from typing import Any

from .base import Document, SearchResult, VectorStore

#: 共用 canonical dataset —— 預設唯讀（憲法 III）。
_CORE_DATASET = "polaris_core"


class BigQueryStore(VectorStore):
    def __init__(self, settings, *, client=None) -> None:
        self.settings = settings
        self._client = client  # 注入（測試）或延遲建立（真環境）

    def _get_client(self):
        if self._client is None:
            from google.cloud import bigquery  # 延遲 import（重相依不進 CI 必經路徑）
            self._client = bigquery.Client(project=self.settings.gcp_project)
        return self._client

    @property
    def _table(self) -> str:
        return f"{self.settings.gcp_project}.{self.settings.bq_dataset}.chunks"

    # ── 寫入（含 polaris_core 防呆）─────────────────────────────────────

    def add_documents(self, docs: list[Document]) -> None:
        if not docs:
            return
        if (
            self.settings.bq_dataset == _CORE_DATASET
            and not getattr(self.settings, "bq_allow_core_write", False)
        ):
            raise PermissionError(
                f"拒寫共用 canonical `{_CORE_DATASET}`（憲法 III：開發者寫自己的 "
                "polaris_dev_<name>；ingestion 帳號設 BQ_ALLOW_CORE_WRITE=1）"
            )
        rows = [
            {
                "id": d.id,
                "doc_id": d.metadata.get("doc_id", d.id),
                "company": d.company,
                "period": d.period,
                "content": d.content,
                "embedding": d.embedding,
                "metadata": json.dumps(d.metadata, ensure_ascii=False),
            }
            for d in docs
        ]
        client = self._get_client()
        client.load_table_from_json(rows, self._table).result()

    # ── 檢索（VECTOR_SEARCH，cosine）───────────────────────────────────

    def search(
        self,
        query_embedding: list[float],
        top_k: int = 8,
        *,
        filters: dict[str, Any] | None = None,
    ) -> list[SearchResult]:
        where = ""
        params: dict[str, Any] = {"qe": query_embedding, "k": top_k}
        clauses = []
        for key in ("company", "period"):
            if filters and filters.get(key) is not None:
                clauses.append(f"{key} = @{key}")
                params[key] = filters[key]
        if clauses:
            where = "WHERE " + " AND ".join(clauses)

        sql = f"""
        SELECT base.id, base.content, base.company, base.period, base.metadata,
               distance
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
        return [
            SearchResult(
                id=row["id"],
                content=row["content"],
                # cosine 距離 → 相似度分數（兩端後端同語意：越大越像）
                score=1.0 - float(row["distance"]),
                company=row.get("company"),
                period=row.get("period"),
                metadata=json.loads(row["metadata"]) if row.get("metadata") else {},
            )
            for row in rows
        ]

    def _run_query(self, sql: str, params: dict[str, Any]) -> list[dict]:
        client = self._get_client()
        job_config = self._build_job_config(params)
        return [dict(row) for row in client.query(sql, job_config=job_config).result()]

    @staticmethod
    def _build_job_config(params: dict[str, Any]):
        """組 QueryJobConfig；fake client（測試）回 None 即可忽略。"""
        try:
            from google.cloud import bigquery
        except ImportError:  # 測試環境（注入 fake client）不需真參數物件
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

    # ── 健康檢查（bq-smoke 零改碼轉真，見 diagnostics）─────────────────

    def health_check(self) -> bool:
        try:
            self._get_client().query("SELECT 1").result()
        except Exception:  # noqa: BLE001 — 健檢回 bool、不拋（診斷層分類 fail）
            return False
        return True
