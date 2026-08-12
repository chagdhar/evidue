#!/usr/bin/env bash
set -euo pipefail
mode=${1:-fast}
if [[ "$mode" != "fast" && "$mode" != "full" ]]; then
  echo "usage: $0 fast|full" >&2
  exit 2
fi
UV_CACHE_DIR=/tmp/evidue-uv-cache uv run ruff format --check backend
UV_CACHE_DIR=/tmp/evidue-uv-cache uv run ruff check backend
python scripts/check-demo-branding.py
python scripts/check-public-privacy.py
node scripts/check-contact-apps-script.js
PYTHONPATH=backend UV_CACHE_DIR=/tmp/evidue-uv-cache uv run pytest
PYTHONPATH=backend UV_CACHE_DIR=/tmp/evidue-uv-cache uv run --group dev python scripts/product-smoke.py
npm --prefix frontend run lint
npm --prefix frontend run test
npm --prefix frontend run build
python scripts/check-public-privacy.py
if [ "$mode" = full ]; then
  npm run e2e
fi
