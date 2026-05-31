"""驗證「本地→雲端」抽象層：只改設定就換後端，呼叫端不變。

這個測試只依賴 pydantic-settings，不需要 DB / 雲端 / 重相依即可跑。
"""
import pytest

from polaris.config import Settings
from polaris.vectorstore import VectorStore, get_vector_store
from polaris.vectorstore.bigquery_store import BigQueryStore
from polaris.vectorstore.pgvector_store import PgVectorStore


def test_factory_returns_pgvector_for_local():
    store = get_vector_store(Settings(vector_backend="pgvector"))
    assert isinstance(store, PgVectorStore)


def test_factory_returns_bigquery_for_cloud():
    store = get_vector_store(Settings(vector_backend="bigquery"))
    assert isinstance(store, BigQueryStore)


def test_factory_rejects_unknown_backend():
    with pytest.raises(ValueError):
        get_vector_store(Settings(vector_backend="redis"))


def test_vectorstore_is_abstract():
    with pytest.raises(TypeError):
        VectorStore()  # 抽象類別不能直接實例化


def test_swapping_backend_changes_implementation():
    """同一份程式，只改 VECTOR_BACKEND → 換實作。本地→雲端的核心保證。"""
    local = get_vector_store(Settings(vector_backend="pgvector"))
    cloud = get_vector_store(Settings(vector_backend="bigquery"))
    assert type(local) is not type(cloud)
    assert isinstance(local, VectorStore)
    assert isinstance(cloud, VectorStore)
