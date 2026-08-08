#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
export PYTHONPATH="${PYTHONPATH:-backend}"

if [ -n "${VIRTUAL_ENV:-}" ]; then
  exec python scripts/evidue_proof.py "$@"
fi

# Inspection/CI images sometimes already provide the runtime dependencies but
# cannot reach a package registry. Prefer that interpreter when it is complete.
if python3 -c 'import fastapi, pydantic, pytest, sqlalchemy' >/dev/null 2>&1; then
  exec python3 scripts/evidue_proof.py "$@"
fi

if command -v uv >/dev/null 2>&1; then
  exec uv run --group dev python scripts/evidue_proof.py "$@"
fi

printf '%s\n' 'Evidue proof requires either a bootstrapped Python environment or uv.' >&2
exit 2
