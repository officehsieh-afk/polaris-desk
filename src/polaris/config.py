"""唯一設定來源 —— 全部從 .env 讀進來。

本地與雲端用同一份程式，差別只在 .env（或雲端環境變數）。
這就是「本地先開發、再上雲」不用改程式的關鍵之一。
"""
from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # --- 向量庫後端開關（本地 ↔ 雲端就靠這個）---
    vector_backend: str = "pgvector"          # pgvector | bigquery

    # 本地 pgvector
    database_url: str = "postgresql://polaris:polaris@localhost:5432/polaris"

    # 雲端 BigQuery
    gcp_project: str = ""
    bq_dataset: str = "polaris"

    # LLM / 檢索金鑰（可留空，跑骨架測試不需要）
    gemini_api_key: str = ""
    cohere_api_key: str = ""
    tavily_api_key: str = ""
    anthropic_api_key: str = ""
    openai_api_key: str = ""

    # 模型（名稱對齊 google-genai 當前版本）
    gemini_model_pro: str = "gemini-3-pro-preview"
    gemini_model_flash: str = "gemini-3-flash-preview"
    embedding_model: str = "gemini-embedding-2"   # 最新多模態嵌入；純文字可改 gemini-embedding-001
    embedding_dim: int = 768

    # 應用
    app_env: str = "local"                    # local | cloud
    log_level: str = "INFO"
    top_k: int = 8


# 全域單例 —— 其他模組 `from polaris.config import settings`
settings = Settings()
