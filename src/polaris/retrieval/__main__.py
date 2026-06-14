"""CLI demo：``python -m polaris.retrieval "<查詢>" [--company 2330] [--period 2024Q3] [--top-k 5]``。

組裝 3 路檢索器（``build_retriever``：BM25 + Gemini 向量 + Cohere rerank），跑一題、
印排序結果與每筆的檢索通道 / 分數，方便 demo「讀資料」這條路。

誠實邊界：無金鑰時只走 **BM25 stub 語料**（會在表頭標明）；設了 ``GEMINI_API_KEY``
（向量）+ ``COHERE_API_KEY``（重排）且向量庫有真 chunks 時，才是完整 3 路真檢索。
全程不主動外呼——路徑由金鑰是否就緒自動 graceful degrade。
"""
from __future__ import annotations

import argparse
import sys

from polaris.retrieval import build_retriever


def _format_result(rank: int, result) -> str:
    channels = result.metadata.get("retrieval_channels") or [result.metadata.get("origin", "?")]
    head = (
        f"{rank}. [{'/'.join(channels)} · score={result.score:.3f}] "
        f"{result.company or ''} {result.period or ''} {result.id}".rstrip()
    )
    snippet = result.content.strip().replace("\n", " ")
    return f"{head}\n   {snippet[:80]}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m polaris.retrieval",
        description="3 路混合檢索 demo（BM25 + Gemini 向量 + Cohere rerank）。",
    )
    parser.add_argument("query", help="查詢字串，例如「台積電 2025Q1 毛利率」")
    parser.add_argument("--company", default=None, help="公司代號過濾，例如 2330")
    parser.add_argument("--period", default=None, help="季別過濾，例如 2025Q1")
    parser.add_argument("--top-k", type=int, default=None, help="回傳筆數上限")
    args = parser.parse_args(argv)

    retriever = build_retriever(top_k=args.top_k) if args.top_k is not None else build_retriever()

    filters: dict[str, str] = {}
    if args.company:
        filters["company"] = args.company
    if args.period:
        filters["period"] = args.period

    results = retriever.retrieve(args.query, filters=filters or None)

    paths = ["BM25(關鍵字)"]
    if retriever.embedding_fn is not None:
        paths.append("向量(Gemini)")
    if retriever.reranker is not None:
        paths.append("Cohere rerank")
    degraded = retriever.embedding_fn is None and retriever.reranker is None

    print(f"=== 檢索 demo：{args.query!r} ===")
    print(
        f"啟用路徑：{' + '.join(paths)}"
        + ("　（無金鑰 → 僅 BM25 stub 語料；接真資料 + 金鑰後為完整 3 路）" if degraded else "")
    )
    if not results:
        print("（無結果）")
        return 0
    for rank, result in enumerate(results, start=1):
        print(_format_result(rank, result))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main(sys.argv[1:]))
