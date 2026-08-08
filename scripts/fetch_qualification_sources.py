#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.agreements.document_ingestion import (
    DocumentIntegrityError,
    decode_transport_bytes,
    validate_text_artifact,
)
from app.agreements.qualification import _strip_html

CATALOG = ROOT / "qualification" / "public_sources.json"


def _validate_download(name: str, content: bytes, suffix: str) -> None:
    if suffix == ".html":
        text = _strip_html(content.decode("utf-8-sig", errors="replace"))
        validate_text_artifact(text, name=name, require_contract_like=True)
    elif suffix in {".txt", ".md"}:
        text = content.decode("utf-8-sig", errors="replace")
        validate_text_artifact(text, name=name, require_contract_like=True)
    elif suffix == ".pdf":
        if not content.startswith(b"%PDF"):
            raise DocumentIntegrityError(f"Downloaded {name} is not a valid PDF payload")


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

    user_agent = os.environ.get(
        "EVIDUE_FETCH_USER_AGENT",
        "Evidue Contract Qualification research@example.com",
    )
    for item in selected["documents"]:
        # Prefer an identity response so stored bytes are the actual artifact.
        # decode_transport_bytes still handles servers that ignore this request.
        headers = {
            "User-Agent": user_agent,
            "Accept-Encoding": "identity",
            "Accept": "text/html,application/xhtml+xml,application/pdf,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }
        request = urllib.request.Request(item["url"], headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                raw_content = response.read()
                content_type = response.headers.get("content-type", "")
                content_encoding = response.headers.get("content-encoding")
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as exc:
            raise SystemExit(
                f"Could not download {item['title']} from {item['url']}: {exc}. "
                "Network access is required only for this source-fetch step; downloaded contracts "
                "remain local and are ignored by Git."
            ) from exc

        try:
            decoded = decode_transport_bytes(raw_content, content_encoding)
        except DocumentIntegrityError as exc:
            raise SystemExit(f"Downloaded {item['title']} could not be decoded: {exc}") from exc

        suffix = (
            ".pdf"
            if "pdf" in content_type.lower() or item["url"].lower().endswith(".pdf")
            else ".html"
        )
        filename = f"{item['id'].lower()}{suffix}"
        try:
            _validate_download(filename, decoded.content, suffix)
        except DocumentIntegrityError as exc:
            raise SystemExit(
                f"Downloaded {item['title']} failed contract-document integrity checks: {exc}"
            ) from exc

        (docs_dir / filename).write_bytes(decoded.content)
        manifest_docs.append(
            {
                "id": item["id"],
                "title": item["title"],
                "path": f"documents/{filename}",
                "document_type": item.get("document_type", "public_source"),
                "precedence": item.get("precedence", 100),
                "source_url": item["url"],
                "retrieved_at": datetime.now(UTC).isoformat(),
                "raw_sha256": decoded.raw_sha256,
                "content_sha256": decoded.content_sha256,
                "transport_encoding": decoded.transport_encoding,
                "content_type": content_type,
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
