"""Ingestion（R4 / SOP §4）：入庫前淨化 / 驗證 + chunks → embed → 入庫管線。"""
from polaris.ingestion.pipeline import (
    IngestReport,
    ingest_chunks,
    ingest_file,
    load_chunks,
)
from polaris.ingestion.sanitize import (
    MAX_CONTENT_CHARS,
    sanitize_text,
    validate_for_ingestion,
)

__all__ = [
    "MAX_CONTENT_CHARS",
    "IngestReport",
    "ingest_chunks",
    "ingest_file",
    "load_chunks",
    "sanitize_text",
    "validate_for_ingestion",
]
