"""Authenticated API for the isolated, operator-assisted pilot workflow."""

from __future__ import annotations

import csv
import io
import json
import re
import uuid
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field

from app.upload.auth import require_pilot_access
from app.upload.models import PilotInvoiceRow, PilotRawRecordRow
from app.upload.parsers import (
    ParseResult,
    parse_evidence_csv,
    parse_evidence_json,
    parse_evidence_jsonl,
    parse_identity_map_csv,
    parse_invoice_csv,
)
from app.upload.pilot_db import PilotSessionLocal
from app.upload.store import (
    approve_contract_compilation,
    clear_pilot_data,
    compare_reconciliation_runs,
    compilation_view,
    compile_contract,
    confirm_manual_match,
    contract_view,
    create_contract,
    create_customer_review,
    create_invoice,
    create_upload,
    customer_review_view,
    evidence_package,
    fail_upload,
    finalize_upload,
    get_match_candidates,
    get_unmatched_events,
    ingest_evidence_events,
    ingest_invoice_claims,
    latest_customer_review,
    persist_identity_mappings,
    pilot_status,
    reconciliation_details,
    reconciliation_summary,
    run_identity_matching,
    run_pilot_reconciliation,
)

router = APIRouter(
    prefix="/api/pilot",
    tags=["pilot"],
    dependencies=[Depends(require_pilot_access)],
)

MAX_UPLOAD_BYTES = 50 * 1024 * 1024
SAFE_SOURCE_TYPE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,99}$")


class CustomerReviewRequest(BaseModel):
    reviewed_by: str = Field(min_length=2, max_length=200)
    claims_sampled: int = Field(ge=0)
    confirmed_disputes: int = Field(ge=0)
    rejected_disputes: int = Field(ge=0)
    missing_disputes: int = Field(ge=0)
    estimated_overpayment_prevented: Decimal = Field(ge=0)
    estimated_hours_saved: Decimal = Field(ge=0)
    would_use_next_month: bool
    willingness_to_pay: str = Field(default="", max_length=200)
    permission_to_quote: bool = False
    notes: str = Field(default="", max_length=4000)


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _safe_filename(name: str | None, fallback: str) -> str:
    cleaned = Path(name or fallback).name.strip()
    if not cleaned or cleaned in {".", ".."}:
        return fallback
    return cleaned[:255]


async def _read_upload(file: UploadFile) -> bytes:
    content = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, f"File exceeds {MAX_UPLOAD_BYTES // (1024 * 1024)} MB limit")
    if not content.strip():
        raise HTTPException(422, "Uploaded file is empty")
    return content


def _parse_iso(value: str, label: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise HTTPException(422, f"{label} must be an ISO 8601 timestamp") from exc
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(UTC).replace(tzinfo=None)
    return parsed


def _parse_money(value: str, label: str) -> Decimal:
    try:
        amount = Decimal(value)
    except InvalidOperation as exc:
        raise HTTPException(422, f"{label} must be a decimal amount") from exc
    if amount < 0:
        raise HTTPException(422, f"{label} cannot be negative")
    return amount


def _extract_contract_text(filename: str, content: bytes) -> str:
    suffix = Path(filename).suffix.lower()
    if suffix in {".txt", ".md", ".text"} or not suffix:
        try:
            text = content.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise ValueError("Contract text must be UTF-8") from exc
    elif suffix == ".pdf":
        try:
            from pypdf import PdfReader
        except ImportError as exc:  # pragma: no cover - dependency installation issue
            raise ValueError("PDF support requires the pypdf dependency") from exc
        reader = PdfReader(io.BytesIO(content))
        text = "\n\n".join((page.extract_text() or "").strip() for page in reader.pages).strip()
    else:
        raise ValueError("Contract must be a UTF-8 text/Markdown file or a PDF")
    if len(text.strip()) < 50:
        raise ValueError("Contract text must contain at least 50 characters")
    return text.strip()


def _parse_evidence(content: bytes, filename: str, source_type: str) -> ParseResult:
    suffix = Path(filename).suffix.lower()
    if suffix == ".csv":
        return parse_evidence_csv(content, source_type)
    if suffix == ".jsonl":
        return parse_evidence_jsonl(content, source_type)
    if suffix == ".json":
        return parse_evidence_json(content, source_type)
    raise HTTPException(422, "Evidence file must use .csv, .json, or .jsonl")


def _reject_if_empty(result: ParseResult, noun: str) -> None:
    if result.accepted:
        return
    raise HTTPException(
        422,
        {
            "detail": f"No valid {noun} parsed",
            "rejections": [
                {"row": rejection.row_number, "reason": rejection.reason}
                for rejection in result.rejected[:20]
            ],
        },
    )


def _mark_upload_failed(upload_class: type, upload_id: str, reason: str) -> None:
    with PilotSessionLocal.begin() as session:
        failed = session.get(upload_class, upload_id)
        if failed:
            fail_upload(session, failed, reason)


@router.get("/status")
def get_pilot_status() -> dict[str, object]:
    with PilotSessionLocal() as session:
        return pilot_status(session)


@router.post("/contract")
async def upload_contract(
    file: Annotated[UploadFile, File(...)],
    customer: str = Query(..., min_length=2, max_length=200),
    vendor: str = Query(..., min_length=2, max_length=200),
    period_start: str = Query(...),
    period_end: str = Query(...),
    price_per_outcome: str = Query("0.00"),
) -> dict[str, object]:
    content = await _read_upload(file)
    filename = _safe_filename(file.filename, "contract.txt")
    with PilotSessionLocal.begin() as session:
        upload = create_upload(
            session,
            "contract",
            filename,
            content,
            content_type=file.content_type,
        )
    try:
        text = _extract_contract_text(filename, content)
        start = _parse_iso(period_start, "period_start")
        end = _parse_iso(period_end, "period_end")
        price = _parse_money(price_per_outcome, "price_per_outcome")
        with PilotSessionLocal.begin() as session:
            upload = session.get(type(upload), upload.id)
            if upload is None:
                raise RuntimeError("Upload record disappeared")
            contract = create_contract(
                session,
                upload,
                customer=customer,
                vendor=vendor,
                period_start=start,
                period_end=end,
                price_per_outcome=price,
                source_document=filename,
                source_text=text,
            )
            upload.status = "complete"
            upload.rows_parsed = 1
            upload.rows_accepted = 1
            contract_id = contract.id
    except HTTPException as exc:
        _mark_upload_failed(type(upload), upload.id, str(exc.detail))
        raise
    except (ValueError, RuntimeError) as exc:
        _mark_upload_failed(type(upload), upload.id, str(exc))
        raise HTTPException(422, str(exc)) from exc
    with PilotSessionLocal() as session:
        return {"upload_id": upload.id, "contract": contract_view(session, contract_id)}


@router.get("/contracts/{contract_id}")
def get_contract(contract_id: str) -> dict[str, object]:
    with PilotSessionLocal() as session:
        try:
            return contract_view(session, contract_id)
        except LookupError as exc:
            raise HTTPException(404, str(exc)) from exc


@router.post("/contracts/{contract_id}/compile")
def compile_pilot_contract(
    contract_id: str,
    mode: str = Query("auto", pattern="^(auto|live|recorded)$"),
) -> dict[str, object]:
    try:
        with PilotSessionLocal.begin() as session:
            row = compile_contract(session, contract_id, mode=mode)
            return compilation_view(row)
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(422, str(exc)) from exc


@router.post("/compilations/{compilation_id}/approve")
def approve_pilot_compilation(compilation_id: str) -> dict[str, object]:
    try:
        with PilotSessionLocal.begin() as session:
            row = approve_contract_compilation(session, compilation_id)
            return compilation_view(row)
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


@router.post("/invoice")
async def upload_invoice(
    file: Annotated[UploadFile, File(...)],
    contract_id: str = Query(...),
    invoice_id: str | None = Query(None, min_length=3, max_length=120),
    billing_period_start: str = Query(...),
    billing_period_end: str = Query(...),
) -> dict[str, object]:
    content = await _read_upload(file)
    filename = _safe_filename(file.filename, "invoice.csv")
    if Path(filename).suffix.lower() != ".csv":
        raise HTTPException(422, "Invoice must be a CSV file")
    with PilotSessionLocal.begin() as session:
        upload = create_upload(
            session,
            "invoice",
            filename,
            content,
            content_type=file.content_type,
        )
    result = parse_invoice_csv(content)
    with PilotSessionLocal.begin() as session:
        current_upload = session.get(type(upload), upload.id)
        if current_upload is None:
            raise HTTPException(500, "Upload record disappeared")
        finalize_upload(session, current_upload, result)
    _reject_if_empty(result, "invoice rows")
    inv_id = invoice_id or f"INV-PILOT-{uuid.uuid4().hex[:12].upper()}"
    try:
        start = _parse_iso(billing_period_start, "billing_period_start")
        end = _parse_iso(billing_period_end, "billing_period_end")
        with PilotSessionLocal.begin() as session:
            current_upload = session.get(type(upload), upload.id)
            if current_upload is None:
                raise RuntimeError("Upload record disappeared")
            create_invoice(
                session,
                current_upload,
                invoice_id=inv_id,
                contract_id=contract_id,
                billing_period_start=start,
                billing_period_end=end,
            )
            count = ingest_invoice_claims(session, current_upload, result, inv_id)
    except HTTPException as exc:
        _mark_upload_failed(type(upload), upload.id, str(exc.detail))
        raise
    except LookupError as exc:
        _mark_upload_failed(type(upload), upload.id, str(exc))
        raise HTTPException(404, str(exc)) from exc
    except (ValueError, RuntimeError) as exc:
        _mark_upload_failed(type(upload), upload.id, str(exc))
        raise HTTPException(409, str(exc)) from exc
    return {
        "upload_id": upload.id,
        "invoice_id": inv_id,
        "claims_ingested": count,
        "rows_parsed": len(result.accepted) + len(result.rejected),
        "rows_accepted": count,
        "rows_rejected": len(result.rejected) + (len(result.accepted) - count),
        "rejections": [
            {"row": rejection.row_number, "reason": rejection.reason}
            for rejection in result.rejected[:20]
        ],
    }


@router.post("/evidence")
async def upload_evidence(
    file: Annotated[UploadFile, File(...)],
    invoice_id: str = Query(...),
    source_type: str = Query(..., min_length=2, max_length=100),
) -> dict[str, object]:
    if not SAFE_SOURCE_TYPE.fullmatch(source_type):
        raise HTTPException(422, "source_type contains unsupported characters")
    content = await _read_upload(file)
    filename = _safe_filename(file.filename, "evidence.jsonl")
    with PilotSessionLocal.begin() as session:
        upload = create_upload(
            session,
            "evidence",
            filename,
            content,
            source_type,
            content_type=file.content_type,
            invoice_id=invoice_id,
        )
    try:
        result = _parse_evidence(content, filename, source_type)
    except HTTPException as exc:
        _mark_upload_failed(type(upload), upload.id, str(exc.detail))
        raise
    with PilotSessionLocal.begin() as session:
        current_upload = session.get(type(upload), upload.id)
        if current_upload is None:
            raise HTTPException(500, "Upload record disappeared")
        finalize_upload(session, current_upload, result)
    _reject_if_empty(result, "evidence rows")
    try:
        with PilotSessionLocal.begin() as session:
            current_upload = session.get(type(upload), upload.id)
            if current_upload is None:
                raise RuntimeError("Upload record disappeared")
            count = ingest_evidence_events(session, current_upload, result, invoice_id)
    except LookupError as exc:
        _mark_upload_failed(type(upload), upload.id, str(exc))
        raise HTTPException(404, str(exc)) from exc
    return {
        "upload_id": upload.id,
        "invoice_id": invoice_id,
        "source_type": source_type,
        "events_ingested": count,
        "rows_parsed": len(result.accepted) + len(result.rejected),
        "rows_accepted": count,
        "rows_rejected": len(result.rejected) + (len(result.accepted) - count),
        "rejections": [
            {"row": rejection.row_number, "reason": rejection.reason}
            for rejection in result.rejected[:20]
        ],
    }


@router.post("/identity-map")
async def upload_identity_map(
    file: Annotated[UploadFile, File(...)],
    invoice_id: str = Query(...),
) -> dict[str, object]:
    content = await _read_upload(file)
    filename = _safe_filename(file.filename, "identity-map.csv")
    if Path(filename).suffix.lower() != ".csv":
        raise HTTPException(422, "Identity map must be a CSV file")
    with PilotSessionLocal.begin() as session:
        upload = create_upload(
            session,
            "identity_map",
            filename,
            content,
            content_type=file.content_type,
            invoice_id=invoice_id,
        )
    result = parse_identity_map_csv(content)
    with PilotSessionLocal.begin() as session:
        current_upload = session.get(type(upload), upload.id)
        if current_upload is None:
            raise HTTPException(500, "Upload record disappeared")
        finalize_upload(session, current_upload, result)
    _reject_if_empty(result, "identity mappings")
    with PilotSessionLocal.begin() as session:
        current_upload = session.get(type(upload), upload.id)
        if current_upload is None:
            raise HTTPException(500, "Upload record disappeared")
        count = persist_identity_mappings(session, current_upload, result, invoice_id)
        summary = run_identity_matching(session, invoice_id)
    if count == 0:
        _mark_upload_failed(type(upload), upload.id, "No identity mappings referenced valid claims")
        raise HTTPException(422, "No identity mappings referenced valid claims")
    return {
        "upload_id": upload.id,
        "invoice_id": invoice_id,
        "mappings_persisted": count,
        "matching_summary": {
            "total_events": summary.total_events,
            "direct_matches": summary.direct_matches,
            "identity_map_matches": summary.identity_map_matches,
            "suggested_composite_matches": summary.composite_matches,
            "unresolved": summary.unresolved,
        },
    }


@router.post("/match")
def run_matching_endpoint(invoice_id: str = Query(...)) -> dict[str, object]:
    with PilotSessionLocal.begin() as session:
        if session.get(PilotInvoiceRow, invoice_id) is None:
            raise HTTPException(404, "Pilot invoice not found")
        summary = run_identity_matching(session, invoice_id)
    return {
        "invoice_id": invoice_id,
        "total_events": summary.total_events,
        "direct_matches": summary.direct_matches,
        "identity_map_matches": summary.identity_map_matches,
        "suggested_composite_matches": summary.composite_matches,
        "unresolved": summary.unresolved,
        "policy": "Composite heuristic matches remain review-only until manually confirmed.",
    }


@router.get("/review/unmatched")
def get_unmatched(
    invoice_id: str = Query(...),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> dict[str, object]:
    with PilotSessionLocal() as session:
        total, events = get_unmatched_events(session, invoice_id, limit, offset)
    return {
        "invoice_id": invoice_id,
        "total": total,
        "offset": offset,
        "limit": limit,
        "items": events,
    }


@router.get("/review/candidates/{event_id}")
def get_candidates(event_id: str, invoice_id: str = Query(...)) -> dict[str, object]:
    with PilotSessionLocal() as session:
        candidates = get_match_candidates(session, invoice_id, event_id)
    if not candidates:
        raise HTTPException(404, "Event not found or no candidate claims")
    return {"invoice_id": invoice_id, "event_id": event_id, "candidates": candidates}


@router.post("/review/confirm")
def confirm_match(
    invoice_id: str = Query(...),
    event_id: str = Query(...),
    claim_id: str = Query(...),
    rationale: str = Query(..., min_length=3, max_length=1000),
) -> dict[str, object]:
    try:
        with PilotSessionLocal.begin() as session:
            row = confirm_manual_match(
                session,
                invoice_id=invoice_id,
                event_id=event_id,
                claim_id=claim_id,
                rationale=rationale,
                confirmed_by="operator",
            )
            return {
                "match_id": row.id,
                "invoice_id": invoice_id,
                "event_id": event_id,
                "claim_id": claim_id,
                "method": "manual",
                "confirmed_at": row.confirmed_at.isoformat(),
            }
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.post("/reconcile")
def reconcile_invoice(invoice_id: str = Query(...)) -> dict[str, object]:
    try:
        with PilotSessionLocal.begin() as session:
            return run_pilot_reconciliation(session, invoice_id)
    except LookupError as exc:
        raise HTTPException(409, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.get("/reconciliation")
def get_reconciliation(run_id: str | None = Query(None)) -> dict[str, object]:
    try:
        with PilotSessionLocal() as session:
            summary = reconciliation_summary(session, run_id)
            summary["determinations"] = reconciliation_details(
                session, summary["reconciliation_id"]
            )
            return summary
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.get("/reconciliations/{run_id}/compare/{prior_run_id}")
def compare_runs(run_id: str, prior_run_id: str) -> dict[str, object]:
    try:
        with PilotSessionLocal() as session:
            return compare_reconciliation_runs(session, run_id, prior_run_id)
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.post("/reconciliations/{run_id}/customer-review")
def record_customer_review(
    run_id: str,
    request: CustomerReviewRequest,
) -> dict[str, object]:
    try:
        with PilotSessionLocal.begin() as session:
            row = create_customer_review(
                session,
                run_id=run_id,
                reviewed_by=request.reviewed_by,
                claims_sampled=request.claims_sampled,
                confirmed_disputes=request.confirmed_disputes,
                rejected_disputes=request.rejected_disputes,
                missing_disputes=request.missing_disputes,
                estimated_overpayment_prevented=request.estimated_overpayment_prevented,
                estimated_hours_saved=request.estimated_hours_saved,
                would_use_next_month=request.would_use_next_month,
                willingness_to_pay=request.willingness_to_pay,
                permission_to_quote=request.permission_to_quote,
                notes=request.notes,
            )
            return customer_review_view(row)
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.get("/reconciliations/{run_id}/customer-review")
def get_customer_review(run_id: str) -> dict[str, object]:
    try:
        with PilotSessionLocal() as session:
            return latest_customer_review(session, run_id)
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.get("/reconciliations/{run_id}/exports/summary.json")
def export_summary(run_id: str) -> Response:
    try:
        with PilotSessionLocal() as session:
            payload = reconciliation_summary(session, run_id)
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    return Response(
        json.dumps(payload, indent=2),
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{run_id}-summary.json"'},
    )


@router.get("/reconciliations/{run_id}/exports/evidence.json")
def export_evidence(run_id: str) -> Response:
    try:
        with PilotSessionLocal() as session:
            payload = evidence_package(session, run_id)
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    return Response(
        json.dumps(payload, indent=2),
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{run_id}-evidence.json"'},
    )


@router.get("/reconciliations/{run_id}/exports/disputes.csv")
def export_disputes(run_id: str) -> Response:
    with PilotSessionLocal() as session:
        try:
            reconciliation_summary(session, run_id)
        except LookupError as exc:
            raise HTTPException(404, str(exc)) from exc
        rows = [
            row for row in reconciliation_details(session, run_id) if row["status"] == "disputed"
        ]
    output = io.StringIO()
    writer = csv.DictWriter(
        output,
        fieldnames=[
            "outcome_id",
            "status",
            "rule_id",
            "reason",
            "billed_amount",
            "confirmed_disputed_amount",
            "engine_version",
            "rule_program_version",
        ],
    )
    writer.writeheader()
    writer.writerows({key: row.get(key) for key in writer.fieldnames} for row in rows)
    return Response(
        output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{run_id}-disputes.csv"'},
    )


@router.get("/raw-records/{raw_record_id}")
def get_raw_record(raw_record_id: str) -> dict[str, object]:
    with PilotSessionLocal() as session:
        row = session.get(PilotRawRecordRow, raw_record_id)
        if row is None:
            raise HTTPException(404, "Pilot raw record not found")
        return {
            "id": row.id,
            "upload_id": row.upload_id,
            "invoice_id": row.invoice_id,
            "row_number": row.row_number,
            "source_record_id": row.source_record_id,
            "record_type": row.record_type,
            "source_system": row.source_system,
            "occurred_at": row.occurred_at.isoformat() if row.occurred_at else None,
            "raw_payload": row.raw_payload,
            "normalized_payload": row.normalized_payload,
            "payload_hash": row.payload_hash,
            "parser_version": row.parser_version,
            "mapping_version": row.mapping_version,
            "normalization_warnings": row.normalization_warnings,
        }


@router.post("/clear")
def clear_pilot() -> dict[str, bool]:
    with PilotSessionLocal.begin() as session:
        clear_pilot_data(session)
    return {"cleared": True}
