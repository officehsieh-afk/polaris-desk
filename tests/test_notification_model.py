"""通知中心資料模型測試（specs/002 T003）。

對應 data-model.md：NotificationEvent / Notification / PublishOutcome 的
必填驗證、frozen 不可變、保留型別禁用、欄位約束、dict round-trip。
"""
from __future__ import annotations

from datetime import datetime

import pytest
from pydantic import ValidationError

from polaris.graph.state import Citation
from polaris.notifications.model import (
    Notification,
    NotificationEvent,
    PublishOutcome,
)

TS = datetime(2026, 3, 15, 8, 30)


def make_event(**overrides) -> NotificationEvent:
    base = dict(
        event_id="mops-2330-20260315-001",
        type="watchdog_alert",
        audience="user",
        ticker="2330",
        title="2330 發布重大訊息",
        body="董事會決議……",
        severity="watch",
        occurred_at=TS,
        evidence=[Citation(source_id="mops-2330-20260315", snippet="董事會決議…", origin="news")],
    )
    base.update(overrides)
    return NotificationEvent(**base)


def make_notification(**overrides) -> Notification:
    base = dict(
        notification_id="ntf-mops-2330-20260315-001",
        event_id="mops-2330-20260315-001",
        type="watchdog_alert",
        audience="user",
        ticker="2330",
        title="2330 發布重大訊息",
        summary="董事會決議……",
        severity="watch",
        evidence=[Citation(source_id="mops-2330-20260315", snippet="董事會決議…", origin="news")],
        deep_link="/notifications/ntf-mops-2330-20260315-001",
        created_at=TS,
        compliance_status="passed",
    )
    base.update(overrides)
    return Notification(**base)


# ── NotificationEvent ────────────────────────────────────────────────────────

class TestNotificationEvent:
    def test_valid_event_roundtrip(self):
        ev = make_event()
        again = NotificationEvent.model_validate(ev.model_dump())
        assert again == ev

    def test_frozen(self):
        ev = make_event()
        with pytest.raises(ValidationError):
            ev.title = "改寫"  # type: ignore[misc]

    @pytest.mark.parametrize("field", ["event_id", "title"])
    def test_required_min_length(self, field):
        with pytest.raises(ValidationError):
            make_event(**{field: ""})

    def test_missing_occurred_at_rejected(self):
        data = make_event().model_dump()
        del data["occurred_at"]
        with pytest.raises(ValidationError):
            NotificationEvent.model_validate(data)

    def test_compliance_incident_type_reserved(self):
        """compliance_incident 保留給 service 合成，生產者不得使用。"""
        with pytest.raises(ValidationError):
            make_event(type="compliance_incident")

    def test_defaults(self):
        ev = make_event(ticker=None, body="", severity="info", evidence=[])
        assert ev.ticker is None
        assert ev.severity == "info"
        assert ev.evidence == []

    def test_unknown_type_rejected(self):
        with pytest.raises(ValidationError):
            make_event(type="not_a_type")


# ── Notification ─────────────────────────────────────────────────────────────

class TestNotification:
    def test_valid_and_frozen(self):
        n = make_notification()
        with pytest.raises(ValidationError):
            n.read_at = TS  # type: ignore[misc]

    def test_summary_max_100(self):
        with pytest.raises(ValidationError):
            make_notification(summary="長" * 101)
        assert make_notification(summary="長" * 100).summary == "長" * 100

    def test_digest_count_ge_1(self):
        with pytest.raises(ValidationError):
            make_notification(digest_count=0)
        assert make_notification(digest_count=3).digest_count == 3

    def test_unread_by_default_mark_read_via_copy(self):
        n = make_notification()
        assert n.read_at is None
        read = n.model_copy(update={"read_at": TS})
        assert read.read_at == TS and n.read_at is None  # 原件不變

    def test_internal_notification_allows_empty_evidence(self):
        n = make_notification(audience="internal", evidence=[], compliance_status="skipped")
        assert n.evidence == []


# ── PublishOutcome ───────────────────────────────────────────────────────────

class TestPublishOutcome:
    @pytest.mark.parametrize(
        "status", ["delivered", "deduped", "digested", "blocked", "rejected", "filtered"]
    )
    def test_statuses(self, status):
        out = PublishOutcome(status=status)
        assert out.status == status
        assert out.notification is None
        assert out.reason == ""

    def test_unknown_status_rejected(self):
        with pytest.raises(ValidationError):
            PublishOutcome(status="lost")

    def test_carries_notification(self):
        n = make_notification()
        assert PublishOutcome(status="delivered", notification=n).notification == n
