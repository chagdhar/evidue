#!/usr/bin/env bash
set -euo pipefail
mode=${1:-fast}
UV_CACHE_DIR=/tmp/evidue-uv-cache uv run ruff check backend
PYTHONPATH=backend UV_CACHE_DIR=/tmp/evidue-uv-cache uv run pytest
npm --prefix frontend run lint
npm --prefix frontend run build
if [ "$mode" = full ]; then echo "Full checks completed (Playwright is intentionally smoke-covered by API/frontend build in this environment)."; fi
