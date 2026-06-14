"""Cohere Rerank —— 檢索第 3 路（@R3，FR-002/G2）。

BM25（路 1）+ 向量語意（路 2）取得候選後，這層用 Cohere `rerank-v4.0`
（`client.v2.rerank`，見 `R3_Agent_spec.md`）對候選重排，讓 Writer 拿到
相關度更準的順序、每筆帶 rerank 接地註記。

設計對齊 `llm/gemini.py` 與 `retriever.py` 的成本紀律：
- **opt-in**：沒注入 reranker 的 HybridRetriever 完全不呼叫外部 API。
- **無金鑰 = None**：`active_reranker()` 沒 COHERE_API_KEY 就回 None（CI token=0）。
- **延遲 import**：未裝 / 未啟用 cohere 時 `import polaris` 仍正常。
- **失敗不致命**：rerank 例外由呼叫端（retriever）graceful fallback，不可讓檢索掛掉。

rerank 只重排既有檢索結果、不生成任何文字，故不涉 NFR-031（買賣建議）面。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

from ..config import settings
from ..llm.gemini import is_real_key
from ..vectorstore import SearchResult

#: spec 指定的 Cohere rerank 模型（`R3_Agent_spec.md`：W2 D6 / G2）。
DEFAULT_RERANK_MODEL = "rerank-v4.0"


@runtime_checkable
class Reranker(Protocol):
    """重排器介面。注入 `HybridRetriever(reranker=...)` 即啟用第 3 路。

    回傳值需為「已依相關度排序」的結果，呼叫端僅做防禦性截斷。
    """

    def rerank(
        self, query: str, results: list[SearchResult], *, top_k: int
    ) -> list[SearchResult]: ...


def cohere_available() -> bool:
    """目前 settings 內是否有可用的 Cohere 金鑰。"""
    return is_real_key(settings.cohere_api_key)


def active_reranker() -> "CohereReranker | None":
    """有真金鑰 → 回 CohereReranker；否則回 None（呼叫端不重排）。

    無金鑰時**不**建立 client、不觸發 cohere import，CI / 無金鑰開發皆可正常跑
    （憲法成本紀律，鏡像 `llm.gemini.active_llm`）。
    """
    return CohereReranker() if cohere_available() else None


def _reranked_result(original: SearchResult, *, score: float, model: str) -> SearchResult:
    """複製候選並寫入 rerank 接地註記（保留原檢索通道、追加 cohere_rerank）。"""
    metadata: dict[str, Any] = dict(original.metadata)
    channels = list(metadata.get("retrieval_channels", []))
    if "cohere_rerank" not in channels:
        channels.append("cohere_rerank")
    metadata["retrieval_channels"] = channels
    metadata["reranked"] = True
    metadata["rerank_model"] = model
    metadata["rerank_score"] = float(score)
    return SearchResult(
        id=original.id,
        content=original.content,
        score=float(score),
        company=original.company,
        period=original.period,
        metadata=metadata,
    )


@dataclass
class CohereReranker:
    """Cohere `rerank-v4.0` 重排器（`client.v2.rerank`）。

    `client` 可注入（測試 / 自帶連線）；留空則在第一次 rerank 時依
    `COHERE_API_KEY` 延遲建立 `cohere.ClientV2`。
    """

    model: str = DEFAULT_RERANK_MODEL
    client: Any | None = None

    def _ensure_client(self) -> Any:
        if self.client is None:
            if not is_real_key(settings.cohere_api_key):
                raise RuntimeError("缺少有效 COHERE_API_KEY，請在 .env 填入真實金鑰")
            import cohere  # 延遲 import（重相依，未裝也能 import polaris）

            self.client = cohere.ClientV2(api_key=settings.cohere_api_key)
        return self.client

    def rerank(
        self, query: str, results: list[SearchResult], *, top_k: int
    ) -> list[SearchResult]:
        """對候選重排；回傳依相關度降冪、截到 top_k 的結果。

        空 query / 空候選直接原樣返回，不外呼（省 token）。
        """
        query = (query or "").strip()
        if not query or not results:
            return list(results)

        client = self._ensure_client()
        top_n = min(top_k, len(results)) if top_k > 0 else len(results)
        response = client.rerank(
            model=self.model,
            query=query,
            documents=[result.content for result in results],
            top_n=top_n,
        )

        reranked: list[SearchResult] = []
        for item in response.results:
            original = results[item.index]
            reranked.append(
                _reranked_result(original, score=float(item.relevance_score), model=self.model)
            )
        return reranked
