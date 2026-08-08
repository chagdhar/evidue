from __future__ import annotations

import gzip
import zlib
from pathlib import Path

import pytest
from app.agreements.document_ingestion import (
    DocumentIntegrityError,
    decode_transport_bytes,
    validate_text_artifact,
)
from app.agreements.qualification import load_document_text


def test_gzip_transport_is_decoded_before_storage_or_parsing() -> None:
    html = b"<html><body><h1>Agreement</h1><p>Customer shall pay Vendor fees.</p></body></html>"
    encoded = gzip.compress(html)
    decoded = decode_transport_bytes(encoded, "gzip")
    assert decoded.content == html
    assert decoded.transport_encoding == "gzip"
    assert decoded.raw_sha256 != decoded.content_sha256


def test_gzip_magic_is_detected_when_metadata_was_lost(tmp_path: Path) -> None:
    html = (
        b"<html><body><h1>Master Agreement</h1>"
        b"<p>Customer shall pay Vendor fees under each Order Form.</p>"
        b"<p>This agreement governs payment and services.</p></body></html>"
    )
    path = tmp_path / "contract.html"
    path.write_bytes(gzip.compress(html))
    text = load_document_text(path)
    assert "Master Agreement" in text
    assert "Customer shall pay Vendor fees" in text


def test_deflate_transport_is_decoded() -> None:
    body = b"Agreement between Customer and Vendor concerning fees and payment."
    decoded = decode_transport_bytes(zlib.compress(body), "deflate")
    assert decoded.content == body


def test_block_page_is_rejected() -> None:
    with pytest.raises(DocumentIntegrityError, match="block page"):
        validate_text_artifact(
            "Access Denied. Your request originates from an undeclared automated tool. " * 5,
            name="contract.html",
            require_contract_like=False,
        )


def test_binary_garbage_is_rejected() -> None:
    with pytest.raises(DocumentIntegrityError):
        validate_text_artifact(
            "\ufffd" * 100 + " agreement customer vendor payment " * 20,
            name="contract.html",
            require_contract_like=True,
        )
