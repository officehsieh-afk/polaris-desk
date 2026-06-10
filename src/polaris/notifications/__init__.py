"""Polaris Desk 通知中心（specs/002）— 公開 API。

統一通知管線：事件 → Composer（去重 / digest）→ Compliance Gate →
訂閱過濾 → In-app 收件匣 + 內部 Slack channel。
生產者只需 ``NotificationService.publish(event)``，契約見
``specs/002-notification-center/contracts/notification-pipeline.md``。
"""
from polaris.notifications.channels import Channel, SlackWebhookChannel
from polaris.notifications.inbox import InAppInbox
from polaris.notifications.model import (
    Notification,
    NotificationEvent,
    PublishOutcome,
)
from polaris.notifications.service import NotificationService
from polaris.notifications.subscriptions import Subscription

__all__ = [
    "Channel",
    "InAppInbox",
    "Notification",
    "NotificationEvent",
    "NotificationService",
    "PublishOutcome",
    "SlackWebhookChannel",
    "Subscription",
]
