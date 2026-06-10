# Tasks: 通知中心（Notification Center）Phase 1 後端核心

**Input**: Design documents from `specs/002-notification-center/`
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, contracts/notification-pipeline.md ✅
**Tests**: 含測試任務（repo 慣例全程 TDD；spec SC-NC-005 要求 0 token / 0 外呼測試）

## Phase 1: Setup

- [X] T001 建立 package 骨架：`src/polaris/notifications/__init__.py`（空 re-export 起步）與 `tests/fixtures/` 目錄確認存在
- [X] T002 `src/polaris/config.py` 的 `Settings` 加 `slack_webhook_url: str = ""`（env `SLACK_WEBHOOK_URL`；註解標明金鑰規則同憲法 III）

## Phase 2: Foundational（阻塞所有 user story）

- [X] T003 [P] 測試先行：`tests/test_notification_model.py` — `NotificationEvent`/`Notification`/`PublishOutcome` 驗證（必填、frozen、`type` 不得為 `compliance_incident`、`summary` ≤100、`digest_count` ≥1、dict round-trip）
- [X] T004 實作 `src/polaris/notifications/model.py` — 列舉型別 + 三個 frozen BaseModel + `PublishOutcome`，依 data-model.md；重用 `graph/state.Citation`
- [X] T005 建 `tests/fixtures/notification_events.json` — ~10 筆樣本：N1–N7 各類、1 筆誘導買進紅隊樣本、1 筆重複 `event_id`、1 筆缺欄位壞事件、2 筆同 `(ticker,type,日)` info 供 digest、1 筆 internal 營運事件

## Phase 3: User Story 1 — 統一通知管線與收件匣（P1）🎯 MVP

**Goal**: 事件進 → 標準通知出 → 收件匣可讀可篩可標已讀；同 `event_id` exactly-once。
**Independent Test**: 餵一筆模擬事件，收件匣出現格式完整通知、未讀 +1；標已讀歸零；重送同 id 仍 1 則。

- [X] T006 [P] [US1] 測試先行：`tests/test_notification_inbox.py` — 未讀計數、`list()` 時間倒序、ticker/type 篩選、`mark_read` 回新實例（原件 frozen 不變）、查無 id 回 None、空收件匣未讀=0
- [X] T007 [P] [US1] 測試先行：`tests/test_notification_composer.py`（去重部分）— 同 `event_id` 第二次進來回 deduped、同 id 不同內容以第一筆為準
- [X] T008 [US1] 實作 `src/polaris/notifications/inbox.py` — `InAppInbox`（in-memory dict、`unread_count`/`list`/`mark_read`/`delivery_failures`）
- [X] T009 [US1] 實作 `src/polaris/notifications/composer.py` — `Composer.compose(event)`：`event_id` 去重（seen set）、事件→通知欄位映射（`notification_id = f"ntf-{event_id}"`、`created_at = occurred_at`、`summary` 取 body 截 100 字）
- [X] T010 [US1] 測試先行：`tests/test_notification_service.py`（US1 部分）— publish 一筆合規事件 → delivered、收件匣 1 則、欄位齊全；壞事件 dict → rejected 不拋例外；確定性：同 fixture 3 連跑收件匣相同
- [X] T011 [US1] 實作 `src/polaris/notifications/service.py` — `NotificationService.publish()` 最小管線：validate → dedupe → compose → 入收件匣（合規/訂閱閘門此階段先 pass-through 佔位，US2/US3 補）

**Checkpoint**: US1 可獨立驗收 — `pytest tests/test_notification_{model,inbox,composer,service}.py` 全綠。

## Phase 4: User Story 2 — 合規閘門（P1，與 US1 同期交付才可上線）

**Goal**: user 受眾文案必過 `compliance_agent.review()`；blocked 不派送＋自動產 internal incident；空證據不派送。
**Independent Test**: 餵紅隊誘導事件 → 收件匣無該通知、有一則 incident（alert）。

- [X] T012 [US2] 測試先行：`tests/test_notification_service.py` 加合規案例 — (a) 紅隊事件 → status=blocked、user 通知不入匣、internal incident 入匣且 severity=alert、incident 摘要不含 `BUYSELL_KEYWORDS`；(b) 中性事件 → passed；(c) internal 事件 → compliance_status=skipped；(d) user 事件 evidence=[] → rejected；(e) 不變量：匣內所有 user 通知文案皆不含關鍵字、evidence 皆非空
- [X] T013 [US2] 在 `src/polaris/notifications/service.py` 實作 Compliance Gate — 呼叫 `compliance_agent.review(f"{title}\n{summary}", client)`（client=None 走 floor）；blocked → 合成 incident 通知（固定模板，research §4）並派送 internal 路徑；加 evidence 非空檢查

**Checkpoint**: 紅線測試綠 — NFR-031 出口守住，US1+US2 = 可上線的最小整體。

## Phase 5: User Story 3 — 訂閱過濾（P2）

**Goal**: watchlist / 類型開關過濾；預設全收；alert 不可靜音。
**Independent Test**: 只追蹤 2330，餵 2330 與 2891 → 匣內只有 2330。

- [X] T014 [P] [US3] 測試先行：`tests/test_notification_subscriptions.py` — 預設全收、watchlist 過濾、`ticker=None` 通知不受 watchlist 擋、muted_types 過濾、alert 恆放行
- [X] T015 [US3] 實作 `src/polaris/notifications/subscriptions.py` — `Subscription` frozen model + `allows()`（data-model 規則 1–4）
- [X] T016 [US3] `service.py` 接上訂閱過濾（compose 之後、派送之前；不放行 → status=filtered），`tests/test_notification_service.py` 加 filtered 案例

## Phase 6: User Story 4 — 內部營運告警送 Slack（P2）

**Goal**: internal 通知另推 Slack webhook；失敗重試後降級記錄；未設定憑證即停用。
**Independent Test**: 注入 recorder transport，餵 internal 事件 → recorder 收到 payload；注入 raiser → `delivery_failures` 有記錄、不拋例外。

- [X] T017 [P] [US4] 測試先行：`tests/test_notification_channels.py` — recorder transport 收到正確 payload 形狀（contracts §payload）、暫時性錯誤經 retry 後成功（注入 no-op sleep）、用盡降級記 `delivery_failures` 不拋、`webhook_url=""` → 0 次 transport 呼叫
- [X] T018 [US4] 實作 `src/polaris/notifications/channels.py` — `Channel` Protocol、`SlackWebhookChannel(webhook_url, transport=None)`、`_urllib_transport`（stdlib）、`call_with_retry` 包裝
- [X] T019 [US4] `service.py` 接上 channel router（internal 受眾 → 所有 channels；incident 亦推），`tests/test_notification_service.py` 加 Slack 路由案例（mock transport）

## Phase 7: User Story 5 — Digest 合併（P3）

**Goal**: 同 `(ticker, type, 日)` 多則 info 合併為一則；watch/alert 不合併。
**Independent Test**: 同日 2330 三筆入庫 info 事件 → 匣內 1 則、digest_count=3、證據 3 筆。

- [X] T020 [US5] 測試先行：`tests/test_notification_composer.py` 加 digest 案例 — 3 筆同鍵 info 合併（count、evidence 累積、標題變「N 則更新」）、watch/alert 不合併、跨日不合併、去重優先於 digest（重複 id 不計入 count）
- [X] T021 [US5] `composer.py` 實作 digest 合併 + `inbox.py` 支援同 `notification_id` 替換更新；`service.py` 回 status=digested

## Phase 8: Polish & Cross-Cutting

- [X] T022 [P] 實作 `src/polaris/notifications/__main__.py` — `python -m polaris.notifications <events.json>` 讀 fixture、印收件匣與 outcome 統計（quickstart 預期輸出）；`tests/test_notification_service.py` 加 CLI smoke（subprocess 或直呼 main）
- [X] T023 [P] `src/polaris/notifications/__init__.py` 公開 API re-export（`NotificationService`、`NotificationEvent`、`InAppInbox`、`Subscription`、`SlackWebhookChannel`、`PublishOutcome`）
- [X] T024 全套件回歸：`make test` 全綠、確認 0 token / 0 外呼（無金鑰環境跑）、`graph/workflow.py` 無 diff（FR-NC-012）
- [X] T025 [P] 文件收尾：quickstart.md 預期輸出與實際對齊；docs/spec-kit/PRD_通知中心_v0.1.md 補「Phase 1 後端核心已實作（specs/002）」狀態列

## Dependencies & Execution Order

- **Phase 1 → 2 → 3**：嚴格順序（Setup → 模型/fixture → MVP 管線）。
- **US2（Phase 4）依賴 US1 的 service 骨架**；US1+US2 視為最小可上線整體（合規閘門未就位前不得對外）。
- **US3（Phase 5）/ US4（Phase 6）互相獨立**，都只依賴 US1+US2 完成的 service；可並行。
- **US5（Phase 7）依賴 US1 的 composer/inbox**，與 US3/US4 獨立。
- 標 [P] 的任務檔案不相交、可並行。

```text
Setup(T001-002) → Foundational(T003-005) → US1(T006-011) → US2(T012-013)
                                                              ├─→ US3(T014-016) ─┐
                                                              ├─→ US4(T017-019) ─┼─→ Polish(T022-025)
                                                              └─→ US5(T020-021) ─┘
```

## Implementation Strategy

- **MVP = US1 + US2**（管線＋合規閘門；缺一不可對外）。
- 每個 user story 完成即跑該 story 測試 + 全套件回歸，綠了才進下一 phase（TDD：先寫測試看它紅，再實作轉綠）。
- 任務總數 25；US1×6、US2×2、US3×3、US4×3、US5×2、Setup/Foundational×5、Polish×4。
