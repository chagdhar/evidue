"""Defensive contract-document ingestion primitives.

Contract qualification and production compilation must never send transport-encoded
or obvious error-page bytes to an LLM.  This module keeps byte handling deterministic,
small, and provider independent.
"""

from __future__ import annotations

import gzip
import re
import zlib
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path


class DocumentIntegrityError(ValueError):
    """Raised when a purported contract artifact is unreadable or clearly wrong."""


@dataclass(frozen=True)
class DocumentBytes:
    content: bytes
    raw_sha256: str
    content_sha256: str
    transport_encoding: str | None


def sha256_hex(value: bytes) -> str:
    return sha256(value).hexdigest()


def decode_transport_bytes(raw: bytes, content_encoding: str | None = None) -> DocumentBytes:
    """Decode HTTP/content compression without trusting filename extensions.

    Historical qualification packs may already contain gzip bytes saved with an
    ``.html`` suffix.  Gzip magic is therefore detected even when the server's
    Content-Encoding metadata was lost.
    """

    raw_hash = sha256_hex(raw)
    encoding = (content_encoding or "").strip().lower() or None
    content = raw
    applied: str | None = None

    try:
        if encoding == "gzip" or content[:2] == b"\x1f\x8b":
            content = gzip.decompress(content)
            applied = "gzip"
        elif encoding == "deflate":
            try:
                content = zlib.decompress(content)
            except zlib.error:
                content = zlib.decompress(content, -zlib.MAX_WBITS)
            applied = "deflate"
    except (OSError, EOFError, zlib.error) as exc:
        raise DocumentIntegrityError(
            f"Could not decode {encoding or 'compressed'} document"
        ) from exc

    return DocumentBytes(
        content=content,
        raw_sha256=raw_hash,
        content_sha256=sha256_hex(content),
        transport_encoding=applied,
    )


def _replacement_ratio(text: str) -> float:
    return text.count("\ufffd") / max(1, len(text))


def _printable_ratio(text: str) -> float:
    printable = sum(ch.isprintable() or ch in "\n\r\t" for ch in text)
    return printable / max(1, len(text))


def validate_text_artifact(
    text: str,
    *,
    name: str,
    require_contract_like: bool = False,
) -> None:
    """Reject binary garbage, block pages, and implausibly empty contract text."""

    stripped = text.strip()
    if len(stripped) < 50:
        raise DocumentIntegrityError(f"Document {name} has too little readable text")
    if _replacement_ratio(stripped) > 0.01 or _printable_ratio(stripped) < 0.95:
        raise DocumentIntegrityError(f"Document {name} appears binary or incorrectly decoded")

    normalized = re.sub(r"\s+", " ", stripped).lower()
    block_markers = (
        "request rate threshold exceeded",
        "your request originates from an undeclared automated tool",
        "access denied",
        "temporarily unavailable due to excessive automated requests",
        "captcha",
    )
    if any(marker in normalized for marker in block_markers):
        raise DocumentIntegrityError(f"Document {name} appears to be an access/block page")

    if require_contract_like:
        contract_markers = (
            "agreement",
            "order form",
            "statement of work",
            "terms",
            "customer",
            "vendor",
            "fees",
            "payment",
        )
        if sum(marker in normalized for marker in contract_markers) < 2:
            raise DocumentIntegrityError(
                f"Document {name} does not contain enough contract-like language"
            )


def read_decoded_file(path: Path) -> DocumentBytes:
    """Read a local artifact and transparently unwrap legacy gzip/deflate payloads."""

    raw = path.read_bytes()
    return decode_transport_bytes(raw)
