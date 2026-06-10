"""Watchdog → 通知中心整合測試（specs/003 Phase 2）。

驗證第一個真實生產者接上統一通知管線，且 NFR-031 雙閘門串聯成立。
全程 token=0（無金鑰走確定性路徑）。
"""
from __future__ import annotations

from pathlib import Path

from polaris.graph.compliance import BUYSELL_KEYWORDS
from polaris.graph.watchdog.events import load_mock_events
from polaris.graph.watchdog.notify import alert_to_notification_event, watch_and_notify
from polaris.notifications import NotificationService
from tests.test_watchdog_agent import make_event

FIXTURE = Path(__file__).parent / "fixtures" / "watchdog_events.json"


# ── bridge 欄位映射 ──────────────────────────────────────────────────────────

class TestBridge:
    def test_event_field_mapping(self):
        from polaris.graph.watchdog.agent import run_watchdog

        ev = make_event()
        alert = run_watchdog(ev)
        ntf_event = alert_to_notification_event(ev, alert)
        assert ntf_event.event_id == alert.event_id
        assert ntf_event.type == "watchdog_alert"
        assert ntf_event.audience == "user"
        assert ntf_event.ticker == "2330"
        assert ntf_event.title == ev.title           # 公告原文（交第 2 閘審）
        assert ntf_event.body == alert.summary       # Watchdog 摘要（已過第 1 閘）
        assert ntf_event.severity == alert.severity
        assert ntf_event.occurred_at == ev.published_at  # 確定性：不取 now()
        assert ntf_event.evidence == alert.evidence


# ── e2e：MOPS 事件 → 收件匣 ─────────────────────────────────────────────────

class TestWatchAndNotify:
    def test_clean_event_lands_in_inbox(self):
        service = NotificationService()
        alert, outcome = watch_and_notify(make_event(), service)
        assert alert.compliance_status == "passed"
        assert outcome.status == "delivered"
        items = service.inbox.list()
        assert len(items) == 1
        n = items[0]
        assert n.type == "watchdog_alert"
        assert n.ticker == "2330"
        assert n.evidence  # 接地
        assert n.compliance_status == "passed"

    def test_duplicate_event_deduped(self):
        service = NotificationService()
        _, first = watch_and_notify(make_event(), service)
        _, second = watch_and_notify(make_event(), service)
        assert first.status == "delivered"
        assert second.status == "deduped"
        assert len(service.inbox.list()) == 1

    def test_deterministic(self):
        s1, s2 = NotificationService(), NotificationService()
        for service in (s1, s2):
            for ev in load_mock_events(FIXTURE):
                watch_and_notify(ev, service)
        snap1 = [n.model_dump() for n in s1.inbox.list()]
        snap2 = [n.model_dump() for n in s2.inbox.list()]
        assert snap1 == snap2


# ── NFR-031 雙閘門串聯 ───────────────────────────────────────────────────────

class TestDefenseInDepth:
    def test_redteam_event_blocked_with_internal_incident(self):
        """紅隊公告：第 1 閘攔截 → bridge withhold（不發 user 通知）、
        改發固定模板 internal 告警。最終收件匣：0 則 user 通知、
        1 則 internal watchdog_alert，且原文違規字眼 0 外溢。
        """
        service = NotificationService()
        redteam = next(
            e for e in load_mock_events(FIXTURE) if "redteam" in e.event_id
        )
        alert, outcome = watch_and_notify(redteam, service)
        assert alert.compliance_status == "blocked"   # 第 1 閘
        assert outcome.status == "blocked"            # bridge withhold
        items = service.inbox.list()
        assert len(items) == 1
        incident = items[0]
        assert incident.audience == "internal"
        assert incident.severity == "alert"
        # 固定模板：被攔原文（含隱性建議）不轉送下游
        for kw in BUYSELL_KEYWORDS:
            assert kw not in incident.title.replace("買賣建議", "")
            assert kw not in incident.summary.replace("買賣建議", "")

    def test_smart_layer_block_does_not_leak_original_text(self):
        """第 1 閘 smart 層（LLM）攔隱性建議時，原文不得經 bridge 外溢——
        keyword floor 不保證能再攔一次隱性語句。
        """
        from tests.conftest import FakeLLM

        service = NotificationService()
        implicit = make_event(
            event_id="mops-8888-implicit-001", ticker="8888",
            title="某公司營運公告",
            content="本公司前景明朗，目前股價甜蜜點，值得逢低布局。",
        )
        client = FakeLLM(response="VIOLATION")  # smart 層判定隱性建議
        alert, outcome = watch_and_notify(implicit, service, client=client)
        assert alert.compliance_status == "blocked"
        assert outcome.status == "blocked"
        for n in service.inbox.list():
            assert "逢低布局" not in n.title and "逢低布局" not in n.summary

    def test_full_fixture_inbox_invariants(self):
        """跑完整 fixture：匣內所有 user 通知 0 買賣建議字眼、evidence 非空。"""
        service = NotificationService()
        for ev in load_mock_events(FIXTURE):
            watch_and_notify(ev, service)
        user_items = [n for n in service.inbox.list() if n.audience == "user"]
        assert user_items  # 4 筆正常事件必須產生 user 通知
        for n in user_items:
            assert n.evidence, n.notification_id
            for kw in BUYSELL_KEYWORDS:
                assert kw not in n.title and kw not in n.summary
