#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
./scripts/bootstrap-checks.sh python
export PATH="$PWD/.venv/bin:$PATH"
./scripts/check-preflight.sh
exec ./scripts/evidue-proof.sh live "$@"
