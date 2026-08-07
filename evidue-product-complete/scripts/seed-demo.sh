#!/usr/bin/env bash
set -euo pipefail
scenario=${1:-headline}
PYTHONPATH=backend UV_CACHE_DIR=/tmp/evidue-uv-cache uv run --project . python -c 'import sys; from app.db.repository import reset; print(reset(sys.argv[1]))' "$scenario"
