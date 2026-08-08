"""Tiny dependency-free PDF renderer for vendor dispute packages.

The output is deliberately plain and audit-friendly. It avoids adding a PDF
framework to the core product just to create a printable evidence summary.
"""

from __future__ import annotations

import textwrap
from typing import Any


def _escape_pdf_text(value: str) -> str:
    return value.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _wrap(value: object, width: int = 92) -> list[str]:
    text = " ".join(str(value).split())
    return textwrap.wrap(text, width=width, break_long_words=True, break_on_hyphens=False) or [""]


def _page_stream(lines: list[str]) -> bytes:
    commands = ["BT", "/F1 9 Tf", "50 760 Td"]
    first = True
    for line in lines:
        if not first:
            commands.append("0 -14 Td")
        commands.append(f"({_escape_pdf_text(line)}) Tj")
        first = False
    commands.append("ET")
    return "\n".join(commands).encode("latin-1", errors="replace")


def render_dispute_pdf(payload: dict[str, Any]) -> bytes:
    lines: list[str] = [
        "EVIDUE VENDOR DISPUTE PACKAGE",
        "",
        f"Case: {payload['case_number']}",
        f"Status: {payload['status']}",
        f"Subject: {payload['subject']}",
        f"Reconciliation run: {payload['run_id']}",
        f"Approval: {payload['approval_id']}",
        f"Disputed amount: ${payload['disputed_amount']}",
        f"Disputed lines: {payload['item_count']}",
        "",
        "The items below are derived from an approved Evidue reconciliation. Machine",
        "determinations and finance review overlays remain separately auditable.",
        "",
    ]
    for index, item in enumerate(payload.get("items", []), start=1):
        lines.extend(
            _wrap(
                f"{index}. Outcome {item['outcome_id']} | ${item['amount']} | "
                f"{item['reason_code']} | source={item['source']}"
            )
        )
        lines.extend(_wrap(f"   {item['reason']}"))
    if payload.get("vendor_response"):
        lines.extend(["", "VENDOR RESPONSE"])
        lines.extend(_wrap(payload["vendor_response"]))

    page_lines = 48
    pages = [lines[i : i + page_lines] for i in range(0, len(lines), page_lines)] or [[""]]
    page_object_numbers = [4 + index * 2 for index in range(len(pages))]

    objects: dict[int, bytes] = {
        1: b"<< /Type /Catalog /Pages 2 0 R >>",
        2: (
            "<< /Type /Pages /Kids "
            f"[{' '.join(f'{number} 0 R' for number in page_object_numbers)}] "
            f"/Count {len(pages)} >>"
        ).encode(),
        3: b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    }
    for index, page in enumerate(pages):
        page_number = 4 + index * 2
        content_number = page_number + 1
        stream = _page_stream(page)
        objects[page_number] = (
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            f"/Resources << /Font << /F1 3 0 R >> >> /Contents {content_number} 0 R >>"
        ).encode()
        objects[content_number] = (
            f"<< /Length {len(stream)} >>\nstream\n".encode() + stream + b"\nendstream"
        )

    output = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets: dict[int, int] = {0: 0}
    for number in range(1, max(objects) + 1):
        offsets[number] = len(output)
        output.extend(f"{number} 0 obj\n".encode())
        output.extend(objects[number])
        output.extend(b"\nendobj\n")
    xref_offset = len(output)
    output.extend(f"xref\n0 {max(objects) + 1}\n".encode())
    output.extend(b"0000000000 65535 f \n")
    for number in range(1, max(objects) + 1):
        output.extend(f"{offsets[number]:010d} 00000 n \n".encode())
    output.extend(
        (
            f"trailer\n<< /Size {max(objects) + 1} /Root 1 0 R >>\n"
            f"startxref\n{xref_offset}\n%%EOF\n"
        ).encode()
    )
    return bytes(output)
