#!/usr/bin/env python3
"""真資料 retriever 驗收（token-free / CI-safe）。

設計成「有權限就驗、沒權限就 no-op」，方便有 GCP（+ Gemini）的人一鍵跑、也能放進 CI：

- **無 GCP 憑證** → 印 SKIP、exit 0、**0 外呼 / 0 token**（雲端 sandbox、CI 預設走這條）。
- **有 GCP 憑證**（ADC / SA）→ 跑「資料端 smoke」：對 ``$BQ_DATASET.chunks`` 查 row count、
  embedding 維度分布、self-similarity ``VECTOR_SEARCH``（用表內既有向量當 query，**不需 Gemini**），
  確認真資料存在、向量搜尋可用、回的是真 chunk（非 stub）。
- **再有 GEMINI_API_KEY** → 跑「完整 retriever」：文字 query → Gemini embed → 3 路檢索，
  斷言結果含**非 stub 的真 chunk**（BM25 只會回 ``stub-*``，故任一非 stub 結果＝向量路命中真資料）。

用法（在有 ADC 的機器）::

    export GCP_PROJECT=polaris-desk-team
    export VECTOR_BACKEND=bigquery
    export BQ_DATASET=polaris_dev_wayne_staging
    # 完整路再加：export GEMINI_API_KEY=<key>
    gcloud auth application-default login          # 或 GOOGLE_APPLICATION_CREDENTIALS=<sa.json>
    python scripts/accept_real_retriever.py "台積電 2025Q1 毛利率" --company 2330

退出碼：``0`` = PASS 或 SKIP（無憑證）；``1`` = FAIL（連到了但資料是 stub / 空 / 出錯）。
"""
from __future__ import annotations

import argparse
import sys


def _has_gcp_credentials() -> bool:
    """ADC / SA / GCE metadata 任一可用即 True；皆無 → False（不拋）。"""
    try:
        import google.auth

        google.auth.default()
        return True
    except Exception:  # noqa: BLE001 — 無憑證是預期路徑，回 False 走 SKIP
        return False


def _smoke_data_side(project: str, dataset: str) -> tuple[bool, dict]:
    """資料端 smoke（不需 Gemini）：row count + 維度分布 + 自相似 VECTOR_SEARCH。"""
    from google.cloud import bigquery

    client = bigquery.Client(project=project)
    table = f"{project}.{dataset}.chunks"
    rows = list(client.query(f"SELECT COUNT(*) AS c FROM `{table}`").result())[0]["c"]
    dims = [
        dict(r)
        for r in client.query(
            f"SELECT ARRAY_LENGTH(embedding) AS dim, COUNT(*) AS c "
            f"FROM `{table}` GROUP BY dim ORDER BY dim"
        ).result()
    ]
    top = [
        dict(r)
        for r in client.query(
            f"""
            SELECT base.chunk_id, base.ticker, base.fiscal_period, distance
            FROM VECTOR_SEARCH(
                (SELECT * FROM `{table}`), 'embedding',
                (SELECT embedding FROM `{table}` LIMIT 1),
                top_k => 3, distance_type => 'COSINE')
            ORDER BY distance
            """
        ).result()
    ]
    ok = (
        rows > 0
        and any(d["dim"] == 768 for d in dims)
        and bool(top)
        and not str(top[0]["chunk_id"]).startswith("stub")
    )
    return ok, {"rows": rows, "dims": dims, "top1": top[0] if top else None}


def _full_retriever(query: str, filters: dict) -> tuple[bool, list]:
    """完整 retriever：文字 query → Gemini embed → 3 路檢索（需 GEMINI_API_KEY + GCP）。"""
    from polaris.retrieval import build_retriever  # 延遲 import（依賴向量庫設定）

    results = build_retriever().retrieve(query, filters=filters or None)
    # BM25 只會回 stub-*；任一「非 stub」結果 ⇒ 向量路命中真資料。
    ok = bool(results) and any(not r.id.startswith("stub-") for r in results)
    return ok, results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="accept_real_retriever")
    parser.add_argument("query", nargs="?", default="台積電 2025Q1 毛利率")
    parser.add_argument("--company", default=None)
    parser.add_argument("--period", default=None)
    args = parser.parse_args(argv)

    if not _has_gcp_credentials():
        print("SKIP：無 GCP 憑證（請在有 ADC/SA 的機器跑此驗收）。token-free no-op，exit 0。")
        return 0

    from polaris.config import settings
    from polaris.llm.gemini import is_real_key

    project = settings.gcp_project
    dataset = settings.bq_dataset or "polaris_core"

    print(f"== 資料端 smoke：{project}.{dataset}.chunks ==")
    try:
        ok_smoke, info = _smoke_data_side(project, dataset)
    except Exception as exc:  # noqa: BLE001 — 把連線/查詢錯誤誠實回報為 FAIL
        print(f"FAIL：資料端查詢出錯：{type(exc).__name__}: {str(exc)[:200]}")
        return 1
    print(f"  rows={info['rows']}  dims={info['dims']}  top1={info['top1']}")
    print("  資料端：", "PASS ✅（真資料、向量搜尋可用）" if ok_smoke else "FAIL ❌")

    filters: dict[str, str] = {}
    if args.company:
        filters["company"] = args.company
    if args.period:
        filters["period"] = args.period

    if not is_real_key(settings.gemini_api_key):
        print("（無 GEMINI_API_KEY → 略過『文字 query → embedding → retriever』完整路；資料端已驗。）")
        return 0 if ok_smoke else 1

    print(f"== 完整 retriever：{args.query!r}（filters={filters or None}）==")
    try:
        ok_full, results = _full_retriever(args.query, filters)
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL：retriever 出錯：{type(exc).__name__}: {str(exc)[:200]}")
        return 1
    for r in results[:5]:
        channels = "/".join(r.metadata.get("retrieval_channels", []) or [r.metadata.get("origin", "?")])
        print(f"  [{channels} · score={r.score:.3f}] {r.id} {r.company or ''} {r.period or ''}")
    print("  retriever：", "PASS ✅（含非 stub 真 chunk）" if ok_full else "FAIL ❌（只有 stub / 空）")
    return 0 if (ok_smoke and ok_full) else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
