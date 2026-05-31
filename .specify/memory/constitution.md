# Polaris Desk Constitution

> 北辰（Polaris Desk）— 台灣資本市場 Agent-Augmented Research Workflow。
> 本憲法凌駕所有任務 / 計畫 / PR；任何違反即為 **No-Go**。對應團隊規格：
> Google Drive `Polaris Desk/03_規格書_PRD/spec-kit/`（專題 spec + 7 角色 spec）。

## Core Principles

### I. 合規紅線 — NFR-031（NON-NEGOTIABLE）
新聞 / 投研功能**只描述、標證據、標矛盾，不得產出任何買賣建議**（投顧執照風險）。
所有對外輸出皆受此約束；Compliance 節點 / Watchdog / 新聞卡都必須攔截買賣建議，
目標：130 題 + 4 場景 + 紅隊題中**買賣建議 = 0**。違反 = 直接砍該輸出。

### II. 引用接地 — Grounding（NON-NEGOTIABLE）
每一句結論、每個數字都必須可追溯到來源（法說稿頁碼 / 新聞出處 / 財報欄位）。
無來源的宣稱不得輸出；來源矛盾時**標出矛盾**並列雙方出處，不替使用者下結論。

### III. 本地優先 · 金鑰安全
開發先本地（pgvector）省雲費（Q-03）；金鑰只放 `.env` / GCP Secret Manager，
**永不 commit、不貼群組、不丟 Drive**（Q-10）。`.env` 已 gitignore。

### IV. Eval 即品質門檻
功能「好不好」以 Ragas + 三方 Judge 客觀分數為準，不以主觀感覺放行。
硬門檻：Context Precision ≥ 0.85、Faithfulness ≥ 0.90、Answer Relevance ≥ 0.85；
130 題達標率 ≥ 80%（G3）。平常 CI 用 1 個便宜模型，三方 Judge 只在閘門跑（省 token）。

### V. Demo 可重現 + 離線備援
Demo 跑**雲端**（Cloud Run + BigQuery + Vercel），但必須有「本地 pgvector + 預錄影片」
的 Plan B；同一場景跑 10 次結果一致；斷網可於 < 30 秒切離線備援。

### VI. 最新技術棧
Gemini 用新版 `google-genai` SDK（`from google import genai; genai.Client()`）+
模型 `gemini-3-pro-preview` / `gemini-3-flash-preview`；嵌入 `gemini-embedding-2`（多模態、768 維、cosine）。
**不得**用已淘汰的 `google-generativeai` / `genai.configure`。Rerank 用 Cohere `client.v2.rerank`（`rerank-v4.0`）。

## Additional Constraints — 技術棧與成本

- 編排 LangGraph（StateGraph）；檢索 4-way（BM25 + 向量 + ColPali + Cohere Rerank）+ 新聞第 5 路。
- 向量庫經 `VectorStore` 介面抽象：`VECTOR_BACKEND=pgvector`（W1-W3）→ `bigquery`（W4 上雲）；維度 768、距離 cosine 兩端一致，切換後重跑同一份 eval 驗證。
- pgvector 查詢必須用 `<=>`（cosine）+ `ORDER BY <=> LIMIT k` 才走 HNSW 索引（見 `scripts/init_pgvector.sql` 註解）。
- 預算 ~$400 USD，大頭是 LLM token（非 GCP infra）；設預算警報、embedding 算一次重用、ColPali 用免費 GPU。

## Development Workflow — Go / No-Go 閘

- **G1 (Day 5)**：Ontology v1 凍結 + 100 份入庫本地 pgvector。
- **G2 (Day 10)**：e2e Workflow 跑通 + Ragas 管線上線 + BigQuery 煙測通過（Q-03）。
- **G3 (Day 17)**：ColPali/LLMLingua 整合 + Eval ≥ 80% + Deep Research + Watchdog 可跑。
- **G4 (Day 24)**：4 場景在雲端可重現 + 離線備援 + Watchdog 上線 + Eval ≥ 80%。
- **Demo (Day 28)**：5 分鐘無斷點，斷網切預錄。
- 過閘沒過即啟動 PRD §5.4 降級方案，不硬撐。

## Governance

本憲法凌駕所有其他實作慣例。所有 PR / review 必須驗證合規（特別是 I、II、III）。
修訂需經 PM（R1）+ Tech Lead（R2）同意並記入 `01_PM_Notion匯入/決策追蹤.csv`。
複雜度須被正當化；runtime 開發指引見 repo `README.md` 與 `CLAUDE.md`。

**Version**: 1.0.0 | **Ratified**: 2026-05-31 | **Last Amended**: 2026-05-31
