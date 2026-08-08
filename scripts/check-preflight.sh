#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

# Run the cheap deterministic gates before any expensive backend/browser suite.
# Wrapper scripts bootstrap dependencies first and put .venv/bin on PATH.
python -m compileall -q backend/app scripts
python scripts/check-repo-hygiene.py
ruff format --check backend scripts
ruff check backend scripts
