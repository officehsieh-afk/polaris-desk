# R7 前端 starter — API 型別 + mock 契約

> **這是什麼**：給 R7（前端 / Demo 全端）開工用的「原料」——後端 HTTP API 的
> TypeScript 型別 + 三份**真實**回應 mock。**不含 UI**；UI 與技術選型（Chainlit /
> Next.js）仍由 R7 自己拍板（見 [`../docs/R7_frontend_開工指南.md`](../docs/R7_frontend_開工指南.md) §1）。

## 內容

| 檔案 | 用途 |
|---|---|
| `api-types/polaris-api.d.ts` | 由 live `/openapi.json` 自動生成的 TS 型別（751 行，含 `AskResponse`/`Citation`/`ResearchResponse`/`ReActStep`/`AlertResponse`）。對接時 import，零手抄、零漂移。 |
| `mocks/ask.json` | `POST /ask` 真實回應（對話 + 引用 UI / Citation Tracer 用）。 |
| `mocks/research.json` | `POST /research` 真實回應（ReAct trace UI 用）。 |
| `mocks/alerts.json` | `GET /alerts` 真實回應（Alert Inbox 用）。 |

三份 mock 是 **2026-06-18 對 live 後端實打**抓回來的真實 payload，形狀與
開工指南 §2 契約一字不差（`source_id` / `compliance_status` / `react_steps`…）。
先用 mock 做完 UI，接真 API 時只換資料來源即可。

## 後端 endpoint（live）

```
Base: https://polaris-api-14326813937.asia-east1.run.app

GET  /health                 健康探針（雲端走 /health，GFE 攔 /healthz）
POST /ask        {query}     → mocks/ask.json 形狀
POST /research   {question}  → mocks/research.json 形狀
GET  /alerts                 → mocks/alerts.json 形狀
GET  /notifications          通知中心（額外 surface，spec 002）
```

⚠️ **延遲**：`/ask`、`/research` 走 Vertex LLM，實測 **23–34 秒**（含冷啟動）。
UI 要做 loading 狀態 + 逾時 fallback；Demo 前先打一發暖機。結構化端點
（`/alerts`）是 ~0.1 秒。

## 重新生成型別（契約變動時）

```bash
npx openapi-typescript https://polaris-api-14326813937.asia-east1.run.app/openapi.json \
  -o frontend/api-types/polaris-api.d.ts
```

> 改契約 = R2/R3/R7 一起改（開工指南 §6）。欄名別自己發明。
