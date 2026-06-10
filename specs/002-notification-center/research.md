# Phase 0 Research: 通知中心 Phase 1 後端核心

> 4 個技術選擇。每項：Decision / Rationale / Alternatives considered。

## 1. 通知時間戳來源

- **Decision**: `Notification.created_at` 一律取自事件的 `occurred_at` 欄位；管線內**不呼叫** `datetime.now()`。
- **Rationale**: SC-NC-004 要求同一組事件樣本重跑 3 次收件匣完全一致。時間戳若取牆鐘，snapshot 式比對直接破功；事件時間也比處理時間更貼近使用者心智（「事情何時發生」）。
- **Alternatives considered**:
  - 牆鐘 `now()` ＋測試 freeze-time 套件：引入新依賴、且 fixture 比對要到處 mock，反而複雜。
  - 雙欄位（occurred_at + processed_at）：Phase 1 無人消費 processed_at，YAGNI 砍掉；Phase 2 持久化時再加。

## 2. 去重與 digest 合併的先後與鍵

- **Decision**: 管線順序＝**先去重、後 digest**。去重鍵＝`event_id`（exactly-once，重複丟棄並記錄）；digest 鍵＝`(ticker, type, occurred_at.date())`，僅 `severity=info` 參與合併，合併進既有通知（`digest_count += 1`、evidence append）。
- **Rationale**: 兩個機制解的是不同問題——去重防「同一事件重送」（FR-NC-005），digest 防「不同事件太吵」（FR-NC-010）。同鍵混做會讓「重送的事件」誤入 digest 計數，破壞 SC-NC-003 的 100% 正確率。
- **Alternatives considered**:
  - 只做去重、digest 留 Phase 2：US5 是 P3 沒錯，但 digest 邏輯 20 行內可確定性實現，且 PRD RK-1（通知疲勞）點名它是頭號留存風險，做掉。
  - 以內容 hash 去重：事件已有唯一 `event_id`（R3 Watchdog 契約既有欄位），內容 hash 多餘且會把「同 id 不同內容」誤判為新事件——edge case 已定義為「以第一筆為準」。

## 3. Slack 派送的 transport seam

- **Decision**: `SlackWebhookChannel(webhook_url, transport=None)`；`transport: Callable[[str, dict], None]`。預設實作 `_urllib_transport` 用 stdlib `urllib.request` POST JSON；測試一律注入 recorder / 拋錯 stub。`webhook_url` 為空 → channel 自我停用（`send()` no-op），管線照常。外呼包 `call_with_retry`（暫時性錯誤重試），用盡後記入 `delivery_failures`、不拋出（FR-NC-009 不無聲丟失、也不弄垮管線）。
- **Rationale**: 與 Deep Research `search` seam、Watchdog `event` seam 同套路——注入點讓 CI 0 真實外呼（憲法 III + SC-NC-005），且不引入 `slack_sdk` 新依賴（incoming webhook 就是一個 HTTP POST）。
- **Alternatives considered**:
  - `slack_sdk` 套件：為一個 POST 加一顆依賴，違反「複雜度需被正當化」。
  - `requests`：repo 未列為直接依賴，stdlib 即可。
  - 失敗時拋例外給呼叫端：生產者不該因「通知送不出去」而失敗——通知是旁路（side channel），降級為僅收件匣才是對的語意。

## 4. 合規 incident 通知的形狀

- **Decision**: 事件被攔截（`blocked`）時，service 自動合成一則 `type="compliance_incident"`、`audience="internal"`、`severity="alert"` 的通知：標題含被攔事件 `event_id`，摘要為**固定模板**（不含被攔原文），evidence 沿用原事件的 evidence（可為空——internal 不受 FR-NC-004 約束）。incident 通知本身不再過攔截改寫（internal 路徑），但仍走訂閱過濾之外的強制派送（alert 不可靜音）。
- **Rationale**: 憲法 I 的違反處置要求「寫 incident report」；摘要用固定模板而非引用被攔文案，避免違規字眼經 incident 通知二次外溢（同 `SAFE_MESSAGE` 不含關鍵字的設計）。
- **Alternatives considered**:
  - incident 摘要附被攔原文方便除錯：違規文案會再次出現在通知面，紅線風險；除錯走原始事件記錄即可。
  - 攔截即拋例外：合規攔截是**正常營運事件**不是程式錯誤；拋例外會讓生產者誤判管線壞掉。

## 既有介面盤點（直接重用，零改動）

| 介面 | 位置 | 用法 |
|---|---|---|
| `review(draft, client) -> (answer, status)` | `graph/nodes/compliance_agent.py` | 合規閘門；`client=None` 走 6 關鍵字 floor（CI 路徑），fail-to-floor 語意內建 |
| `Citation` | `graph/state.py` | 事件/通知的 evidence 型別，origin 用既有 `"news"` / `"stub"` |
| `call_with_retry(fn, *, sleep=...)` | `retry.py` | Slack 外呼重試；測試注入 no-op sleep |
| `Settings` | `config.py` | 新增 `slack_webhook_url: str = ""`（env：`SLACK_WEBHOOK_URL`，只進 `.env`） |

**所有 NEEDS CLARIFICATION：無**（上位決策已由 PRD v0.1 + 使用者核可拍板）。
