# ===========================================================
# Polaris Desk — 容器化（W4 上 Cloud Run 用）
# 「我電腦能跑」= 「雲端能跑」，所以 W1 就先備好這個檔
# ===========================================================
FROM python:3.12-slim

# 系統相依（psycopg / 一些套件需要）
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 先複製相依定義，利用 layer cache
COPY pyproject.toml ./
RUN pip install --no-cache-dir --upgrade pip && pip install --no-cache-dir .

# 再複製程式
COPY src/ ./src/

ENV PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src \
    APP_ENV=cloud

EXPOSE 8000

# TODO(@R2)：W2-W3 接好 API 入口後改成實際啟動指令
#   例如：uvicorn polaris.api:app --host 0.0.0.0 --port 8000
CMD ["python", "-c", "import polaris; print('Polaris Desk container OK — TODO: 接 API 入口')"]
