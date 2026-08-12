#!/usr/bin/env bash
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/.." && pwd)
cd "$ROOT"

echo "[1/5] Removing disposable fixture database and generated state"
rm -f data/evidue.db data/*.sqlite data/*.sqlite3
rm -rf .pytest_cache .ruff_cache frontend/dist playwright-report test-results
find backend -type d -name __pycache__ -prune -exec rm -rf {} +

echo "[2/5] Installing Python, frontend, and Playwright dependencies"
./scripts/bootstrap.sh

echo "[3/5] Generating production-shaped source exports"
UV_CACHE_DIR=/tmp/evidue-uv-cache uv run python scripts/generate-source-fixtures.py

echo "[4/5] Creating the headline synthetic fixture"
./scripts/seed-demo.sh headline

echo "[5/5] Running the fast validation suite"
./scripts/dev-check.sh fast

printf '\nSetup complete. Start Evidue with:\n  ./scripts/dev.sh\n\nThen open:\n  http://localhost:5173/try\n\nProtected product:\n  http://localhost:5173/workspace\n'
