"""Composer 測試（specs/002 T007 去重 / T020 digest）。

- 去重：同 event_id 第二次 → duplicate；同 id 不同內容以第一筆為準。
- 映射：notification_id 確定性派生、created_at = occurred_at、summary ≤ 100。
- digest：同 (ticker, type, 日) 多則 info 合併；watch/alert 不合併；跨日不合併；
  去重優先於 digest（重複 id 不計入 count）。
"""
from __future__ import annotations

from datetime import datetime

from polaris.notifications.composer import Composer
from tests.test_notification_model import make_event


def test_duplicate_event_id_detected():
    c = Composer()
    assert c.is_duplicate(make_event()) is False
    assert c.is_duplicate(make_event()) is True


def test_duplicate_with_different_content_still_dropped():
    """同 id 不同內容 → 以第一筆為準，後到視為重複（edge case 規格）。"""
    c = Composer()
    assert c.is_duplicate(make_event(title="第一版")) is False
    assert c.is_duplicate(make_event(title="第二版內容不同")) is True


def test_build_field_mapping():
    c = Composer()
    ev = make_event()
    n = c.build(ev, compliance_status="passed")
    assert n.notification_id == f"ntf-{ev.event_id}"
    assert n.event_id == ev.event_id
    assert n.created_at == ev.occurred_at  # 不取 now()（確定性）
    assert n.deep_link == f"/notifications/{n.notification_id}"
    assert n.title == ev.title
    assert n.summary == ev.body
    assert n.digest_count == 1
    assert n.compliance_status == "passed"


def test_build_summary_truncated_to_100():
    n = Composer().build(make_event(body="長" * 150), compliance_status="passed")
    assert len(n.summary) == 100


def test_build_summary_falls_back_to_title_when_body_empty():
    ev = make_event(body="")
    n = Composer().build(ev, compliance_status="passed")
    assert n.summary == ev.title


# ── digest（US5 / T020）─────────────────────────────────────────────────────

def info_event(seq: int, *, day: int = 1, **overrides):
    params = dict(
        event_id=f"ing-2330-2026060{day}-{seq:03d}",
        type="data_ingested",
        severity="info",
        title=f"2330 入庫 #{seq}",
        body=f"第 {seq} 筆入庫",
        occurred_at=datetime(2026, 6, day, 9 + seq, 0),
    )
    params.update(overrides)
    return make_event(**params)


def test_digest_merges_same_key_info_events():
    c = Composer()
    first = c.build(info_event(1), compliance_status="passed")
    c.register_digest(first)
    ev2, ev3 = info_event(2), info_event(3)
    merged2 = c.merge_digest(first, ev2)
    merged3 = c.merge_digest(merged2, ev3)
    assert merged3.digest_count == 3
    assert merged3.notification_id == first.notification_id  # 同則更新，不長新則
    assert len(merged3.evidence) == 3  # 證據累積
    assert "3 則更新" in merged3.title
    assert merged3.created_at == ev3.occurred_at  # 時間推進到最新一筆


def test_digest_lookup_only_matches_same_key():
    c = Composer()
    first = c.build(info_event(1), compliance_status="passed")
    c.register_digest(first)
    assert c.lookup_digest(info_event(2)) == first.notification_id
    # 跨日不合併
    assert c.lookup_digest(info_event(2, day=2)) is None
    # 不同類型不合併
    assert c.lookup_digest(info_event(2, type="watchlist_event")) is None
    # 不同 ticker 不合併
    assert c.lookup_digest(info_event(2, ticker="2891")) is None


def test_watch_and_alert_never_digested():
    c = Composer()
    first = c.build(info_event(1), compliance_status="passed")
    c.register_digest(first)
    assert c.lookup_digest(info_event(2, severity="watch")) is None
    assert c.lookup_digest(info_event(2, severity="alert")) is None
    # watch/alert 也不註冊 digest 鍵
    w = c.build(info_event(5, severity="watch"), compliance_status="passed")
    c.register_digest(w)
    assert c.lookup_digest(info_event(6)) == first.notification_id  # 仍指向 info 那則
