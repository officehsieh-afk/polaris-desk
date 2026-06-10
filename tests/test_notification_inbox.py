"""InAppInbox 測試（specs/002 T006 / US1）。

未讀計數、時間倒序列表、ticker/type 篩選、mark_read 回新實例（原件 frozen
不變）、查無 id 回 None、空收件匣未讀 = 0。
"""
from __future__ import annotations

from datetime import datetime

from polaris.notifications.inbox import InAppInbox
from tests.test_notification_model import make_notification

T1 = datetime(2026, 6, 1, 9, 0)
T2 = datetime(2026, 6, 5, 16, 45)
T3 = datetime(2026, 6, 8, 11, 0)


def make_inbox() -> InAppInbox:
    inbox = InAppInbox()
    inbox.add(make_notification(notification_id="ntf-a", event_id="a", created_at=T1,
                                ticker="2330", type="data_ingested"))
    inbox.add(make_notification(notification_id="ntf-b", event_id="b", created_at=T2,
                                ticker=None, type="research_done"))
    inbox.add(make_notification(notification_id="ntf-c", event_id="c", created_at=T3,
                                ticker="2891", type="watchdog_alert"))
    return inbox


def test_empty_inbox():
    inbox = InAppInbox()
    assert inbox.unread_count() == 0
    assert inbox.list() == []
    assert inbox.delivery_failures == []


def test_unread_count_and_mark_read():
    inbox = make_inbox()
    assert inbox.unread_count() == 3
    read = inbox.mark_read("ntf-a", at=T3)
    assert read is not None and read.read_at == T3
    assert inbox.unread_count() == 2
    # 已讀通知保留可查（不消失）
    assert inbox.get("ntf-a") is not None
    assert inbox.get("ntf-a").read_at == T3


def test_mark_read_returns_new_instance_original_frozen():
    inbox = InAppInbox()
    n = make_notification(notification_id="ntf-x", event_id="x", created_at=T1)
    inbox.add(n)
    read = inbox.mark_read("ntf-x", at=T2)
    assert read is not n
    assert n.read_at is None  # 外部持有的原件不變


def test_mark_read_unknown_id_returns_none():
    assert make_inbox().mark_read("ntf-nope", at=T1) is None


def test_list_sorted_by_created_at_desc():
    assert [n.notification_id for n in make_inbox().list()] == ["ntf-c", "ntf-b", "ntf-a"]


def test_list_filter_by_ticker_and_type():
    inbox = make_inbox()
    assert [n.notification_id for n in inbox.list(ticker="2330")] == ["ntf-a"]
    assert [n.notification_id for n in inbox.list(type="research_done")] == ["ntf-b"]
    assert inbox.list(ticker="2330", type="research_done") == []


def test_replace_updates_in_place():
    inbox = make_inbox()
    merged = inbox.get("ntf-a").model_copy(update={"digest_count": 3})
    inbox.add(merged)  # 同 id 覆寫
    assert len(inbox.list()) == 3
    assert inbox.get("ntf-a").digest_count == 3
