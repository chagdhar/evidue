#!/usr/bin/env bash
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd)
cd "$ROOT"
PYTHONPATH=backend UV_CACHE_DIR=/tmp/evidue-uv-cache uv run --group dev python scripts/product-smoke.py
