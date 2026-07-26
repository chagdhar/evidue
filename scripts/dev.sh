#!/usr/bin/env bash
set -euo pipefail
UV_CACHE_DIR=/tmp/evidue-uv-cache uv run --project . uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port 8000 & backend=$!
npm --prefix frontend run dev & frontend=$!
cleanup() {
  kill "$backend" "$frontend" 2>/dev/null || true
  wait "$backend" "$frontend" 2>/dev/null || true
}
trap cleanup EXIT INT TERM
wait -n "$backend" "$frontend"
