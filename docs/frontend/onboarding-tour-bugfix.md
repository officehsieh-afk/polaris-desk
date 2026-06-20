# ResearchTour — 效能與邏輯問題修正紀錄

> **日期**：2026-06-19
> **影響範圍**：前端元件，後端零異動
> **修改檔案**：
> - `frontend/src/components/polaris/ResearchTour.tsx`（主要）
> - `frontend/src/components/polaris/OnboardingModal.tsx`（1 行）
> - `frontend/src/app/styles/polaris.css`（CSS 補丁）

---

## 問題清單與修法

### Bug 1 + Bug 3（Critical）— loading 永遠不推進

**觸發條件**
- Bug 1：使用者在 Tour 出現前已執行過查詢（`hasResults` 初始值已是 `true`）
- Bug 3：使用者從 Step 3+ 點步驟點退回 Step 2（動作步驟），再按「執行範例分析」

**根因**
```ts
// useEffect 只在 hasResults「改變」時觸發
useEffect(() => {
  if (waitingRef.current && hasResults) { setStep(3); }
}, [hasResults]);
// → hasResults 沒有從 false → true 的變化，effect 不跑，waiting 永遠不解除
```

**修法**：`handleRunSample` 點擊時先同步檢查 `hasResults`
```ts
const handleRunSample = () => {
  if (hasResults) { setStep(3); return; }   // 已有結果，直接跳，不進 loading
  // ...
};
```
動作步驟 JSX 同步調整：`hasResults` 已有值時按鈕改為「查看結果 →」
```tsx
hasResults
  ? <button onClick={() => setStep(3)}>查看結果 →</button>
  : <button onClick={handleRunSample}>執行範例分析 →</button>
```

---

### Bug 2（Critical）— API 失敗時 loading 永遠不解除

**觸發條件**：`run()` 的 catch 區塊被觸發（API 錯誤、網路逾時）

**根因**
```ts
// research/page.tsx catch 區
} catch {
  setPhase("done");
  setProgress(0);
  // data 仍是 undefined → hasResults 仍是 false → Tour 永遠卡在 loading
}
```

**修法**：加入 30 秒安全逾時，到期後顯示提示讓使用者強制推進
```ts
timeoutRef.current = setTimeout(() => {
  if (waitingRef.current) setTimedOut(true);
}, 30_000);
```
Loading 卡片逾時後顯示：
```
⚠ 載入時間較長，可繼續查看後續說明。  [繼續]
```
「繼續」呼叫 `forceAdvance()` → 直接跳至 Step 3，即使沒有結果也能繼續引導。

---

### Bug 4（Medium）— `dismiss()` 在 API 飛行中呼叫 `onReset()`，async 回呼引發 state 衝突

**觸發條件**：使用者在 `waiting=true`（API 仍在飛行）時按「跳過」

**根因**
```ts
// 原本 dismiss() 無條件呼叫 onReset()
const dismiss = () => {
  onReset(); // 清掉 query/phase，但 run() 的 .then() 還在跑
  // → 回呼完成後再次 setHasQueried/setPhase/toast，state 不一致
};
```

**修法**：`waiting=true` 時跳過 `onReset()`，讓 API 自然完成
```ts
const dismiss = () => {
  // ...
  if (!waiting) onReset(); // API 飛行中不重置，讓結果正常顯示
};
```

---

### Bug 5（Medium）— OnboardingModal 與 ResearchTour 同時出現，元素高亮在 OnboardingModal 後方閃現

**觸發條件**：使用者第一次進入 `/research`（兩個 flag 均未設定）

**根因**
- `OnboardingModal`（AppShell）：立即顯示，`z-index: 300`
- `ResearchTour`：延遲 700ms 後顯示，overlay `z-index: 200`、卡片 `z-index: 202`
- Tour 的 `useEffect` 加高亮（`z-index: 201`）在 OnboardingModal 後方閃現

同一 tab 的 `localStorage.setItem` **不觸發 `storage` 事件**，Tour 無法得知 OnboardingModal 何時關閉。

**修法**：OnboardingModal 關閉時 dispatch CustomEvent；Tour 等事件後再啟動
```ts
// OnboardingModal.tsx dismiss()
window.dispatchEvent(new CustomEvent("polaris:onboarded"));
```
```ts
// ResearchTour.tsx useEffect
if (localStorage.getItem(ONBOARD_KEY)) {
  // OnboardingModal 已完成 → 延遲 700ms 啟動
  const t = setTimeout(startTour, 700);
  return () => clearTimeout(t);
} else {
  // 等待 OnboardingModal 關閉事件
  window.addEventListener("polaris:onboarded", handler);
  return () => window.removeEventListener("polaris:onboarded", handler);
}
```

---

### Bug 6（Minor）— loading 卡片高度跳躍

**現象**：loading 中間態的卡片比正常卡片短，切換時視覺跳動

**修法**：加 `minHeight: 64px`
```tsx
<div className="tour-card-loading" style={{ minHeight: 64 }}>
```

---

### Bug 7（UX）— Desktop 引用追蹤器被 rcol-ctx overflow:hidden 裁切

**觸發條件**：桌機版 Step 6（引用追蹤器），螢幕高度不足時第 3 個 ctx-panel 被裁切

**根因**
```css
/* polaris.css */
.rcol-ctx { position: sticky; top: 0; overflow: hidden; }
/* → 三個 ctx-panel 疊在 sticky 容器內，高度超出時底部 panel 被裁切 */
/* → overlay 阻擋手動捲動，使用者無法看到引用追蹤器 */
```

**修法**：高亮目標在 `.rcol-ctx` 內時，暫時加 `.tour-ctx-open` class 解除裁切
```ts
// applyHighlight()
if (ctx && el.closest(".rcol-ctx")) {
  (ctx as HTMLElement).classList.add("tour-ctx-open");
} else if (ctx) {
  (ctx as HTMLElement).classList.remove("tour-ctx-open");
}
```
```css
/* polaris.css */
.rcol-ctx.tour-ctx-open { overflow: visible; }
```
`clearHighlight()` 一併移除 `.tour-ctx-open`。

---

### Bug 8（UX）— Mobile 模型思考追蹤與引用追蹤器看不到

**觸發條件**：手機版（< 1230px）Step 5、Step 6

**根因**
```css
/* polaris.css @media (max-width: 1230px) */
.rcol-ctx { position: static; flex-direction: row; flex-wrap: wrap; overflow: visible; }
/* → rcol-ctx 在頁面流最下方，且 overlay pointer-events:all 阻擋手動捲動 */
/* → 使用者無法捲動到 rcol-ctx 的位置 */
```

**修法**：`applyHighlight()` 高亮後加入 `scrollIntoView`
```ts
requestAnimationFrame(() => {
  (el as HTMLElement).scrollIntoView({ behavior: "smooth", block: "center" });
});
```
JS 呼叫的 `scrollIntoView` 不受 `pointer-events: all` 影響，可突破 overlay 限制自動捲動至目標元素。

同時加入 `isVisible()` 判斷：若 primary selector 元素不可見（`display:none` 或尺寸為 0），自動降級至 `fallbackSelector`。

---

### Bug 9（Layout）— Mobile tour-card 被 mobnav 遮住

**觸發條件**：手機版（< 1230px）所有 Tour 步驟

**根因**
```css
/* tour-card 固定在 bottom: 132px，計算僅考慮 dock (~120px + 12px gap) */
/* 手機版 mobnav 為 position:fixed; bottom:0; height:60px; z-index:40 */
/* → tour-card 實際底部落在 mobnav 範圍內，被遮擋 */
```

**修法**：手機版 media query 增加 60px
```css
@media (max-width: 1230px) {
  .tour-card { bottom: 196px; } /* 132 + 60（mobnav）+ 4（buffer） */
}
```

---

### Bug 10（UX）— 模型思考追蹤 selector 選不到目標，退回整個 sidebar

**觸發條件**：Step 5（模型思考追蹤），高亮包含上方「收起側欄」按鈕

**根因**
```css
/* rcol-ctx 子元素順序 */
/* 1. button.ctx-toggle-btn  ← nth-child(1) */
/* 2. div.ctx-panel（模型思考追蹤）← nth-child(2) */
/* 3. div.ctx-panel（監控系統警示）← nth-child(3) */
/* 4. div.ctx-panel（引用追蹤器）← nth-child(4) */
```
`.ctx-panel:first-child` 要求元素**同時**是 `.ctx-panel` 且是第 1 個子元素。
但第 1 個子元素是 `button.ctx-toggle-btn`，不符合 → 選不到任何元素 → 退回 `fallbackSelector: ".rcol-ctx"` → 整個 sidebar 含收縮按鈕都被高亮。

**修法**：改用 `:nth-child(2)` 直接選第 2 個子元素
```ts
selector: ".rcol-ctx .ctx-panel:nth-child(2)",
fallbackSelector: ".rcol-ctx .ctx-panel:first-of-type",
```

---

### Bug 11（UX）— 引用追蹤器 selector 選到監控系統警示

**觸發條件**：Step 6（引用追蹤器），高亮到錯誤的面板

**根因**
```ts
selector: ".rcol-ctx .ctx-panel:nth-child(3)"
// nth-child(3) 是 rcol-ctx 的第 3 個子元素 = 監控系統警示 panel
// 引用追蹤器實際是第 4 個子元素
```

**修法**：改用 `:nth-child(4)`
```ts
selector: ".rcol-ctx .ctx-panel:nth-child(4)",
fallbackSelector: ".rcol-ctx .ctx-panel:last-of-type",
```

---

### Feature（2026-06-20）— 新增監控系統警示步驟、側欄收縮步驟，重排步驟順序

**新增步驟**
1. **idx=5 監控系統警示**：`selector: ".rcol-ctx .ctx-panel:nth-child(3)"`（修正後即是正確面板）
2. **idx=7 側欄收縮**：同時高亮右側 `.ctx-toggle-btn`＋左側 `.collapse-btn`（導覽列收縮）；手機版 fallback 高亮 `.mobnav`（底部導覽列）

**新增 `secondarySelector` 欄位**
```ts
interface Step {
  // ...
  secondarySelector?: string | null;  // 同時高亮第二個目標
}
```
`applyHighlight(selector, fallback, secondary?)` 第三參數可選；`clearHighlight()` 已用 `querySelectorAll(".tour-highlight")` 全清，不需額外處理。

**重排後完整步驟（共 9 步）**

| idx | 標題 | selector | secondarySelector | fallbackSelector |
|---|---|---|---|---|
| 0 | 快速開始 | `.dock-chips` | — | `.dock` |
| 1 | 查詢列 | `.dock-input` | — | `.dock` |
| 2 | 執行範例分析（動作） | `.dock` | — | `.dock` |
| 3 | 營運重點摘要 | `.rcol-main .panel` | — | `.rcol-main` |
| 4 | 模型思考追蹤 | `.rcol-ctx .ctx-panel:nth-child(2)` | — | `…:first-of-type` |
| 5 | 監控系統警示 | `.rcol-ctx .ctx-panel:nth-child(3)` | — | `…:nth-of-type(2)` |
| 6 | 引用追蹤器 | `.rcol-ctx .ctx-panel:nth-child(4)` | — | `…:last-of-type` |
| 7 | 側欄收縮 | `.ctx-toggle-btn` | `.collapse-btn` | `.mobnav` |
| 8 | 引導完成（結尾） | null | — | — |

**手機版側欄收縮行為**：
- `.ctx-toggle-btn` → `display: none`（不可見）→ `isVisible()` 回傳 false
- 降級至 `fallbackSelector: ".mobnav"` → 高亮底部導覽列
- `.collapse-btn`（secondary）若不可見則直接跳過
- 說明文字標示「（桌機版）」，並說明手機版的等效排版

---

## 修正後完整行為流程

```
首次進入 /research
    │
    ├─ polaris-onboarded 未設 → 等 polaris:onboarded 事件
    │     OnboardingModal 關閉 → dispatch CustomEvent
    │     → 400ms 後 Tour 啟動
    │
    └─ polaris-onboarded 已設 → 700ms 後 Tour 啟動

Tour 啟動 (step=0)
    │
    Step 1（chips）→ Step 2（input）→ Step 3（動作）
    │
    ├─ hasResults 已是 true → 「查看結果 →」直接跳 step 3    ← Fix Bug 1/3
    └─ hasResults 是 false → 「執行範例分析 →」
          │ onRunSample() → waiting=true → loading 卡片
          │ + 30s timeout 安全閥                              ← Fix Bug 2
          │
          ├─ hasResults 變 true → 自動跳 step 3
          └─ 30s 到期 → 顯示「繼續」強制推進
          │
          使用者中途「跳過」(waiting=true)
          └─ dismiss() 跳過 onReset()，API 自然完成           ← Fix Bug 4

Step 4（summary）→ Step 5（ReAct）→ Step 6（monitor）→ Step 7（citation）→ Step 8（sidebar）→ Step 9（完成）
    └─ dismiss() → localStorage flag → clearHighlight() → onReset()
```

---

## DoD 更新

- [x] Bug 1/3：`handleRunSample` 先同步檢查 `hasResults`
- [x] Bug 2：30s timeout → `timedOut` 狀態 → 強制推進按鈕
- [x] Bug 4：`dismiss()` 中 `if (!waiting) onReset()`
- [x] Bug 5：`OnboardingModal` dispatch `polaris:onboarded`；Tour 等事件後啟動
- [x] Bug 6：loading card `minHeight: 64px`
- [x] Bug 7：`.rcol-ctx.tour-ctx-open { overflow: visible }` 解除桌機裁切
- [x] Bug 8：`scrollIntoView` via `requestAnimationFrame` 突破 overlay 限制（Mobile）
- [x] Bug 9：`@media (max-width: 1230px) { .tour-card { bottom: 196px } }` 避開 mobnav
- [x] Bug 10：模型思考追蹤 selector 改 `:nth-child(2)`，不再退回整個 sidebar
- [x] Bug 11：引用追蹤器 selector 改 `:nth-child(4)`，不再指向監控系統警示
- [x] Feature：新增監控系統警示（idx=5）＋側欄收縮（idx=7）步驟，共 9 步
- [x] Feature：`Step` 介面加 `secondarySelector`；`applyHighlight` 支援雙元素高亮
- [x] Feature：側欄收縮步驟手機版 fallback 高亮 `.mobnav`，說明文字標示桌機限定
- [x] 後端零異動
