# Quickstart: 通知中心 Phase 1

## 跑測試（0 token、0 外呼）

```bash
pytest tests/test_notification_model.py tests/test_notification_inbox.py \
       tests/test_notification_subscriptions.py tests/test_notification_composer.py \
       tests/test_notification_channels.py tests/test_notification_service.py -v
```

全套件回歸：

```bash
make test
```

## CLI demo（讀 fixture 事件、印收件匣）

```bash
python -m polaris.notifications tests/fixtures/notification_events.json
```

預期 stdout（節錄；重跑 3 次完全相同）：

```text
=== 通知中心收件匣（未讀 7）===
[alert] nightly eval：Faithfulness 0.87 < 0.90 — G3 硬門檻不過，請 R5 檢查 eval 管線與最近的 prompt 變更。（證據 0 筆）
[alert] 合規事故：事件 mops-9999-bad-001 文案遭攔截 — 通知文案命中合規規則，已攔截未派送…（證據 1 筆）
[info ] 2330 今日 2 則更新 — 新資料入庫 ×2（證據 2 筆）
[watch] 2330 發布重大訊息 — 本公司董事會決議通過 2026 年第一季財務報告。（證據 1 筆）
...
outcomes: delivered=6 digested=1 deduped=1 blocked=1 rejected=2 filtered=0
```

## 紅線驗證（NFR-031）

fixture 內含一筆誘導買進的事件（`mops-9999-bad-001`）：

- 它**不會**出現在收件匣的 user 通知裡。
- 取而代之的是一則 internal `compliance_incident`（severity=alert）。
- 斷言見 `tests/test_notification_service.py::test_redteam_event_blocked_with_incident`。

## 接真實生產者（R3/R4/R5 之後做）

```python
from polaris.notifications import NotificationService

outcome = service.publish({
    "event_id": alert.event_id, "type": "watchdog_alert", "audience": "user",
    "ticker": alert.ticker, "title": alert.summary, "severity": alert.severity,
    "occurred_at": ..., "evidence": [c.model_dump() for c in alert.evidence],
})
```

管線、合規閘門、訂閱過濾不需任何修改。

## 開啟內部 Slack 推播（選用）

`.env` 加一行（金鑰規則同憲法 III，永不 commit）：

```bash
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/...
```

未設定時 channel 自動停用，管線照常、不外呼。
