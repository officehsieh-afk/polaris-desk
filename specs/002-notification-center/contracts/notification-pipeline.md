# Contract: NotificationService.publish()

> 唯一入口。生產者（R3 Watchdog / R4 ingestion / R5 eval / budget monitor）只依賴本契約；
> 管線內部（composer / gate / router）可自由演進，契約不變。

## 介面

```python
service = NotificationService(
    inbox=InAppInbox(),                  # 恆開管道
    channels=[SlackWebhookChannel(...)], # 額外管道（internal 受眾）；可空
    subscription=Subscription(),         # 預設全收
    client=None,                         # 合規 smart 層 LLM client；None=floor only（CI）
)

outcome = service.publish(event)         # event: NotificationEvent | dict
```

- 傳 `dict` 時內部 `model_validate`；驗證失敗 → `PublishOutcome(status="rejected", reason=...)`，**不拋例外**（FR-NC-011）。
- `publish` 為同步、單執行緒語意；冪等性由 `event_id` 去重保證。

## 事件 JSON schema（生產者對齊用）

```jsonc
{
  "event_id": "mops-2330-20260315-001",   // 必填，唯一；重送同 id 會被去重
  "type": "watchdog_alert",                // N1–N7 列舉（不得用 compliance_incident）
  "audience": "user",                      // user | internal
  "ticker": "2330",                        // 可選；N6/N7 系統級事件可省略
  "title": "2330 發布重大訊息",             // 必填（不可信文字）
  "body": "公告全文…",                      // 可選（不可信文字）
  "severity": "watch",                     // info(預設) | watch | alert
  "occurred_at": "2026-03-15T08:30:00",    // 必填 ISO-8601；即通知 created_at
  "evidence": [                            // audience=user 派送前強制 ≥ 1 筆
    {"source_id": "mops-2330-20260315", "snippet": "董事會決議…", "origin": "news"}
  ]
}
```

> 與 R3 開工指南 §3 的 `WatchdogAlert` 對齊：R3 把 `WatchdogAlert` 映射成本事件
> （`summary`→`title`/`body`、`evidence` 直通、severity 直通）即可接上，agent 邏輯不變。

## PublishOutcome 語意

| status | 條件 | notification | 收件匣 | Slack |
|---|---|---|---|---|
| `delivered` | 通過全管線 | 該通知 | ✅ 新增未讀 | internal 受眾 → ✅ |
| `digested` | 同 `(ticker,type,日)` 已有 info 通知 | 合併後通知（`digest_count` +1） | ✅ 原則更新（仍 1 則） | — |
| `deduped` | `event_id` 已見過 | None | 不變 | — |
| `blocked` | user 受眾文案被合規攔截 | **incident 通知**（internal/alert） | ❌ 原通知不入；✅ incident 入 | ✅ incident 推送 |
| `rejected` | 事件驗證失敗，或 user 受眾 evidence 為空 | None | 不變 | — |
| `filtered` | 訂閱規則不放行 | None | 不變 | — |

不變量（測試直接斷言）：
1. 收件匣中任何 user 受眾通知的 `title`/`summary` **不含** `BUYSELL_KEYWORDS` 任一（SC-NC-001）。
2. 收件匣中任何 user 受眾通知 `evidence` 非空（SC-NC-002）。
3. 同一 `event_id` 重送 N 次，收件匣恆 1 則（SC-NC-003）。
4. `publish` 永不對生產者拋例外（壞事件 → `rejected`；管道失敗 → 降級記錄）。

## InAppInbox 查詢介面

```python
inbox.unread_count() -> int
inbox.list(ticker=None, type=None) -> list[Notification]   # created_at 倒序
inbox.mark_read(notification_id, at: datetime) -> Notification | None  # 回新實例；查無回 None
inbox.delivery_failures -> list[str]                        # 外送降級記錄（FR-NC-009）
```

## SlackWebhookChannel payload 形狀

```jsonc
// POST {webhook_url}
{"text": "[ALERT] pipeline_health — nightly eval：Faithfulness 0.87 < 0.90（evt eval-20260610-001）"}
```

- `webhook_url` 來自 `Settings.slack_webhook_url`（env `SLACK_WEBHOOK_URL`，只進 `.env`）。
- URL 為空 → channel 停用（`send()` no-op、0 外呼）。
- transport 注入：`Callable[[str, dict], None]`；預設 stdlib urllib，測試注入 recorder / raiser。
- 失敗：`call_with_retry` 重試暫時性錯誤；用盡 → 記 `inbox.delivery_failures`、不拋。
