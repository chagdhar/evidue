#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

# One command: bootstrap, apply only safe Ruff fixes, format, then run the
# complete deterministic/backend/frontend/browser validation gate.
./scripts/bootstrap-checks.sh all
export PATH="$PWD/.venv/bin:$PATH"

printf '%s\n' '[FIX] Formatting Python'
ruff format backend scripts
printf '%s\n' '[FIX] Applying safe Ruff fixes'
ruff check backend scripts --fix
printf '%s\n' '[FIX] Reformatting after lint fixes'
ruff format backend scripts
printf '%s\n' '[CHECK] Preflight'
./scripts/check-preflight.sh

exec ./scripts/evidue-proof.sh full
