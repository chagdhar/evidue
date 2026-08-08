#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

scope="${1:-all}"
case "$scope" in
  python|all) ;;
  *)
    printf 'usage: %s [python|all]\n' "$0" >&2
    exit 2
    ;;
esac

command -v uv >/dev/null 2>&1 || {
  printf '%s\n' 'uv is required to bootstrap Python checks.' >&2
  exit 2
}

python_ready=false
if [ -x .venv/bin/python ] && [ -x .venv/bin/ruff ]; then
  if .venv/bin/python -c 'import fastapi, httpx, pydantic, pytest, sqlalchemy' >/dev/null 2>&1 \
    && .venv/bin/ruff --version >/dev/null 2>&1; then
    python_ready=true
  fi
fi

if [ "$python_ready" != true ]; then
  uv sync --group dev
fi

if [ "$scope" = python ]; then
  exit 0
fi

command -v npm >/dev/null 2>&1 || {
  printf '%s\n' 'npm is required for frontend and browser checks.' >&2
  exit 2
}

if [ ! -d frontend/node_modules ]; then
  npm --prefix frontend ci --no-audit --no-fund
fi
if [ ! -d node_modules ]; then
  npm ci --no-audit --no-fund
fi

# `npm ci` installs the pinned Playwright package. `--no-install` prevents npx
# from silently fetching a different package version. Playwright itself skips
# the browser download when the pinned Chromium build is already present.
npx --no-install playwright install chromium
