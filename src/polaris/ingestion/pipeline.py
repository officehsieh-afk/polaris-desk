"""Ingestion pipeline（R4 / SOP §4）：chunks JSONL → sanitize → embed → 入庫。

輸入契約（JSONL，一行一塊；fetch-tw-earnings-call 抓回的法說稿經切塊後落地）：
``{"id": "...", "content": "...", "company": "2330", "period": "2025Q1",
   "metadata": {...}}``

- **seam 注入**：``embed``（預設 ``active_llm().embed``）與 ``store``（預設
  ``get_vector_store()``）都可注入 → 測試 0 token / 0 外呼。
- **安全（LLM01）**：每塊先過 ``sanitize_text``（去 HTML 註解 / 零寬 / BiDi）
  ＋ ``validate_for_ingestion``；不合格塊 quarantine 記錄、不入庫、不弄垮整批。
- **寫入目標**：依 ``Settings.bq_dataset``——開發者寫自己的 ``polaris_dev_<name>``；
  ``polaris_core`` 由 store 層防呆把關（BQ_ALLOW_CORE_WRITE，憲法 III）。
- 失敗語意：embedding 暫時性失敗由 ``call_with_retry`` 撐；單塊 embed 用盡
  失敗 → 該塊 quarantine（不丟整批）。
"""
from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from polaris.ingestion.sanitize import sanitize_text, validate_for_ingestion
from polaris.retry import call_with_retry
from polaris.vectorstore.base import Document, VectorStore

EmbedFn = Callable[[str], list[float]]

#: 一次寫入 store 的批量（BigQuery load job 友善值）。
_BATCH_SIZE = 100


@dataclass
class IngestReport:
    """一次 ingestion 的結果統計（可重跑、可稽核）。"""

    ingested: int = 0
    quarantined: list[tuple[str, str]] = field(default_factory=list)  # (id, 原因)

    @property
    def total(self) -> int:
        return self.ingested + len(self.quarantined)


def load_chunks(path: str | Path) -> list[dict]:
    """讀 chunks JSONL；壞行（非 JSON）quarantine 由 caller 統計，這裡直接拋。"""
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines if line.strip()]


def _to_document(raw: dict, embed: EmbedFn, *, sleep=None) -> Document:
    content = sanitize_text(raw.get("content", ""))
    embedding = call_with_retry(lambda: embed(content), sleep=sleep)
    return Document(
        id=raw["id"],
        content=content,
        embedding=embedding,
        company=raw.get("company"),
        period=raw.get("period"),
        metadata=dict(raw.get("metadata", {})),
    )


def ingest_chunks(
    chunks: list[dict],
    *,
    store: VectorStore,
    embed: EmbedFn,
    sleep=None,
) -> IngestReport:
    """sanitize → validate → embed（含 retry）→ 批次入庫。

    不合格 / embed 失敗的塊 quarantine（記 id+原因），其餘照常入庫——
    一塊壞資料不弄垮整批（R4 下載清單的語料品質參差是常態）。
    """
    report = IngestReport()
    batch: list[Document] = []
    for raw in chunks:
        doc_id = str(raw.get("id", ""))
        content = sanitize_text(raw.get("content", ""))
        issues = validate_for_ingestion(doc_id, content)
        if issues:
            report.quarantined.append((doc_id or "<no-id>", "; ".join(issues)))
            continue
        try:
            batch.append(_to_document(raw, embed, sleep=sleep))
        except Exception as exc:  # noqa: BLE001 — 單塊失敗 quarantine、不丟整批
            report.quarantined.append((doc_id, f"embed failed: {exc}"))
            continue
        if len(batch) >= _BATCH_SIZE:
            store.add_documents(batch)
            report.ingested += len(batch)
            batch = []
    if batch:
        store.add_documents(batch)
        report.ingested += len(batch)
    return report


def ingest_file(
    path: str | Path,
    *,
    store: VectorStore | None = None,
    embed: EmbedFn | None = None,
) -> IngestReport:
    """檔案入口：預設接真 store（factory）與真 embedding（active_llm）。

    無金鑰 → 拋 RuntimeError（誠實失敗；ingestion 必須真 embedding，
    不做假向量——假向量入庫會毒害檢索品質且難以察覺）。
    """
    if store is None:
        from polaris.vectorstore import get_vector_store

        store = get_vector_store()
    if embed is None:
        from polaris.llm.gemini import active_llm

        client = active_llm()
        if client is None:
            raise RuntimeError(
                "ingestion 需要 GEMINI_API_KEY（真 embedding 才可入庫；"
                "不產假向量毒害檢索）"
            )
        embed = client.embed
    return ingest_chunks(load_chunks(path), store=store, embed=embed)


__all__ = ["EmbedFn", "IngestReport", "ingest_chunks", "ingest_file", "load_chunks"]
