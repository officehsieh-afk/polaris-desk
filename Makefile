# Polaris Desk — 常用指令（make <target>）
.PHONY: install dev db-up db-down test fmt lint check

install:        ## 安裝相依（uv 優先，沒有用 pip）
	uv sync || pip install -e ".[dev]"

db-up:          ## 起本地 Postgres + pgvector
	docker compose up -d db

db-down:        ## 關閉本地資料庫
	docker compose down

test:           ## 跑測試
	pytest -q

fmt:            ## 格式化
	ruff format src tests

lint:           ## 檢查
	ruff check src tests

check: lint test  ## lint + test 一起跑
