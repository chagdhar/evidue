#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "qualification" / "public_sources.json"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Download lawful public contract qualification sources"
    )
    parser.add_argument("--pack", required=True)
    parser.add_argument("--output-root", default=str(ROOT / "qualification" / "downloaded"))
    args = parser.parse_args()

    catalog = json.loads(CATALOG.read_text())
    selected = next((item for item in catalog["packs"] if item["id"] == args.pack), None)
    if selected is None:
        raise SystemExit(f"Unknown public qualification pack: {args.pack}")

    root = Path(args.output_root) / selected["id"]
    docs_dir = root / "documents"
    docs_dir.mkdir(parents=True, exist_ok=True)
    manifest_docs = []
    for item in selected["documents"]:
        request = urllib.request.Request(
            item["url"],
            headers={"User-Agent": "Evidue contract qualification research contact=operator"},
        )
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                content = response.read()
                content_type = response.headers.get("content-type", "")
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as exc:
            raise SystemExit(
                f"Could not download {item['title']} from {item['url']}: {exc}. "
                "Network access is required only for this source-fetch step; downloaded contracts "
                "remain local and are ignored by Git."
            ) from exc
        suffix = (
            ".pdf"
            if "pdf" in content_type.lower() or item["url"].lower().endswith(".pdf")
            else ".html"
        )
        filename = f"{item['id'].lower()}{suffix}"
        (docs_dir / filename).write_bytes(content)
        manifest_docs.append(
            {
                "id": item["id"],
                "title": item["title"],
                "path": f"documents/{filename}",
                "document_type": item.get("document_type", "public_source"),
                "precedence": item.get("precedence", 100),
                "source_url": item["url"],
                "retrieved_at": datetime.now(UTC).isoformat(),
            }
        )
    manifest = {
        "id": selected["id"],
        "title": selected["title"],
        "contract_id": f"QUAL-{selected['id'].upper()}",
        "customer": selected.get("customer", "Qualification customer"),
        "vendor": selected.get("vendor", "Qualification vendor"),
        "documents": manifest_docs,
        "relations": selected.get("relations", []),
        "gold_file": None,
        "scenario_file": None,
        "mutations": [],
        "source_class": selected["source_class"],
        "source_notes": selected["notes"],
    }
    (root / "manifest.json").write_text(json.dumps(manifest, indent=2))
    (root / "SOURCES.json").write_text(json.dumps(selected, indent=2))
    print(root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
