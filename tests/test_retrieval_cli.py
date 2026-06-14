"""檢索 demo CLI 測試（token-free：清空金鑰 → 只走 BM25 stub）。"""
from __future__ import annotations

import pytest

from polaris.retrieval.__main__ import main


@pytest.fixture(autouse=True)
def _no_keys(monkeypatch):
    """清空金鑰，確保走確定性 BM25 stub、0 外呼。"""
    from polaris.llm import gemini as gemini_mod
    from polaris.retrieval import rerank as rerank_mod

    monkeypatch.setattr(gemini_mod.settings, "gemini_api_key", "")
    monkeypatch.setattr(rerank_mod.settings, "cohere_api_key", "")


def test_cli_runs_and_prints_ranked_results(capsys):
    rc = main(["台積電 2025Q1 毛利率"])
    out = capsys.readouterr().out

    assert rc == 0
    assert "檢索 demo" in out
    assert "BM25" in out
    assert "stub-2330" in out          # 有印出 stub 結果
    assert "僅 BM25 stub 語料" in out    # 無金鑰時誠實標明 degrade


def test_cli_respects_company_and_period_filter(capsys):
    rc = main(["毛利率", "--company", "2330", "--period", "2025Q1"])
    out = capsys.readouterr().out

    assert rc == 0
    assert "stub-2330-2025Q1-gm" in out
    assert "2317" not in out            # 鴻海被 filter 濾掉


def test_cli_top_k_limits_results(capsys):
    rc = main(["台積電 法說", "--top-k", "1"])
    out = capsys.readouterr().out

    assert rc == 0
    # 只應有一筆編號結果行（"1." 開頭），不應出現 "2."
    assert "\n1. " in "\n" + out
    assert "\n2. " not in "\n" + out


def test_cli_missing_query_errors():
    with pytest.raises(SystemExit):   # argparse 缺必填參數 → SystemExit(2)
        main([])
