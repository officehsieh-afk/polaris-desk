# Implementation Plan: 通知中心（Notification Center）Phase 1 後端核心

**Branch**: `r2/002-notification-center` | **Date**: 2026-06-10 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/002-notification-center/spec.md` + [PRD 通知中心 v0.1](../../docs/spec-kit/PRD_通知中心_v0.1.md)

## Summary

新增獨立 package `src/polaris/notifications/`，實作統一通知管線：事件（`NotificationEvent`）進 → Composer（去重、digest 合併）→ Compliance Gate（audience=user 必過 `compliance_agent.review()`，blocked 不派送＋自動產內部 incident 通知）→ 訂閱過濾 → 派送（In-app 收件匣恆開；內部通知另推 Slack webhook，transport 注入式 seam）。**不動既有 5 節點 workflow**、不引入新依賴、CI 全程 token-free / 0 真實網路呼叫、確定性可重跑。真實生產者（Watchdog R3 / ingestion R4 / eval R5）之後以同一事件格式接上，管線不改——與 Deep Research `search` seam、Watchdog `event` seam 同套路。

## Technical Context

**Language/Version**: Python 3.13（`.python-version` 已鎖；pyproject `requires-python>=3.13`）

**Primary Dependencies**:
- `pydantic >= 2.7`（事件 / 通知 / 訂閱模型，沿用 `state.py` frozen BaseModel 模式）
- 既有內部模組：`graph/nodes/compliance_agent.review()`、`graph/state.Citation`、`retry.call_with_retry`、`config.Settings`
- **不引入**任何新第三方套件（Slack 送出用 stdlib `urllib`，且預設注入 mock transport）

**Storage**: in-memory 收件匣（Phase 1 單人單機；BigQuery 持久化為 Phase 2 / PRD OQ-1）

**Testing**: `pytest >= 8.2`，全程確定性（時間取自事件欄位、不取 `now()`）、0 token、0 真實外呼

**Target Platform**: macOS / Linux 本機開發；之後隨 server 上 Cloud Run（不在本 feature scope）

**Project Type**: Single Python package（`src/polaris/notifications/`）

**Performance Goals**: SC-NC-006 — 事件進管線到派送 ≤ 5 分鐘（同步派送，實測 < 1 秒；上限為 PRD 承諾值）

**Constraints**:
- 確定性 — 同一組事件樣本重跑 3 次收件匣完全一致（SC-NC-004）
- 不得修改 `graph/workflow.py` 與既有 5 節點行為（FR-NC-012）
- 合規閘門 fail-to-floor：smart 層失敗退回 6 關鍵字 floor，絕不放行（沿用 `compliance_agent` 語意）
- Slack webhook URL 屬金鑰：只進 `.env`（`Settings` 新欄位），未設定時 no-op、不外呼

**Scale/Scope**: 7 類通知（N1–N7）× 2 受眾；fixture 事件樣本 ~10 筆（含紅隊誘導樣本）；單一全域訂閱設定

## Constitution Check

> 對 `.specify/memory/constitution.md`（v2.0.0）6 原則逐一檢視。

| Principle | 本 feature 如何遵循 | 證據 |
|---|---|---|
| **I. NFR-031（買賣建議攔截）** | 通知是新的對外輸出面：audience=user 文案必過 `compliance_agent.review()`（floor 永不解除）；blocked 不派送＋產 incident；紅隊 fixture 進測試 | spec US2、FR-NC-003；SC-NC-001 |
| **II. 引用接地** | 對使用者通知 `evidence: list[Citation]` 不得為空，空證據不派送 | spec FR-NC-004；SC-NC-002 |
| **III. 雲端協作優先 · 金鑰安全** | 0 DB 寫入（in-memory）；Slack webhook URL 只進 `.env` / `Settings`，未設定即停用；測試注入 mock transport、0 真實外呼 | FR-NC-008；`config.py` 新欄位 |
| **IV. Eval 即品質門檻** | 確定性管線 → 可寫 snapshot 式測試；CI 0 token；eval 掉分本身成為 N6 通知的事件來源（之後 R5 接） | SC-NC-004/005 |
| **V. Demo 可重現 + 離線備援** | 全功能離線可跑（fixture 注入、無網路依賴），天然符合斷網備援 | quickstart.md |
| **VI. 最新技術棧** | 只用 pydantic + stdlib + 既有內部模組；不碰 LLM SDK（smart 合規層由既有 `compliance_agent` 注入 client 時才啟用） | 無新依賴 |

**Gate result**: ✅ ALL PASS — 0 violations，Complexity Tracking 免填。

**Post-Phase 1 re-check**: 設計後 6 原則仍全部 PASS（見本檔末尾）。

## Project Structure

### Documentation (this feature)

```text
specs/002-notification-center/
├── spec.md                     # ✅ /speckit-specify 產出
├── plan.md                     # ✅ 本檔（/speckit-plan 產出）
├── research.md                 # ✅ Phase 0 產出
├── data-model.md               # ✅ Phase 1 產出
├── quickstart.md               # ✅ Phase 1 產出
├── contracts/
│   └── notification-pipeline.md  # ✅ Phase 1 產出
├── checklists/
│   └── requirements.md         # ✅ /speckit-specify 產出
└── tasks.md                    # ⏳ /speckit-tasks 產出
```

### Source Code (repository root)

```text
src/polaris/
├── notifications/              # 🆕 本 feature 全部新增於此
│   ├── __init__.py             # 🆕 公開 API re-export
│   ├── model.py                # 🆕 NotificationEvent / Notification / 列舉型別
│   ├── inbox.py                # 🆕 InAppInbox：未讀計數、列表、標已讀、篩選
│   ├── subscriptions.py        # 🆕 Subscription 模型 + allows() 過濾規則
│   ├── composer.py             # 🆕 Composer：event_id 去重、digest 合併
│   ├── channels.py             # 🆕 Channel Protocol + SlackWebhookChannel（注入式 transport）
│   ├── service.py              # 🆕 NotificationService.publish()：組裝→合規→過濾→派送
│   └── __main__.py             # 🆕 python -m polaris.notifications <events.json> demo
├── config.py                   # 🔧 Settings 加 slack_webhook_url（預設空字串）
├── graph/                      # （未動 — FR-NC-012）
└── ...                         # （其餘未動）

tests/
├── fixtures/
│   └── notification_events.json  # 🆕 mock 事件樣本（含紅隊誘導樣本）
├── test_notification_model.py     # 🆕 模型驗證、frozen、必填欄位
├── test_notification_inbox.py     # 🆕 未讀數、已讀、篩選
├── test_notification_subscriptions.py  # 🆕 watchlist / 類型開關 / alert 不可靜音
├── test_notification_composer.py  # 🆕 去重、digest 合併、watch/alert 不合併
├── test_notification_channels.py  # 🆕 Slack mock transport、retry、降級、未設定即停用
└── test_notification_service.py   # 🆕 e2e：管線全流程、合規攔截＋incident、紅線測試、確定性 3 連跑
```

**Structure Decision**:
- 沿用 Single project；通知中心是事件驅動的並行子系統（同 Watchdog 在 PRD 架構圖的定位），**自成 package、不碰 `graph/workflow.py`**。
- `service.py` 只做 orchestration；去重/合併（composer）、過濾（subscriptions）、出口（channels）、儲存（inbox）各自獨立純模組——對齊「換節點不動 wiring」的既有拆分哲學，R3/R4/R5 之後接真實生產者只 import `NotificationService.publish`。

## Complexity Tracking

> Constitution Check 全部 PASS，無需 justification。

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| — | — | — |

## Phase 0: Research

4 個技術選擇，詳見 [research.md](research.md)：

1. **通知時間戳來源**：取事件 `occurred_at`，不取 `datetime.now()` → 確定性（SC-NC-004）。
2. **去重 vs digest 的先後**：先去重（exactly-once）再 digest（同鍵合併）；兩者鍵不同（`event_id` vs `(ticker, type, date)`）。
3. **Slack transport seam**：`Callable[[str, dict], None]` 注入；預設實作用 stdlib `urllib`，測試一律注入 recorder/mock。
4. **incident 通知的受眾與證據**：audience=internal（不過攔截改寫）、severity=alert、不要求 evidence（內部訊號非對外輸出）。

## Phase 1: Design & Contracts

### Data model

- `NotificationEvent`（frozen BaseModel）：`event_id`、`type`、`audience`、`ticker?`、`title`、`body`（不可信文字）、`occurred_at`、`evidence: list[Citation]`
- `Notification`（frozen 除 `read_at` 外 → 採「mark_read 回新實例」維持 frozen）：FR-NC-001 全欄位 + `digest_count`
- `Subscription`（frozen BaseModel）：`tickers: frozenset[str] | None`（None=全收）、`muted_types: frozenset[NotificationType]`
- `PublishOutcome`：`status: Literal["delivered","deduped","digested","blocked","rejected","filtered"]` + `notification | None`

詳見 [data-model.md](data-model.md)。

### Contracts

- **`notification-pipeline.md`**：`NotificationService.publish(event) -> PublishOutcome` 的輸入/輸出契約、事件 JSON schema（R3/R4/R5 生產者對齊用）、各 outcome 語意、Slack payload 形狀。

### Quickstart

- `pytest tests/test_notification_service.py -v`
- `python -m polaris.notifications tests/fixtures/notification_events.json`

詳見 [quickstart.md](quickstart.md)。

### Agent context update

- `CLAUDE.md` `<!-- SPECKIT START -->` 區段已更新指向本 plan.md。

## Re-check after Phase 1

| Principle | Phase 1 設計後仍 PASS？ |
|---|---|
| I. NFR-031 | ✅ 合規閘門在 service 管線正中央，blocked 路徑含 incident 通知；紅隊 fixture 已列入 |
| II. 引用接地 | ✅ `evidence` 必填檢查在派送前；`Citation` 直接重用 |
| III. 金鑰安全 | ✅ webhook URL 走 `Settings`；mock transport 讓 CI 0 外呼 |
| IV. Eval 門檻 | ✅ 確定性設計 + snapshot 式 e2e 測試 |
| V. 可重現 | ✅ fixture 注入、離線可跑 |
| VI. 技術棧 | ✅ pydantic + stdlib only |

**Final gate**: ✅ ALL PASS — Phase 2 (`/speckit-tasks`) 可開始。
