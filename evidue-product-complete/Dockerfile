FROM node:22-bookworm AS web
WORKDIR /src/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
ARG VITE_POSTHOG_KEY
ARG VITE_POSTHOG_HOST
ENV VITE_POSTHOG_KEY=$VITE_POSTHOG_KEY \
    VITE_POSTHOG_HOST=$VITE_POSTHOG_HOST
RUN npm run build

FROM python:3.13-slim
WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    EVIDUE_DB_PATH=/app/data/evidue.db

RUN pip install --no-cache-dir uv
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY backend ./backend
COPY demo-data ./demo-data
COPY --from=web /src/frontend/dist ./frontend_dist

RUN addgroup --system evidue \
    && adduser --system --ingroup evidue evidue \
    && mkdir -p /app/data \
    && chown -R evidue:evidue /app/data

USER evidue
EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=90s --retries=3 \
  CMD ["/app/.venv/bin/python", "-c", "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:' + os.getenv('PORT', '8080') + '/api/health')"]

CMD ["sh", "-c", "exec /app/.venv/bin/uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port ${PORT:-8080}"]
