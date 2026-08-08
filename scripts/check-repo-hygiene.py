#!/usr/bin/env python3
"""Fast repository-integrity checks that do not require network access."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEXT_SUFFIXES = {
    ".css",
    ".html",
    ".js",
    ".json",
    ".md",
    ".py",
    ".sh",
    ".toml",
    ".ts",
    ".tsx",
    ".yaml",
    ".yml",
}
IGNORED_PARTS = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "artifacts",
    "dist",
    "node_modules",
    "playwright-report",
    "test-results",
}


def _git_files() -> list[Path] | None:
    if not (ROOT / ".git").exists():
        return None
    process = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=ROOT,
        check=False,
        capture_output=True,
    )
    if process.returncode != 0:
        return None
    return [ROOT / item.decode() for item in process.stdout.split(b"\0") if item]


def _candidate_files() -> list[Path]:
    tracked = _git_files()
    if tracked is not None:
        return [path for path in tracked if path.is_file()]
    return [
        path
        for path in ROOT.rglob("*")
        if path.is_file() and not IGNORED_PARTS.intersection(path.relative_to(ROOT).parts)
    ]


def main() -> int:
    failures: list[str] = []
    files = _candidate_files()

    for path in files:
        relative = path.relative_to(ROOT)
        if path.suffix == ".json":
            try:
                json.loads(path.read_text())
            except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
                failures.append(f"{relative}: invalid JSON: {exc}")

        if path.suffix in TEXT_SUFFIXES or path.name in {"Dockerfile", "Makefile"}:
            try:
                lines = path.read_text().splitlines()
            except (OSError, UnicodeDecodeError):
                continue
            for line_number, line in enumerate(lines, 1):
                if line != line.rstrip():
                    failures.append(f"{relative}:{line_number}: trailing whitespace")

        if os.access(path, os.X_OK) and path.suffix in {".py", ".sh"}:
            try:
                first_line = path.open(encoding="utf-8").readline()
            except (OSError, UnicodeDecodeError):
                continue
            if not first_line.startswith("#!"):
                failures.append(f"{relative}: executable script is missing a shebang")

    if (ROOT / ".git").exists():
        diff_check = subprocess.run(
            ["git", "diff", "--check"],
            cwd=ROOT,
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        if diff_check.returncode != 0:
            failures.append("git diff --check failed:\n" + diff_check.stdout.strip())

    if failures:
        print("Repository hygiene failed:", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1

    print(f"Repository hygiene passed ({len(files)} files checked).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
