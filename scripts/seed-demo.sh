#!/usr/bin/env bash
set -euo pipefail
PYTHONPATH=backend UV_CACHE_DIR=/tmp/evidue-uv-cache uv run --project . python -c 'from app.db.repository import reset; print(reset())'
