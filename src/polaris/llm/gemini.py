"""Gemini 用戶端薄封裝（@R2 / @R3）。

使用新版 **google-genai** SDK（`pip install google-genai`），
取代已淘汰的舊 `google-generativeai`。API 形態：
    from google import genai
    client = genai.Client(api_key=...)
    client.models.generate_content(model=..., contents=...)

LLM 本就走雲端 API，本地 / 雲端共用此封裝。金鑰從 settings（.env）讀。
重相依採延遲 import，未安裝 SDK 時 `import polaris` 仍正常。
"""
from __future__ import annotations

from ..config import settings


class GeminiClient:
    def __init__(self) -> None:
        if not settings.gemini_api_key:
            raise RuntimeError("缺少 GEMINI_API_KEY，請在 .env 填入")
        from google import genai  # 延遲 import
        self._client = genai.Client(api_key=settings.gemini_api_key)

    def generate(
        self,
        prompt: str,
        *,
        flash: bool = False,
        system_instruction: str | None = None,
    ) -> str:
        """單輪文字生成。flash=True 用便宜快速的 Flash 模型。"""
        from google.genai import types  # 延遲 import

        model = settings.gemini_model_flash if flash else settings.gemini_model_pro
        config = (
            types.GenerateContentConfig(system_instruction=system_instruction)
            if system_instruction
            else None
        )
        resp = self._client.models.generate_content(
            model=model, contents=prompt, config=config
        )
        return resp.text

    def embed(self, text: str) -> list[float]:
        """產生 embedding（入庫與查詢都用）；維度由 .env EMBEDDING_DIM 控制。

        TODO(@R4)：W1 接 DB 後，確認回傳形狀與 batch 寫法（可一次 contents=[...] 多筆）。
        """
        from google.genai import types  # 延遲 import

        resp = self._client.models.embed_content(
            model=settings.embedding_model,
            contents=text,
            config=types.EmbedContentConfig(output_dimensionality=settings.embedding_dim),
        )
        return list(resp.embeddings[0].values)
