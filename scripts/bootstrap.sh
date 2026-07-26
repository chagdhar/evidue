#!/usr/bin/env bash
set -euo pipefail
uv sync --group dev
npm --prefix frontend install
