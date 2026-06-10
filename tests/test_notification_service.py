"""NotificationService e2e 管線測試（specs/002 T010/T012/T016/T019/T022）。

契約見 specs/002-notification-center/contracts/notification-pipeline.md：
- US1：publish → delivered、壞事件 rejected 不拋、去重、確定性 3 連跑。
- US2：合規閘門 — 紅隊事件 blocked + incident、internal skipped、空證據 rejected、
  不變量（匣內 user 通知 0 買賣建議字眼、evidence 皆非空）。
- US3：訂閱過濾 filtered。
- US4：internal 通知路由到 Slack channel（mock transport）、失敗降級記錄。
- US5：digest 合併 digested。
- CLI smoke：python -m polaris.notifications <fixture>。
"""
from __future__ import annotations

import json
from pathlib import Path

from polaris.graph.compliance import BUYSELL_KEYWORDS
from polaris.notifications import NotificationService
from polaris.notifications.channels import SlackWebhookChannel
from polaris.notifications.inbox import InAppInbox
from polaris.notifications.subscriptions import Subscription
from tests.conftest import ApiError
from tests.test_notification_channels import RecorderTransport
from tests.test_notification_model import TS, make_event

FIXTURE = Path(__file__).parent / "fixtures" / "notification_events.json"


def load_fixture_events() -> list[dict]:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def make_service(**overrides) -> NotificationService:
    params: dict = dict(inbox=InAppInbox(), channels=[], subscription=Subscription())
    params.update(overrides)
    return NotificationService(**params)


# ── US1：管線基本流 ──────────────────────────────────────────────────────────

class TestPipelineBasics:
    def test_publish_clean_event_delivered(self):
        service = make_service()
        outcome = service.publish(make_event())
        assert outcome.status == "delivered"
        n = outcome.notification
        assert n is not None
        assert n.title and n.summary and n.evidence and n.deep_link
        assert n.compliance_status == "passed"
        assert service.inbox.unread_count() == 1

    def test_publish_accepts_dict(self):
        outcome = make_service().publish(load_fixture_events()[0])
        assert outcome.status == "delivered"

    def test_invalid_event_rejected_not_raised(self):
        service = make_service()
        outcome = service.publish({"event_id": "bad", "type": "data_ingested"})
        assert outcome.status == "rejected"
        assert outcome.reason  # 人讀原因
        assert service.inbox.list() == []
        # 壞事件不弄垮管線：後續事件照常處理
        assert service.publish(make_event()).status == "delivered"

    def test_duplicate_event_id_deduped(self):
        service = make_service()
        assert service.publish(make_event()).status == "delivered"
        assert service.publish(make_event(title="同 id 不同內容")).status == "deduped"
        assert len(service.inbox.list()) == 1  # SC-NC-003

    def test_deterministic_three_runs_identical(self):
        """SC-NC-004：同 fixture 3 連跑，收件匣完全一致。"""
        events = load_fixture_events()
        snapshots = []
        for _ in range(3):
            service = make_service()
            for event in events:
                service.publish(event)
            snapshots.append([n.model_dump() for n in service.inbox.list()])
        assert snapshots[0] == snapshots[1] == snapshots[2]


# ── US2：合規閘門（NFR-031 紅線）────────────────────────────────────────────

class TestComplianceGate:
    def test_redteam_event_blocked_with_incident(self):
        service = make_service()
        outcome = service.publish(make_event(
            event_id="mops-9999-bad-001",
            ticker="9999",
            title="9999 利多消息，建議買進",
        ))
        assert outcome.status == "blocked"
        # 原通知不入匣；取而代之 internal incident（alert）
        incident = outcome.notification
        assert incident is not None
        assert incident.type == "compliance_incident"
        assert incident.audience == "internal"
        assert incident.severity == "alert"
        assert "mops-9999-bad-001" in incident.title
        inbox_items = service.inbox.list()
        assert len(inbox_items) == 1 and inbox_items[0].type == "compliance_incident"
        # incident 文案不得二次外溢違規字眼
        for kw in BUYSELL_KEYWORDS:
            assert kw not in incident.title and kw not in incident.summary

    def test_internal_event_skips_review(self):
        outcome = make_service().publish(make_event(
            event_id="eval-001", type="pipeline_health", audience="internal",
            ticker=None, title="eval 掉分", evidence=[],
        ))
        assert outcome.status == "delivered"
        assert outcome.notification.compliance_status == "skipped"

    def test_user_event_without_evidence_rejected(self):
        """接地原則延伸（FR-NC-004）：沒有來源的事件不發通知。"""
        outcome = make_service().publish(make_event(evidence=[]))
        assert outcome.status == "rejected"
        assert "evidence" in outcome.reason

    def test_inbox_invariants_after_fixture_run(self):
        """契約不變量 1+2：匣內 user 通知 0 違規字眼、evidence 皆非空。"""
        service = make_service()
        for event in load_fixture_events():
            service.publish(event)
        user_items = [n for n in service.inbox.list() if n.audience == "user"]
        assert user_items  # fixture 必須產生 user 通知才有意義
        for n in user_items:
            assert n.evidence, n.notification_id
            for kw in BUYSELL_KEYWORDS:
                assert kw not in n.title and kw not in n.summary

    def test_smart_layer_flags_implicit_advice(self):
        """有 client 時 smart 層補抓隱性建議（沿用 compliance_agent 契約）。"""
        from tests.conftest import FakeLLM

        service = make_service(client=FakeLLM(response="VIOLATION"))
        outcome = service.publish(make_event(title="9999 值得逢低布局"))
        assert outcome.status == "blocked"


# ── US3：訂閱過濾 ────────────────────────────────────────────────────────────

class TestSubscriptionFilter:
    def test_unsubscribed_ticker_filtered(self):
        service = make_service(subscription=Subscription(tickers=frozenset({"2330"})))
        assert service.publish(make_event()).status == "delivered"  # 2330
        outcome = service.publish(make_event(
            event_id="mops-2891-001", ticker="2891", severity="info",
        ))
        assert outcome.status == "filtered"
        assert len(service.inbox.list()) == 1

    def test_alert_not_silenced_by_subscription(self):
        service = make_service(subscription=Subscription(tickers=frozenset()))
        outcome = service.publish(make_event(severity="alert"))
        assert outcome.status == "delivered"


# ── US4：內部告警送 Slack ────────────────────────────────────────────────────

class TestSlackRouting:
    URL = "https://hooks.slack.invalid/services/T000/B000/XXX"

    def internal_event(self, **overrides):
        params = dict(
            event_id="eval-20260610-001", type="pipeline_health", audience="internal",
            ticker=None, title="nightly eval：Faithfulness 0.87 < 0.90",
            severity="alert", evidence=[],
        )
        params.update(overrides)
        return make_event(**params)

    def test_internal_notification_pushed_to_slack(self):
        transport = RecorderTransport()
        service = make_service(channels=[SlackWebhookChannel(self.URL, transport=transport)])
        assert service.publish(self.internal_event()).status == "delivered"
        assert len(transport.calls) == 1
        assert "Faithfulness" in transport.calls[0][1]["text"]

    def test_user_notification_not_pushed_to_slack(self):
        transport = RecorderTransport()
        service = make_service(channels=[SlackWebhookChannel(self.URL, transport=transport)])
        service.publish(make_event())  # user 受眾
        assert transport.calls == []

    def test_incident_pushed_to_slack(self):
        transport = RecorderTransport()
        service = make_service(channels=[SlackWebhookChannel(self.URL, transport=transport)])
        service.publish(make_event(title="建議買進"))
        assert len(transport.calls) == 1
        assert "compliance_incident" in transport.calls[0][1]["text"]

    def test_channel_failure_degrades_and_records(self):
        """FR-NC-009：重試用盡 → 降級僅收件匣、記錄失敗、不拋給生產者。"""
        transport = RecorderTransport(fail_times=99, error=ApiError(503))
        channel = SlackWebhookChannel(self.URL, transport=transport, sleep=lambda _s: None)
        service = make_service(channels=[channel])
        outcome = service.publish(self.internal_event())
        assert outcome.status == "delivered"  # 收件匣路徑不受影響
        assert service.inbox.unread_count() == 1
        assert len(service.inbox.delivery_failures) == 1


# ── US5：digest 合併 ─────────────────────────────────────────────────────────

class TestDigest:
    def ingest_event(self, seq: int, **overrides):
        params = dict(
            event_id=f"ing-2330-20260601-{seq:03d}", type="data_ingested",
            severity="info", title=f"2330 入庫 #{seq}",
            occurred_at=TS.replace(month=6, day=1, hour=9 + seq),
        )
        params.update(overrides)
        return make_event(**params)

    def test_same_day_info_events_digested(self):
        service = make_service()
        assert service.publish(self.ingest_event(1)).status == "delivered"
        assert service.publish(self.ingest_event(2)).status == "digested"
        outcome = service.publish(self.ingest_event(3))
        assert outcome.status == "digested"
        items = service.inbox.list()
        assert len(items) == 1
        assert items[0].digest_count == 3
        assert len(items[0].evidence) == 3

    def test_watch_events_not_digested(self):
        service = make_service()
        service.publish(self.ingest_event(1))
        outcome = service.publish(self.ingest_event(2, severity="watch"))
        assert outcome.status == "delivered"
        assert len(service.inbox.list()) == 2


# ── CLI smoke（T022）────────────────────────────────────────────────────────

def test_cli_main_prints_inbox_and_outcomes(capsys):
    from polaris.notifications.__main__ import main

    exit_code = main([str(FIXTURE)])
    out = capsys.readouterr().out
    assert exit_code == 0
    assert "通知中心收件匣" in out
    assert "delivered=" in out and "blocked=1" in out and "deduped=1" in out
    # 紅隊事件的違規字眼不得出現在收件匣輸出（incident 模板安全）
    assert "建議買進" not in out
