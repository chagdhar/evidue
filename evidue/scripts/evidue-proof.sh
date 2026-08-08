#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
export PYTHONPATH="${PYTHONPATH:-backend}"

if [ -x .venv/bin/python ] && .venv/bin/python -c 'import fastapi, pydantic, pytest, sqlalchemy' >/dev/null 2>&1; then
  export PATH="$PWD/.venv/bin:$PATH"
  exec .venv/bin/python scripts/evidue_proof.py "$@"
fi

if [ -n "${VIRTUAL_ENV:-}" ] && python -c 'import fastapi, pydantic, pytest, sqlalchemy' >/dev/null 2>&1; then
  exec python scripts/evidue_proof.py "$@"
fi

# Useful in offline inspection images with preinstalled runtime dependencies.
if python3 -c 'import fastapi, pydantic, pytest, sqlalchemy' >/dev/null 2>&1; then
  exec python3 scripts/evidue_proof.py "$@"
fi

if command -v uv >/dev/null 2>&1; then
  exec uv run --group dev python scripts/evidue_proof.py "$@"
fi

printf '%s\n' 'Evidue proof requires a bootstrapped Python environment or uv.' >&2
exit 2
