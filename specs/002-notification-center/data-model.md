# Data Model: 通知中心 Phase 1 後端核心

> 全部為 pydantic v2 `frozen=True` BaseModel（沿用 `graph/state.py` 的 `Citation` 模式）。
> 時間欄位一律 `datetime`（帶 tz 或 naive 皆可，fixture 用 ISO-8601 字串解析）；管線不呼叫 `now()`。

## 列舉型別

```python
NotificationType = Literal[
    "watchdog_alert",        # N1 合規/重大訊息警示（Watchdog）
    "watchlist_event",       # N2 追蹤清單事件（法說公告、財報發布）
    "data_ingested",         # N3 新資料入庫
    "research_done",         # N4 Deep Research 完成
    "contradiction",         # N5 來源矛盾偵測
    "pipeline_health",       # N6 管線健康（ingestion 失敗、eval 掉分）
    "ops_alert",             # N7 成本警報
    "compliance_incident",   # N7 合規事故（由 service 在攔截時自動合成）
]

Audience = Literal["user", "internal"]
Severity = Literal["info", "watch", "alert"]
DeliveryStatus = Literal["delivered", "deduped", "digested", "blocked", "rejected", "filtered"]
```

## NotificationEvent（事件 — 生產者發出的原始輸入）

| 欄位 | 型別 | 約束 | 說明 |
|---|---|---|---|
| `event_id` | `str` | min_length=1 | 唯一識別碼；去重鍵（如 `mops-2330-20260315-001`） |
| `type` | `NotificationType` | 必填；不得為 `compliance_incident`（保留給 service 合成） | 通知類型 |
| `audience` | `Audience` | 必填 | user → 過合規閘門＋evidence 必填 |
| `ticker` | `str \| None` | default None | 公司代號；N6/N7 通常無 |
| `title` | `str` | min_length=1 | 事件標題（不可信文字） |
| `body` | `str` | default "" | 事件內文（不可信文字；digest 摘要素材） |
| `severity` | `Severity` | default "info" | 生產者建議值；composer 可依規則升級 |
| `occurred_at` | `datetime` | 必填 | 事件發生時間；通知時間戳來源（research §1） |
| `evidence` | `list[Citation]` | default [] | 來源證據；audience=user 在派送前強制非空 |

驗證：缺必填 / 空字串 → pydantic `ValidationError`；service 對 dict 輸入用 `model_validate` 包 try → `rejected`（FR-NC-011，壞事件不弄垮管線）。

## Notification（通知 — 管線組裝後的派送單位）

| 欄位 | 型別 | 約束 | 說明 |
|---|---|---|---|
| `notification_id` | `str` | min_length=1 | `ntf-{event_id}`（確定性派生，不用 uuid4） |
| `event_id` | `str` | min_length=1 | 來源事件識別碼（digest 時為首筆） |
| `type` | `NotificationType` | 必填 | 同事件 |
| `audience` | `Audience` | 必填 | 同事件 |
| `ticker` | `str \| None` | default None | 同事件 |
| `title` | `str` | min_length=1 | 合規閘門後的最終文案 |
| `summary` | `str` | max_length=100（中文字數以 len 計） | 合規閘門後的最終摘要 |
| `severity` | `Severity` | 必填 | — |
| `evidence` | `list[Citation]` | user 受眾派送前非空 | — |
| `deep_link` | `str` | default 形如 `/notifications/{notification_id}` | 回 app 詳情 |
| `created_at` | `datetime` | 必填 | = 事件 `occurred_at` |
| `read_at` | `datetime \| None` | default None | 已讀時間 |
| `compliance_status` | `Literal["passed","blocked","skipped"]` | 必填 | user→passed；internal→skipped（不審改寫） |
| `digest_count` | `int` | ge=1, default 1 | 合併筆數；>1 表 digest 通知 |

**Frozen 與已讀的相容**：`Notification` 維持 frozen；`InAppInbox.mark_read(notification_id, at)` 以 `model_copy(update={"read_at": at})` 產生新實例替換存放——外部拿到的物件永遠 immutable。`at` 由呼叫端傳入（不取 now，維持確定性）。

**State transitions**：`unread (read_at=None) → read (read_at=ts)`；單向、不可逆轉回未讀（Phase 1 無此需求）。

## Subscription（訂閱 — Phase 1 單一全域設定）

| 欄位 | 型別 | 約束 | 說明 |
|---|---|---|---|
| `tickers` | `frozenset[str] \| None` | default None | None＝全收（FR-NC-006 預設）；空集合＝全擋（除 alert） |
| `muted_types` | `frozenset[NotificationType]` | default frozenset() | 被關閉的類型 |

規則 `allows(n: Notification) -> bool`：
1. `n.severity == "alert"` → **恆 True**（安全攸關不可靜音）。
2. `n.type in muted_types` → False。
3. `tickers is not None and n.ticker is not None and n.ticker not in tickers` → False。
4. 其餘 True。（`ticker=None` 的通知不受 watchlist 過濾——系統級訊息。）

## PublishOutcome（publish 回傳）

| 欄位 | 型別 | 說明 |
|---|---|---|
| `status` | `DeliveryStatus` | 管線最終判定（語意見 contracts） |
| `notification` | `Notification \| None` | delivered/digested 時為派送的通知；blocked 時為 incident 通知；其餘 None |
| `reason` | `str` | rejected/filtered/deduped 的人讀原因；其餘空字串 |

## 關聯圖

```
NotificationEvent ──publish()──▶ [dedupe] ─▶ [digest] ─▶ [compliance gate] ─▶ [Subscription.allows] ─▶ Notification
       │ 1:1（一般）/ N:1（digest）                │ blocked                                              │
       └────────────────────────────────────────── └─▶ ComplianceIncident（= internal Notification）──────┤
                                                                                                          ▼
                                                                              InAppInbox（恆開）＋ SlackWebhookChannel（internal）
```
