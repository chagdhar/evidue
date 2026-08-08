#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
./scripts/bootstrap-checks.sh all
export PATH="$PWD/.venv/bin:$PATH"

# Fail fast on syntax/hygiene/style before starting the slower backend and
# browser suites. evidue-proof.sh repeats these checks in the final dossier,
# but only after this preflight has guaranteed they are clean.
./scripts/check-preflight.sh
exec ./scripts/evidue-proof.sh full
