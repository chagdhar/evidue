FROM node:26-bookworm AS web
WORKDIR /src/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.13-slim
WORKDIR /app
RUN pip install --no-cache-dir uv
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev
COPY backend ./backend
COPY --from=web /src/frontend/dist ./frontend_dist
RUN addgroup --system evidue && adduser --system --ingroup evidue evidue \
    && mkdir -p /app/data && chown -R evidue:evidue /app/data
USER evidue
EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=3s --start-period=20s --retries=3 \
  CMD ["/app/.venv/bin/python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health')"]
CMD ["/app/.venv/bin/uvicorn","app.main:app","--app-dir","backend","--host","0.0.0.0","--port","8000"]
