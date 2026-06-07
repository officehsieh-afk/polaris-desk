# Polaris Desk — UX 設計規格：可點擊原型（Clickable Prototype）

- **日期**：2026-06-05
- **作者**：R2（Tech Lead）協助 R7（Demo & 全端）
- **狀態**：草案（待 PM/R7 review）
- **產物**：靜態可點擊 HTML 原型 + 本規格
- **對應**：R7 spec（SC-004/005/007）、`docs/R7_frontend_開工指南.md`、demo 場景 US1–US4 + Watchdog

---

## 1. 目標與範圍

### 1.1 目標
為 Polaris Desk 產出一份**可點擊的前端原型**，達成三個用途：
1. **Demo 用**：4 個展示場景（US1–US4）+ Watchdog 合規哨兵，能在瀏覽器點擊走完。
2. **R7 實作參考**：原型的 mock JSON **一字不差**對齊現有 thin API 契約（`/ask`、`/research`、Watchdog Alert），R7 接真 API 時零改欄位。
3. **斷網備援**：純靜態、無後端、無 build step，雙擊 `index.html` 即開（憲法 V 離線備援）。

### 1.2 範圍內
- 4 個主畫面 + 1 個來源抽屜（drawer），涵蓋 R7 開工指南列的 **5 個 DoD 畫面**。
- Clean light SaaS 視覺風格（見 §3）。
- Mock 資料以**真實 API 回應形狀**驅動（見 §6）。
- RWD（手機不跑版，SC-005）。

### 1.3 範圍外（明確不做）
- **真後端串接**：原型只讀本地 mock JSON；接真 API 是 R7 後續工作（換資料來源一行）。
- **真 PDF 引擎**：「匯出 PDF」用瀏覽器 `window.print()` + print CSS，不引第三方 PDF 套件。
- **登入/權限/多租戶**：demo 不需要。
- **US3 多模態（ColPali）為 P2／可砍**：原型會畫出來但以旗標標示，砍掉是改一個 flag（見 §5.5、§8）。

---

## 2. 使用者與場景對應

兩種角色（雙場景價值主張）：**投研**（投顧/券商研究/家辦）與 **法遵**（IR/法務）。頂欄有 投研 ⇄ 法遵 切換，只影響首頁快速場景卡與哨兵的強調，不分流資料。

| 場景 | 說明 | 走哪個畫面 | API |
|---|---|---|---|
| **US1 單一公司投研摘要**（P1） | 問一家公司一季重點 | 主控台 → 摘要卡 | `POST /ask` |
| **US2 同業比較**（P1） | 兩家公司並排比較（台積電 vs 聯發科 毛利率） | 主控台 → 比較卡（雙欄表） | `POST /ask` |
| **US3 多模態圖表**（P2/可砍） | 圖表頁檢索（ColPali） | 來源抽屜 → 頁面圖 + 框選區域 | `POST /ask` + citation |
| **US4 跨產業營收拆解**（P1） | 部門營收拆解（鴻海/聯發科，**非台積電**單一部門） | 主控台 → 拆解卡（部門表/長條） | `POST /ask` |
| **Watchdog 合規哨兵**（跨場景亮點） | 事件驅動合規警示 | 合規哨兵 → Alert Inbox | Watchdog Alert（mock） |
| **Deep Research**（agentic 亮點） | 多步 ReAct 推理 | 深度研究 → ReAct 時間軸 | `POST /research` |

---

## 3. 視覺系統（Clean Light SaaS）

對齊「細部專題規劃簡報（給指導老師）」的創新風格。

| Token | 值 | 用途 |
|---|---|---|
| `--bg` | `#F5F8FC` | 頁底 |
| `--surface` | `#FFFFFF` | 卡片 |
| `--primary`（北辰藍） | `#2A5BD7` | 主色、連結、tab active |
| `--gold`（北辰金） | `#D99A33` | 節制點綴、✦ 四角星 motif |
| `--ok`（合規通過） | `#1F9D6B` | `passed` badge |
| `--block`（合規攔阻） | `#D9533A` | `blocked` badge |
| `--ink` | `#1A2233` | 主文字 |
| `--muted` | `#5B6678` | 次要文字/metadata |
| 字體 | PingFang TC / Noto Sans TC（UI）；**JetBrains Mono**（數字、`source_id`、股號） | |
| 圓角 | 卡片 14px、chip 999px | |
| 陰影 | 柔和 `0 1px 3px rgba(20,34,51,.08)` | |

**✦ 四角星 motif**：wordmark 前綴、loading 動畫、空狀態裝飾。節制使用金色（重點不淹沒藍）。

---

## 4. 畫面清單與導覽（V2 三欄工作區）

採用團隊 V2 參考圖（`05_Demo資料/研究助理_AI_詢問介面_V2.png`）的**三欄工作區**：左側深色導覽列＋中央 Research Canvas＋右側欄三面板（模型推考紀錄／預測系統警示／引用追蹤）。頂欄含輸入框、模型選單、**投研⇄法遵 persona 切換**與模式選單。來源抽屜可從任何畫面被 citation chip／⤢ 觸發。對應 R7 五個 DoD 畫面已標註。

```
┌ 左導覽 ───┬ 頂欄：✦ [🔍輸入問題…] 模型▾   投研⇄法遵  模式▾  🔔 ───────────┐
│ 首頁       │ 中央 Research Canvas             │ 右側欄                       │
│ 研究助理   │  問句 → 答案卡（引用＋合規）     │  模型推考紀錄（trace/ReAct） │
│ 公司投研   │  → 來源頁檢視                    │  預測系統警示（Watchdog）    │
│ 跨產業分析 │  （主控台場景累積成對話串）      │  引用追蹤                    │
│ 同業比較   │                                 │                             │
│ 合規哨兵   │                                 │                             │
└───────────┴─────────────────────────────────┴─────────────────────────────┘
```

| Route | 畫面 | 對應 R7 DoD 畫面 | API 形狀 |
|---|---|---|---|
| `#/home` | 首頁／空狀態（tagline + 6 場景卡，依 persona 強調） | — | — |
| `#/us1` `#/us2` `#/us4` | 研究主控台（答案卡對話串，三種變體） | #1 對話+引用 | `/ask` |
| `#/blocked` | 合規攔阻示範（SAFE_MESSAGE） | #1 | `/ask` |
| `#/research` | 深度研究（ReAct） | #5 ReAct trace | `/research` |
| `#/watchdog` | 合規哨兵（Alert Inbox） | #4 Alert Inbox | Watchdog Alert |
| `#/report` | 報告檢視 + 匯出 PDF | #3 Report Viewer | 由 `/ask` 結果組版 |
| `#/database` `#/history` | 資料庫／歷史紀錄（輔助畫面） | — | — |
| （drawer）來源檢視 | citation 點擊跳轉 | #2 Citation Tracer | citation 物件 |

導覽：左導覽列切換主畫面（hash router）；頂欄 **投研⇄法遵** persona 切換影響首頁卡片強調與哨兵；答案卡的「產生報告」按鈕導去 `#/report`；任一 `[n]` chip 或 ⤢ 開來源抽屜（跳轉正確率須 100%，SC-007）。主控台場景（US1/US2/US4/blocked）以**答案卡對話串**累積，可「清除對話」。

---

## 5. 各畫面細部

### 5.1 研究主控台 `#/console`（預設）
空狀態即首頁：產品 tagline + 6 張快速場景卡（US1/US2/US4 + 深度研究 + 合規哨兵 + 合規攔阻；依 persona 重新排序強調）。送出問題後，主區是**答案卡對話串**（場景累積、可「清除對話」），右側是 Agent 工作軌跡。Loading 以 5 節點（planner→…→compliance）逐一亮起呈現。

```
┌─ ✦ Polaris Desk ──────────── 🔍 ───── 主控台·深度研究·合規哨兵 ── 投研⇄法遵 ┐
├──────────────────────────────────────────────┬───────────────────────────┤
│  ❯ 台積電 2024Q3 毛利率與重點？               │  Agent 工作軌跡            │
│  ╭── 答案 ──────────────────────────────────╮ │  ① planner    ok   12 ms  │
│  │ 2024Q3 毛利率 57.8%，季增 4.6pp…[1]      │ │  ② retriever  ok 1,140 ms │
│  │ 主因 3nm 放量與匯率…[2]                   │ │  ③ calculator ok  220 ms  │
│  │  〔合規通過 ✓〕                          │ │  ④ writer     ok  910 ms  │
│  ╰──────────────────────────────────────────╯ │  ⑤ compliance ok   45 ms  │
│  來源 [1] 法說逐字稿 p.4  [2] 財報附註 p.12    │  ─────────────────────    │
│  [ 產生報告 ]                                  │  狀態 passed              │
│  ┌ 快速場景 ─────────────────────────────────┐ │                          │
│  │ US1 單一公司摘要  US2 同業比較             │ │                          │
│  │ US4 跨產業營收    ⚑ 看 Watchdog 警示       │ │                          │
│  └────────────────────────────────────────────┘ │                         │
└──────────────────────────────────────────────┴───────────────────────────┘
```

**答案卡三種變體**（同一 `/ask` 形狀，不同排版）：
- **US1 摘要卡**：純文字答案 + 行內 `[n]` chip + 合規 badge。
- **US2 比較卡**：雙欄表（台積電｜聯發科），列＝毛利率 by 季；每格帶 `[n]`。
- **US4 拆解卡**：部門營收表/長條（鴻海/聯發科部門）；每列帶 `[n]`。

**合規攔阻 demo**（NFR-031 亮點）：輸入「該不該買台積電？」→ fixture 回 `compliance_status: "blocked"` → 卡片不顯示答案，改顯示 **SAFE_MESSAGE**（「本系統僅提供事實與證據，不提供買賣建議」）+ 攔阻 badge。這是刻意安排的 demo 時刻。

**Agent 工作軌跡**：固定 5 節點 `planner → retriever → calculator → writer → compliance`，逐節點 `status`（ok/error/skipped）+ `elapsed_ms` 格式化為毫秒。底部顯示整體 `compliance_status`。

### 5.2 深度研究 `#/research`
垂直 ReAct 時間軸；右側證據累積到 ≥3；底部最終結論過合規閘。

```
❯ 比較台積電與聯發科最近兩季毛利率變化            證據 (evidence)  3 筆 ✓≥3
│ ① 💭 thought  需要兩家近兩季毛利率…             [1] 2330 法說 Q3
│    🔧 action  search「台積電 毛利率 2024Q3」     [2] 2454 法說 Q3
│    👁 observation  命中…                          [3] 2330 財報 Q2
│ ② 💭 thought  還缺聯發科 Q2…                     ───────────────
│    🔧 action  search「聯發科 毛利率 2024Q2」     狀態 answered
│    👁 observation  命中…                          迴圈 4 步 ✓≤6
│ … finish →
╰─ 最終結論（逐點，句句附（來源：sid））  〔合規通過 ✓〕
```

- 每步顯示 `thought / action / action_input / observation`（`ReActStep` 真欄位）。
- **保證徽章**：`迴圈 = react_steps.length`（≤6）、`證據 = evidence.length`（≥3）。
  ⚠️ 真 `/research` 回應**不含** `iterations` 欄位 → 迴圈數由 `react_steps.length` 推得（見 §6.2）。
- 最終結論逐點、每點帶 `（來源：sid）`（對齊 D16 `is_fully_traceable`）。

### 5.3 合規哨兵 `#/watchdog`（Alert Inbox）
左清單、右詳情。事件 → Watchdog 判定 → 接地理由 → 建議動作。

```
⚑ 合規哨兵                          詳情：鴻海 重訊 — 疑似選擇性揭露
├ 🔴 alert  鴻海   選擇性揭露?  2h │  事件 event_id  mops-2317-…-001
├ 🟠 watch  台達電 前瞻措辭     5h │  Watchdog 摘要  summary（0 買賣建議）
├ 🔵 info   台積電 已澄清       1d │  證據  evidence[]（接地引用 [1][2]）
│                                 │  〔合規攔阻 ⛔〕標記，非買賣建議
```

- `severity` 上色：`alert`🔴、`watch`🟠、`info`🔵。
- `compliance_status: blocked` 標紅；`summary` 永不含買賣建議（NFR-031）。
- ⚠️ Watchdog **尚無真 endpoint**（api.py 未實作 `GET /alerts`）→ 原型純 mock；之後由 R3/R2 補（見 §8 依賴）。

### 5.4 報告檢視 `#/report` + 匯出 PDF
把一筆 `/ask` 結果排成完整報告頁：標題 + 問題 + 答案 + 來源清單 + 合規聲明頁尾。「匯出 PDF」= `window.print()` + print CSS（A4、隱藏頂欄/側欄）。

### 5.5 來源檢視抽屜（Citation Tracer）
任一 `[n]` chip 點擊 → 抽屜滑入（跳轉正確率 100%，SC-007）。

- **文字來源**：顯示 `snippet` 高亮 + 由 `source_id` 推得的 metadata（doc_type/company/period/page，見 §6.4）。
- **US3 多模態（ColPali，P2/可砍）**：`origin: "colpali"` 時顯示**頁面圖**並框選相關區域。以 `data-feature="colpali"` 標示；砍掉＝隱藏該 origin 的圖、退回文字卡。

---

## 6. 資料契約與 Mock（核心）

所有 fixture **一字不差**對齊現有程式碼真實輸出。欄位來源：`src/polaris/api.py`、`src/polaris/graph/state.py`、`deep_research/state.py`、R7 開工指南 §2。

### 6.1 `/ask` 回應（主控台 / 報告）
```jsonc
{
  "answer": "……（已過合規）",
  "compliance_status": "passed",          // passed | blocked | unknown
  "citations": [
    { "source_id": "stub-2330-2024Q3-transcript-p4", "snippet": "…", "origin": "stub" }
    // origin: stub|bm25|embedding|colpali|rerank|news
  ],
  "trace": [
    { "node_name": "planner", "status": "ok", "elapsed_ms": 12,
      "input_keys": ["query"], "output_keys": ["plan","period"], "error_message": null }
    // node_name 依序：planner, retriever, calculator, writer, compliance
    // status: ok | error | skipped；error 時 error_message 非空
  ]
}
```

### 6.2 `/research` 回應（深度研究）
```jsonc
{
  "final_answer": "- 論點…（來源：sid）",
  "evidence": [ { "source_id": "…", "snippet": "…", "origin": "stub" } ],  // ≥3
  "react_steps": [
    { "thought": "需要毛利率資料", "action": "search",
      "action_input": "台積電 毛利率", "observation": "取得引用：sid1" }
  ],
  "status": "answered",                    // answered | exhausted
  "compliance_status": "passed"
}
// 注意：實際 ResearchResponse 不含 iterations/question → 迴圈數 = react_steps.length
```

### 6.3 Watchdog Alert（合規哨兵，mock-only）
```jsonc
{
  "event_id": "mops-2317-20260315-001",
  "stock_id": "2317",
  "summary": "事件合規判斷摘要（0 買賣建議）",
  "compliance_status": "passed",           // passed | blocked
  "evidence": [ { "source_id": "mops-2317-…", "snippet": "…", "origin": "news" } ],
  "severity": "alert"                       // info | watch | alert
}
```

### 6.4 `source_id` 命名慣例（mock 專用，供抽屜推 metadata）
真 `Citation` **只有** `source_id/snippet/origin`，無結構化欄位。為讓來源抽屜顯示 doc_type/company/period/page，mock 的 `source_id` 採可解析格式：

```
<prefix>-<stock_id>-<period>-<doc_type>-p<page>
例：stub-2330-2024Q3-transcript-p4
    stub-2454-2024Q2-financials-p12
    mops-2317-20260315-news
```

抽屜以 `app.js` 解析此字串還原 metadata（UI 標示「由 source_id 推得」）。**接真 API 時**：若後端 `source_id` 非此格式，R7 改一支 parser 即可，不影響其他畫面。

### 6.5 Fixture 清單
`data.js` 匯出一組 fixtures，每場景一筆（含 blocked 案例）：
- `ask_us1_summary`（passed）、`ask_us2_compare`（passed）、`ask_us4_segment`（passed）、`ask_blocked`（blocked，買賣建議）
- `research_us2`（answered，evidence≥3，react_steps≤6）
- `alerts`（陣列：1×alert/1×watch/1×info，含 1×blocked）

點快速場景卡 = 顯示短暫 loading 動畫（節點逐一亮）後渲染對應 fixture（feels live，無後端）。

---

## 7. 技術結構

無 build step，**單一自含 HTML**（為 Drive 派送：一檔雙擊即開、離線可跑、無相對路徑斷裂）：

```
05_Demo資料/
└── Polaris Desk - UX 互動原型.html   # 內含 <style> + <script>（fixtures + router + 渲染 + 抽屜 + parser）
```

- **Router**：`window.location.hash` 切 view（`#/home #/us1 #/us2 #/us4 #/research #/watchdog #/report #/blocked #/database #/history`）；`hashchange` 重渲染。
- **渲染**：vanilla JS（無框架、無 CDN 相依 → 離線可開）。
- **內嵌資料**：§6.5 fixtures 以 JS 常數內嵌（`FX` / `ALERTS`），形狀同真實 API。
- **RWD**：≤1180 與 ≤720 兩段斷點，右側欄／導覽列收合、整頁自然捲動（SC-005「4 場景無跑版」）。
- **Print**：`@media print` 隱藏導覽/側欄、A4 版面（`#/report` 匯出）。

> 註：本節原以 `data.js`/`app.js` 邏輯分檔描述；**as-built 為單檔自含**（同等內容內嵌於一個 `.html`），以利 Drive 一檔派送與離線備援。

---

## 8. 依賴、開放問題與切點

- **真 API 串接（R7 後續）**：把「讀 `data.js`」換成 `fetch('/ask'|'/research')`；契約已對齊（§6）→ 零改欄位。
- **Watchdog `GET /alerts` 未實作**：原型 mock-only；正式需 R3（事件格式）+ R2（thin endpoint）補。
- **US3 ColPali 為 P2/可砍**：以 `data-feature="colpali"` 標示，砍＝隱旗標；連動真 ColPali POC 命中率 ≥70% 才上（TD-01）。
- **`source_id` 真實格式**：若後端非 §6.4 格式，R7 補一支 parser（其餘畫面不受影響）。
- **存放位置**：原型置於 Drive `Polaris Desk/05_Demo資料/ux-prototype/`（與團隊 demo 資產同處）；本規格置於 repo `docs/superpowers/specs/`（規格慣例）。

---

## 9. 驗收（DoD，對應 R7 spec）

- [ ] 4 主畫面 + 來源抽屜可點擊走完（涵蓋 R7 五個 DoD 畫面）。
- [ ] US1/US2/US4 三種答案卡變體 + blocked 案例正確渲染。
- [ ] Citation 點擊→來源抽屜**跳轉正確率 100%**（SC-007）。
- [ ] 深度研究 ReAct 時間軸 + 證據≥3 + 迴圈≤6 徽章正確。
- [ ] 合規哨兵 severity 上色 + blocked 標紅。
- [ ] `#/report` 可 `window.print()` 出乾淨 A4。
- [ ] **手機 RWD 4 場景無跑版**（SC-005）。
- [ ] 所有 fixture 欄位**一字不差**對齊 §6（接真 API 零改）。
- [ ] 雙擊 `index.html` 離線可開（無 CDN/後端相依，憲法 V 備援）。
```