#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = ROOT / "frontend" / "src"
DIST_ROOT = ROOT / "frontend" / "dist"

# These markers must never ship in public UI/source. Keep this list intentionally
# explicit so an accidental fallback cannot silently reintroduce a founder address.
FORBIDDEN = (
    "Email Dharun",
    "mailto:",
    "personal email address",
)

# Ignore tests because they may assert that forbidden strings are absent.
def candidate_files(root: Path):
    if not root.exists():
        return []
    return [
        p for p in root.rglob("*")
        if p.is_file()
        and p.suffix.lower() in {".ts", ".tsx", ".js", ".jsx", ".html", ".css", ".json"}
        and not p.name.endswith((".test.ts", ".test.tsx", ".spec.ts", ".spec.tsx"))
    ]

violations: list[str] = []
for base in (SOURCE_ROOT, DIST_ROOT):
    for path in candidate_files(base):
        text = path.read_text(errors="ignore")
        for marker in FORBIDDEN:
            if marker.lower() in text.lower():
                violations.append(f"{path.relative_to(ROOT)} contains forbidden public marker: {marker}")

# Also catch a direct personal-address shaped fallback if someone changes the exact
# founder address while leaving it embedded in public source.
public_email_pattern = re.compile(
    r"(?:href\s*=\s*[\"']mailto:|contactEmail\s*=|@[a-z0-9._%+-]+(?:gmail|yahoo|outlook|hotmail)\.[a-z]{2,})",
    re.IGNORECASE,
)
for path in candidate_files(SOURCE_ROOT):
    text = path.read_text(errors="ignore")
    if public_email_pattern.search(text):
        violations.append(f"{path.relative_to(ROOT)} contains a direct public email fallback")

if violations:
    print("Public privacy check failed:", file=sys.stderr)
    for item in sorted(set(violations)):
        print(f"- {item}", file=sys.stderr)
    raise SystemExit(1)

print("Public privacy checks passed.")
