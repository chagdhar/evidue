#!/usr/bin/env bash
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/.." && pwd)
cd "$ROOT"

echo "[1/4] Removing disposable demo database and generated state"
rm -f data/evidue.db data/*.sqlite data/*.sqlite3
rm -rf .pytest_cache .ruff_cache frontend/dist playwright-report test-results
find backend -type d -name __pycache__ -prune -exec rm -rf {} +

echo "[2/4] Installing Python, frontend, and Playwright dependencies"
./scripts/bootstrap.sh

echo "[3/4] Creating the headline synthetic fixture"
./scripts/seed-demo.sh headline

echo "[4/4] Running the fast validation suite"
./scripts/dev-check.sh fast

printf '\nSetup complete. Start Evidue with:\n  ./scripts/dev.sh\n\nThen open:\n  http://localhost:5173/demo\n'
