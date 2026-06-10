"""Watchdog → 通知中心 bridge（specs/003 Phase 2 / specs/002 後續）。

把 :func:`run_watchdog` 的輸出轉成 ``NotificationEvent`` 餵進
``NotificationService.publish()``——第一個接上統一通知管線的真實生產者
（contracts/notification-pipeline.md §事件 schema）。

Defense-in-depth（NFR-031 雙閘門串聯）：
- 第 1 閘：Watchdog 摘要過 ``compliance_agent.review``。**blocked → bridge 直接
  withhold**：不發 user 通知（安全訊息無資訊價值），改發固定模板的 internal
  告警（原文不外溢——第 1 閘可能是 smart 層攔的隱性建議，keyword floor
  不保證能再攔一次，所以絕不把原文轉送下游）。
- 第 2 閘：通過第 1 閘的 alert，NotificationService 仍對 user 受眾的
  ``title+summary`` 再審一次（backstop：兩閘的 smart 層判斷各自獨立）。
"""
from __future__ import annotations

from polaris.notifications.model import NotificationEvent, PublishOutcome
from polaris.notifications.service import NotificationService
from polaris.graph.watchdog.agent import run_watchdog
from polaris.graph.watchdog.events import MopsEvent
from polaris.graph.watchdog.state import WatchdogAlert


def alert_to_notification_event(
    event: MopsEvent, alert: WatchdogAlert
) -> NotificationEvent:
    """組 ``NotificationEvent``：title 取公告原文（不可信，交第 2 閘審）、
    body 取 Watchdog 摘要（已過第 1 閘）、時間取公告 ``published_at``（確定性）。
    """
    return NotificationEvent(
        event_id=alert.event_id,
        type="watchdog_alert",
        audience="user",
        ticker=alert.ticker,
        title=event.title,
        body=alert.summary,
        severity=alert.severity,
        occurred_at=event.published_at,
        evidence=list(alert.evidence),
    )


def _incident_event(event: MopsEvent, alert: WatchdogAlert) -> NotificationEvent:
    """第 1 閘攔截時的 internal 告警（固定模板；被攔原文不轉送下游）。"""
    return NotificationEvent(
        event_id=f"{alert.event_id}-wd-incident",
        type="watchdog_alert",
        audience="internal",
        ticker=alert.ticker,
        title=f"Watchdog 攔截：事件 {alert.event_id} 摘要含買賣建議",
        body="Watchdog 合規閘已攔截、user 通知未發；請依憲法原則 I 記錄 incident 並補測試。",
        severity="alert",
        occurred_at=event.published_at,
        evidence=list(alert.evidence),
    )


def watch_and_notify(
    event: MopsEvent,
    service: NotificationService,
    *,
    client=None,
) -> tuple[WatchdogAlert, PublishOutcome]:
    """一站式：跑 Watchdog → 發佈通知。回 (alert, outcome) 供呼叫端記錄。

    outcome.status 語意同 publish 契約；blocked = 任一閘攔下（user 通知未發、
    internal 告警已入匣，``outcome.notification`` 即該告警）。
    """
    alert = run_watchdog(event, client=client)
    if alert.compliance_status == "blocked":
        incident_outcome = service.publish(_incident_event(event, alert))
        return alert, PublishOutcome(
            status="blocked",
            notification=incident_outcome.notification,
            reason=f"watchdog blocked event {alert.event_id}; internal incident filed",
        )
    outcome = service.publish(alert_to_notification_event(event, alert))
    return alert, outcome


__all__ = ["alert_to_notification_event", "watch_and_notify"]
