#!/usr/bin/env bash
set -euo pipefail
UV_CACHE_DIR=/tmp/evidue-uv-cache uv sync --group dev
npm --prefix frontend ci
npm ci
npx playwright install chromium
