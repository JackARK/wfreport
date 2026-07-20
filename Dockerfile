# ---- 阶段 1: 前端构建 ----
FROM node:20-bookworm-slim AS frontend
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build -- --base=/wfreport/

# ---- 阶段 2: 运行时 ----
FROM python:3.12-slim-bookworm

COPY --from=ghcr.io/astral-sh/uv:0.11.8 /uv /usr/local/bin/uv

ENV DEBIAN_FRONTEND=noninteractive \
    LANG=C.UTF-8 \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    LOG_LEVEL=INFO

# chromium + 中文字体(图表 PNG 渲染必须)
RUN apt-get update && apt-get install -y --no-install-recommends \
        chromium \
        fonts-noto-cjk \
        fonts-noto-cjk-extra \
        fonts-noto-cjk-extra \
        xvfb \
        libnss3 libatk1.0-0 libatk-bridge2.0-0 libgtk-3-0 libgbm1 \
        libasound2 libxshmfence1 libxkbcommon0 libxcomposite1 libxdamage1 \
        libxfixes3 libxrandr2 libpango-1.0-0 libcairo2 libfontconfig1 \
        libfreetype6 libdrm2 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 先装 Python 依赖(利用 Docker layer cache 加速重建)
COPY pyproject.toml uv.lock .python-version ./
RUN UV_NO_CACHE=1 uv sync --frozen --no-dev
ENV PATH="/app/.venv/bin:$PATH"

# 拷贝代码 + 资源
COPY backend/ ./backend/
COPY conftest.py ./
COPY --from=frontend /app/frontend/dist ./frontend/dist
COPY resource/ ./resource/

# data / output / logs 三个目录在 compose 里挂载,这里不创建内容
RUN mkdir -p /app/data /app/output /app/logs

# 让 kaleido 找到系统 chromium(不依赖 kaleido_get_chrome)
ENV KALEIDO_CHROME_PATH=/usr/bin/chromium \
    CHROME_BIN=/usr/bin/chromium

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/ai/providers', timeout=2).read()" || exit 1

CMD ["python", "-m", "uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
