# PRD：Polaris Desk 通知中心（Notification Center）

**Version**: v0.1（Draft，發想稿）
**Created**: 2026-06-10
**Status**: Draft — 待 PM (R1) + Tech Lead (R2) review
**實作進度**: Phase 1 後端核心已實作（[specs/002-notification-center](../../specs/002-notification-center/spec.md)，2026-06-10）— 統一管線、合規閘門、訂閱過濾、收件匣、Slack channel、digest；待接真實生產者（R3/R4/R5）與前端（R7）
**時程定位**: **Demo（Day 28）後 roadmap**。Demo 期內僅交付既有規格的 Alert Inbox（R7 W2 D7）＋ Watchdog（R3 W3），本 PRD 規劃其後的演進。
**上位文件**: `.specify/memory/constitution.md`（憲法 v2.0.0）、`00_Polaris-Desk_專題_spec.md`、`R3_Agent_spec.md`、`R7_Demo全端_spec.md`

---

## 1. 一句話

> 把現在「只裝 Watchdog 合規警示」的 Alert Inbox，升級成 Polaris Desk 唯一的通知出口——**分析師訂閱的公司有事、研究任務跑完、資料有更新、系統有狀況，都從同一個地方、經同一道合規閘門送出去**。

## 2. 背景與動機

### 2.1 現況

Demo 規格中已有一條「事件 → 警示」的線：

```
MOPS 公告（mock → R4 真爬蟲）
   └→ Watchdog Agent（R3，事件驅動合規初篩）
        └→ WatchdogAlert JSON（過 compliance_agent.review，0 買賣建議）
             └→ Alert Inbox（R7 前端收件匣）
```

這條線只處理**一種**通知（合規警示），但系統裡還有許多「使用者離開畫面後才發生、卻需要被告知」的事件：Deep Research 跑完、訂閱公司的新法說稿入庫、來源矛盾被偵測到、ingestion 失敗、eval 掉分、token 預算逼近上限……目前這些事件要嘛沒人接、要嘛散落在 log / CI / 群組訊息裡。

### 2.2 名詞定義：Watchdog、Alert Inbox、通知中心的關係

> 本節同時回答「**為什麼 Watchdog 的輸出要放在 Alert Inbox**」，供對內說明使用。

| 名詞 | 是什麼 | 角色 |
|---|---|---|
| **Watchdog Agent** | 事件驅動的合規初篩 agent（R3）。MOPS 一有新公告就被觸發，產出「合規判斷摘要 + 證據引用」，結尾必過 `compliance_agent.review()`（NFR-031） | **生產者**（產警示） |
| **Alert Inbox** | 前端的警示收件匣（R7）。渲染 `WatchdogAlert` JSON：ticker、摘要、severity、證據引用 | **消費介面**（收警示） |
| **通知中心** | Alert Inbox 的**超集**。Watchdog 警示只是其中一類通知；再納入研究任務、資料更新、系統營運等其他通知類型，並擴充到多管道 | **平台**（本 PRD 範圍） |

**為什麼 Watchdog 放在 Alert Inbox（而不是塞進對話、或各自做 UI）**：

1. **時序錯位 — Watchdog 是非同步的**：對話 UI 是「使用者問 → 系統答」的同步模式；Watchdog 是「MOPS 半夜發公告 → agent 自己被事件觸發」的非同步模式，**產出警示時根本沒有對話 session 可以回**。非同步產出需要一個持久化的承接面，那就是收件匣。
2. **使用情境是 triage（分流），不是 conversation（對話）**：分析師面對警示要的是「掃一眼 severity → 挑重要的展開 → 點證據驗證」，這是收件匣互動（列表、已讀、嚴重度排序），不是聊天互動。
3. **解耦 agent 與 UI，雙方可平行開發**：R3 與 R7 以 `WatchdogAlert` JSON 契約為界（R3 開工指南 §3），R7 用 mock JSON 先做 UI、R3 用 mock 事件先做 agent，互不阻塞——這正是 W2/W3 排程能各自推進的關鍵。
4. **合規上需要單一出口**：憲法原則 I 要求「所有對外輸出」零買賣建議。把警示集中到一個介面，等於只有一個出口要守——每則警示在進收件匣前都已過 `compliance_agent.review()`，前端再過一次 UI 層檢查（三層防線的第三層）。出口越分散，越容易漏。

通知中心延續同一套邏輯：**所有**非同步產出（不只 Watchdog）共用同一個承接面、同一道合規閘門、同一份 JSON 契約模式。

## 3. 目標與非目標

### 目標

- **G1**：分析師不用守在畫面前——訂閱的公司有事、長任務跑完，系統主動告知。
- **G2**：所有通知共用一條「組裝 → 合規 → 派送」管線，合規出口唯一（NFR-031 三層防線不破口）。
- **G3**：內部團隊（R1–R7）的營運訊號（ingestion、eval、預算）也走同一條管線，不再散落群組。
- **G4**：每則通知都帶來源引用，點了能跳回原文（憲法原則 II 延伸到通知）。

### 非目標

- ❌ 不做任何形式的投資訊號 / 買賣提示推播（NFR-031 紅線；連「股價異動提醒」都先不做，見 §10 開放問題 OQ-2）。
- ❌ 不做通知的雙向互動（在 LINE 裡直接問答）——管道只送「摘要 + 回 app 的連結」。
- ❌ Demo（Day 28）前不動工。既有 Alert Inbox / Watchdog 規格與排程**完全不變**。

## 4. 受眾與通知類型（通知什麼）

兩類受眾、七類通知。每類標：受眾、觸發來源、預設嚴重度、預設管道。

### 4.1 終端使用者（分析師）

| # | 通知類型 | 觸發 | severity | 範例文案（皆過合規閘門） |
|---|---|---|---|---|
| N1 | **合規 / 重大訊息警示**（= 現有 Watchdog 線） | MOPS 新公告 → Watchdog 初篩 | info / watch / alert | 「2330 發布重大訊息：董事會決議⋯（摘要）。證據：MOPS 2026-03-15」 |
| N2 | **追蹤清單事件**（watchlist） | 訂閱的 ticker 有新法說會公告、財報發布、法說簡報上線 | info | 「您追蹤的 2891 已公告 Q2 法說會（6/25 14:00）」 |
| N3 | **新資料入庫** | 訂閱公司的法說稿 / 逐字稿完成 ingestion 入 `polaris_core` | info | 「2330 2026Q1 法說逐字稿已入庫，現在可以問了」 |
| N4 | **研究任務完成** | Deep Research（ReAct loop）跑完 | info | 「您的深度研究『鴻海各事業群營收拆解』已完成，點此檢視報告」 |
| N5 | **來源矛盾偵測** | 新入庫資料與使用者近期查過的結論矛盾（grounding 原則：標矛盾、不下結論） | watch | 「新入庫的 2330 Q1 財報數字與 3/2 新聞報導不一致：A 來源稱⋯、B 來源稱⋯」 |

### 4.2 內部團隊（R1–R7 營運）

| # | 通知類型 | 觸發 | severity | 範例 |
|---|---|---|---|---|
| N6 | **管線健康** | ingestion 失敗 / 成功批次報告（R4）、eval 分數跌破門檻（R5，Context Precision < 0.85 等） | watch / alert | 「nightly eval：Faithfulness 0.87 < 0.90，G3 門檻不過」 |
| N7 | **成本與合規事故** | token 花費逼近預算（~$400 上限的 80%）；compliance 攔截事件（每次 `blocked` 都要記 incident） | alert | 「本週 token 花費 $310 / $400（78%）」、「Watchdog 攔截 1 則買賣建議輸出，incident #12」 |

> N7 的 compliance incident 通知直接支撐憲法原則 I 的「違反處置：寫 incident report + 補測試」——事故發生當下就推給 R1/R2/R6，而不是事後翻 log。

## 5. 管道策略（如何送）

### 5.1 管道建議與分期

| 管道 | 適合 | 建議 | 理由 |
|---|---|---|---|
| **In-app 鈴鐺 + 收件匣** | 全部通知類型 | **Phase 1 必做**（基底） | Alert Inbox 既有元件直接演進；所有管道的「詳情頁」都連回這裡（引用跳轉只能在 app 內做到 100%） |
| **Slack（內部）** | N6/N7 營運通知 | **Phase 1 必做** | Incoming webhook 零成本、團隊已在用群組溝通；先服務自己人，管線跑熟再對外 |
| **Email 每日摘要** | N1–N5 彙整 | **Phase 2** | 投研節奏適合「每天早上一封 digest」；成本低（SES/SendGrid 免費額度內）、不需要使用者裝任何東西 |
| **Email 即時信** | severity = alert 的 N1/N5 | Phase 2（與 digest 同套基建） | 重大事件不等 digest |
| **LINE 推播** | N1/N2 即時推 | **Phase 3** | 台灣使用者黏著度最高；但 **LINE Notify 已於 2025/3 終止服務**，需走 LINE Messaging API（官方帳號 + 訊息量計費），有額外的帳號申請與每月成本——價值高、成本也高，放最後 |
| ~~Slack（對外）~~ | — | 不做 | 台灣個人投研使用者幾乎不用 Slack 收個人通知 |

### 5.2 派送原則

- **嚴重度決定即時性**：`alert` → 即時推（所有已開啟管道）；`watch` → in-app 即時 + 進 digest；`info` → in-app + digest only。
- **Digest 合併**：同一 ticker 同日多則 info 通知合併成一則（「2330 今日 3 則更新」），防通知疲勞。
- **每則通知必含**：摘要（≤ 100 字）、來源引用（source_id + 可跳轉連結）、severity、回 app 詳情頁的 deep link。
- **外送管道（Email/LINE）只送摘要**，全文與引用跳轉一律回 app——控制外洩面、也讓引用接地（原則 II）保持可驗證。

## 6. 功能需求

- **FR-NC-001**：系統 MUST 定義統一通知 schema `Notification`（擴充自 `WatchdogAlert`）：`notification_id`、`type (N1–N7)`、`audience (user|internal)`、`ticker?`、`title`、`summary`、`severity (info|watch|alert)`、`evidence: list[Citation]`、`deep_link`、`created_at`、`read_at?`。
- **FR-NC-002**：所有通知產生器（Watchdog、ingestion、Deep Research、eval、budget monitor）MUST 經由同一個 Notification Service 派送，不得自行直送任何管道。
- **FR-NC-003**：每則對外通知（audience=user）的 `title` + `summary` MUST 通過 `compliance_agent.review()`；`blocked` 的通知不得派送並 MUST 產生 N7 incident 通知給內部。
- **FR-NC-004**：使用者 MUST 能訂閱 / 退訂：(a) 個別 ticker（watchlist）、(b) 通知類型 N1–N5、(c) 管道（per-channel on/off）。預設只開 in-app。
- **FR-NC-005**：in-app 通知中心 MUST 支援：未讀計數（鈴鐺 badge）、列表（severity + 時間排序）、已讀標記、依 ticker / 類型篩選、點引用跳轉原文（沿用 Citation Tracer）。
- **FR-NC-006**：系統 MUST 對同一 `(ticker, type, 日)` 的 info 通知做 digest 合併；MUST 對相同 `event_id` 去重（exactly-once 到收件匣）。
- **FR-NC-007**：內部通知（N6/N7）MUST 可送 Slack webhook；webhook URL 屬金鑰，只放 `.env` / Secret Manager（原則 III）。
- **FR-NC-008**：Email / LINE 派送 MUST 帶退訂連結，且派送失敗 MUST 重試（沿用 `retry.py` 模式）後降級為 in-app only，不得無聲丟失。

## 7. 非功能需求

- **NFR-NC-1（合規，繼承 NFR-031）**：紅隊測試含「誘導性公告 → 通知文案」案例，通知文案中買賣建議出現次數 = **0**。LINE/Email 屬對外輸出，與新聞卡同層級管制。
- **NFR-NC-2（接地）**：audience=user 的通知 `evidence` 不得為空——**沒有來源的事件不發通知**。
- **NFR-NC-3（延遲）**：事件發生 → in-app 可見 ≤ 60 秒（demo 級）；外送管道 ≤ 5 分鐘。
- **NFR-NC-4（金鑰）**：所有管道憑證（SMTP、LINE channel token、Slack webhook）只放 `.env` / Secret Manager，永不 commit。
- **NFR-NC-5（成本）**：LINE Messaging API 月訊息量設上限與預算警報；超量自動降級為 Email/in-app。

## 8. 架構概要

```
事件來源（生產者）                      Notification Service                        介面（消費者）
─────────────────                ────────────────────────────              ─────────────────
Watchdog Agent (N1)  ──┐                                                  ┌─→ In-app 通知中心（鈴鐺+收件匣）
MOPS/watchlist (N2)  ──┤        ┌──────────┐  ┌──────────┐  ┌─────────┐   ├─→ Email（digest / 即時）
Ingestion 完成 (N3)   ──┼──事件─→│ Composer │─→│Compliance│─→│ Channel │───┼─→ LINE Messaging API
Deep Research (N4)   ──┤        │去重/合併/ │  │  Gate    │  │ Router  │   └─→ Slack webhook（內部）
矛盾偵測 (N5)         ──┤        │嚴重度判定 │  │(review())│  │(訂閱過濾)│
Eval/Budget (N6/N7)  ──┘        └──────────┘  └──────────┘  └─────────┘
                                       ↑ 統一 Notification schema（FR-NC-001）
```

設計原則：

- **生產者只發事件、不碰管道**（FR-NC-002）——新增通知類型 = 新增一個生產者，管線不改。
- **Compliance Gate 是唯一出口**，跟主 workflow 的 Compliance 節點同一套 `compliance_agent`，規則只在一處維護（R6）。
- **沿用既有 seam 模式**：管道 adapter 採注入式（mock → 真實 API），與 Deep Research `search` seam、Watchdog `event` seam 同套路，CI 全程 token-free。
- 儲存：通知記錄入 BigQuery（沿用 `polaris_core` 旁的營運 dataset；schema 變更走 SOP §7 PR）。

## 9. 分期 Roadmap

| Phase | 內容 | 前置 |
|---|---|---|
| **Phase 0**（Demo 內，既有規格，不在本 PRD 範圍） | Watchdog → Alert Inbox（mock 事件、in-app only） | R3 W3、R7 W2 D7 |
| **Phase 1**（Demo 後第 1–2 週） | 統一 `Notification` schema；Alert Inbox 改名升級為通知中心（N1 遷入）；加 N3/N4 兩個低風險生產者；watchlist 訂閱；內部 Slack webhook（N6/N7） | Demo 結束、R4 真 MOPS 爬蟲 |
| **Phase 2**（第 3–4 週） | Email digest + 即時信；N2 watchlist 事件；digest 合併與去重完工；通知偏好設定頁 | Phase 1 |
| **Phase 3**（之後，視留存數據決定） | LINE Messaging API 推播；N5 矛盾偵測（需要「使用者近期查詢」的歷史脈絡，技術上最難）；quiet hours / 頻率上限 | Phase 2 + 預算核可 |

## 10. 成功指標

- **SC-NC-1**：通知文案紅隊測試買賣建議 = 0（含 LINE/Email 渠道抽驗）。
- **SC-NC-2**：audience=user 通知的引用覆蓋率 = 100%、引用跳轉正確率 = 100%。
- **SC-NC-3**：事件 → in-app 延遲 p95 ≤ 60 秒；派送丟失率 = 0（失敗有降級記錄）。
- **SC-NC-4**：（採用指標）Phase 2 結束時，活躍使用者 watchlist 訂閱率 ≥ 50%、digest 開信率 ≥ 30%。
- **SC-NC-5**：內部告警有效性：ingestion 失敗 / eval 掉分從發生到團隊知悉 ≤ 5 分鐘（取代「翻 log 才發現」）。

## 11. 風險與開放問題

| 編號 | 風險 / 待決 | 影響 | 處置建議 | owner |
|---|---|---|---|---|
| RK-1 | 通知疲勞：MOPS 公告量大，全推會被關通知 | 留存 | digest 合併 + 預設保守（只開 in-app）+ severity 門檻 | R1 |
| RK-2 | LINE Messaging API 成本與官方帳號審核時程 | Phase 3 延期 | 提前申請；月訊息量上限 + 預算警報（NFR-NC-5） | R1/R2 |
| RK-3 | 通知文案是 LLM 產出 → 幻覺風險外溢到推播 | 合規/信任 | 文案模板化（事件欄位填空優先，LLM 摘要為輔）+ 必過 compliance gate | R3/R6 |
| OQ-1 | 通知記錄存哪：BigQuery 營運 dataset vs 另起 OLTP（Cloud SQL）？ | 架構 | Phase 1 用 BigQuery 先跑，量大再議 | R2 |
| OQ-2 | 「股價 / 財務指標異動提醒」要不要做？描述性數字變動不算買賣建議，但貼著紅線 | 合規 | 先不做；若做需 R6 出規則 + 紅隊專測，PM/TL 雙簽 | R1+R2+R6 |
| OQ-3 | 多使用者帳號體系（訂閱需要 user identity）目前不存在 | Phase 1 前置 | Demo 後與整體產品化一起決定（單機單人 → 多人） | R1/R2 |

---

> **下一步**：R1 review 本 draft → 確認 Phase 1 範圍 → `/speckit-specify` 起正式 feature spec。
