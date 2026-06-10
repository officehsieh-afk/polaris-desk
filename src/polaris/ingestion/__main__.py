"""CLI：``python -m polaris.ingestion <chunks.jsonl>``。

讀切塊 JSONL → sanitize → embed（gemini-embedding-2, 768）→ 入庫
（依 .env：VECTOR_BACKEND / BQ_DATASET）。需 GEMINI_API_KEY；
寫 polaris_core 另需 BQ_ALLOW_CORE_WRITE=1（ingestion 帳號，憲法 III）。
"""
from __future__ import annotations

import sys

from polaris.config import settings
from polaris.ingestion.pipeline import ingest_file


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 1:
        print("用法：python -m polaris.ingestion <chunks.jsonl>", file=sys.stderr)
        return 2
    try:
        report = ingest_file(args[0])
    except RuntimeError as exc:
        print(f"❌ {exc}", file=sys.stderr)
        return 1
    print(
        f"=== Ingestion 完成（backend={settings.vector_backend} "
        f"dataset={settings.bq_dataset}）===\n"
        f"入庫 {report.ingested} / {report.total} 塊"
    )
    if report.quarantined:
        print(f"quarantine {len(report.quarantined)} 塊：")
        for doc_id, reason in report.quarantined:
            print(f"  - {doc_id}: {reason}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
