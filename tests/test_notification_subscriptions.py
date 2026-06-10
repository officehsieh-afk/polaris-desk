"""Subscription 過濾規則測試（specs/002 T014 / US3）。

預設全收、watchlist 過濾、ticker=None 系統級通知不受 watchlist 擋、
muted_types 過濾、severity=alert 恆放行（安全攸關不可靜音）。
"""
from __future__ import annotations

from polaris.notifications.subscriptions import Subscription
from tests.test_notification_model import make_notification


def test_default_allows_everything():
    sub = Subscription()
    assert sub.allows(make_notification()) is True
    assert sub.allows(make_notification(ticker=None, severity="info")) is True


def test_watchlist_filters_other_tickers():
    sub = Subscription(tickers=frozenset({"2330"}))
    assert sub.allows(make_notification(ticker="2330")) is True
    assert sub.allows(make_notification(ticker="2891", severity="info")) is False


def test_system_notification_without_ticker_passes_watchlist():
    sub = Subscription(tickers=frozenset({"2330"}))
    assert sub.allows(make_notification(ticker=None, type="research_done")) is True


def test_muted_type_filtered():
    sub = Subscription(muted_types=frozenset({"data_ingested"}))
    assert sub.allows(make_notification(type="data_ingested", severity="info")) is False
    assert sub.allows(make_notification(type="research_done", severity="info")) is True


def test_alert_severity_never_silenced():
    sub = Subscription(
        tickers=frozenset(),  # 空集合 = 全擋（除 alert）
        muted_types=frozenset({"watchdog_alert"}),
    )
    assert sub.allows(make_notification(type="watchdog_alert", severity="alert")) is True
    assert sub.allows(make_notification(type="watchdog_alert", severity="watch")) is False


def test_frozen():
    import pytest
    from pydantic import ValidationError

    sub = Subscription()
    with pytest.raises(ValidationError):
        sub.tickers = frozenset({"2330"})  # type: ignore[misc]
