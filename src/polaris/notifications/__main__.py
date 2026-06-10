"""CLI demo：``python -m polaris.notifications <events.json>``。

讀事件 fixture、跑完整管線、印收件匣與 outcome 統計。
重跑 3 次輸出完全相同（確定性，SC-NC-004）；無金鑰、0 token、0 外呼
（Slack channel 未設 ``SLACK_WEBHOOK_URL`` 時自動停用）。
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

from polaris.config import settings
from polaris.notifications.channels import SlackWebhookChannel
from polaris.notifications.service import NotificationService


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 1:
        print("用法：python -m polaris.notifications <events.json>", file=sys.stderr)
        return 2

    events = json.loads(Path(args[0]).read_text(encoding="utf-8"))
    service = NotificationService(
        channels=[SlackWebhookChannel(settings.slack_webhook_url)],
    )

    counts: Counter[str] = Counter()
    for event in events:
        counts[service.publish(event).status] += 1

    items = service.inbox.list()
    print(f"=== 通知中心收件匣（未讀 {service.inbox.unread_count()}）===")
    for n in items:
        print(
            f"[{n.severity:<5}] {n.title} — {n.summary}"
            f"（證據 {len(n.evidence)} 筆）"
        )
    print(
        "outcomes: "
        + " ".join(
            f"{key}={counts.get(key, 0)}"
            for key in ("delivered", "digested", "deduped", "blocked", "rejected", "filtered")
        )
    )
    if service.inbox.delivery_failures:
        print(f"delivery_failures: {len(service.inbox.delivery_failures)}")
    return 0


if __name__ == "__main__":  # pragma: no cover — 由 CLI smoke 測 main()
    raise SystemExit(main())
