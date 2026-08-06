"""Pilot API router.

All endpoints are under /api/pilot/. They provide the upload-based
ingestion path described in PRODUCT_PLAN.md Stage 1-2.

The demo routes (/api/demo/*) remain untouched.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)

from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from sqlalchemy import select

import app.db.repository as _repo
from app.db.models import (
    ContractRow,
    InvoiceRow,
    OperationalEventRow,
    OutcomeClaimRow,
)
from app.upload.match import IdentityMapping
from app.upload.parsers import (
    parse_evidence_csv,
    parse_evidence_json,
    parse_evidence_jsonl,
    parse_identity_map_csv,
    parse_invoice_csv,
)
from app.upload.store import (
    clear_pilot_data,
    confirm_manual_match,
    create_upload,
    ensure_pilot_state,
    finalize_upload,
    get_match_candidates,
    get_unmatched_events,
    ingest_evidence_events,
    ingest_invoice_claims,
    pilot_status,
    run_identity_matching,
)

router = APIRouter(prefix="/api/pilot", tags=["pilot"])

MAX_UPLOAD_BYTES = 50 * 1024 * 1024  # 50 MB


async def _read_upload(file: UploadFile) -> bytes:
    content = await file.read()
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, f"File exceeds {MAX_UPLOAD_BYTES // (1024*1024)} MB limit")
    if not content.strip():
        raise HTTPException(422, "Uploaded file is empty")
    return content


# ---------------------------------------------------------------------------
# Status
# ---------------------------------------------------------------------------


@router.get("/status")
def get_pilot_status() -> dict:
    with _repo.SessionLocal() as session:
        return pilot_status(session)


# ---------------------------------------------------------------------------
# Invoice upload
# ---------------------------------------------------------------------------


@router.post("/invoice")
async def upload_invoice(
    file: UploadFile = File(...),
    invoice_id: str | None = None,
    billing_period_start: str | None = None,
    billing_period_end: str | None = None,
) -> dict:
    """Upload a vendor invoice CSV."""
    content = await _read_upload(file)
    filename = file.filename or "invoice.csv"

    if not filename.lower().endswith(".csv"):
        raise HTTPException(422, "Invoice must be a CSV file")

    result = parse_invoice_csv(content)

    if not result.accepted and result.rejected:
        raise HTTPException(
            422,
            {
                "detail": "No valid rows parsed",
                "rejections": [
                    {"row": r.row_number, "reason": r.reason}
                    for r in result.rejected[:20]
                ],
            },
        )

    inv_id = invoice_id or f"INV-PILOT-{uuid.uuid4().hex[:8].upper()}"

    with _repo.SessionLocal.begin() as session:
        state = ensure_pilot_state(session)

        upload = create_upload(session, "invoice", filename)

        # Create or reuse invoice row
        existing_invoice = session.get(InvoiceRow, inv_id)
        if not existing_invoice:
            period_start = (
                datetime.fromisoformat(billing_period_start)
                if billing_period_start
                else datetime(2026, 1, 1)
            )
            period_end = (
                datetime.fromisoformat(billing_period_end)
                if billing_period_end
                else datetime(2026, 12, 31)
            )
            # Get or create a contract
            contract_id = state.active_contract_id or "CONTRACT-PILOT-001"
            existing_contract = session.get(ContractRow, contract_id)
            if not existing_contract:
                session.add(
                    ContractRow(
                        id=contract_id,
                        customer="Pilot Customer",
                        vendor="Pilot Vendor",
                        period_start=period_start,
                        period_end=period_end,
                        price_per_outcome=Decimal("1.50"),
                    )
                )
                state.active_contract_id = contract_id

            session.add(
                InvoiceRow(
                    id=inv_id,
                    contract_id=contract_id,
                    billing_period_start=period_start,
                    billing_period_end=period_end,
                    submitted_at=_now(),
                )
            )

        count = ingest_invoice_claims(session, upload, result, inv_id)
        finalize_upload(session, upload, result)

        state.invoice_uploaded = True
        state.active_invoice_id = inv_id

    return {
        "upload_id": upload.id,
        "invoice_id": inv_id,
        "claims_ingested": count,
        "rows_parsed": len(result.accepted) + len(result.rejected),
        "rows_accepted": len(result.accepted),
        "rows_rejected": len(result.rejected),
        "rejections": [
            {"row": r.row_number, "reason": r.reason}
            for r in result.rejected[:20]
        ],
    }


# ---------------------------------------------------------------------------
# Evidence upload
# ---------------------------------------------------------------------------


@router.post("/evidence")
async def upload_evidence(
    file: UploadFile = File(...),
    source_type: str = Query("unknown", max_length=100),
) -> dict:
    """Upload customer evidence (CSV, JSON, or JSONL)."""
    content = await _read_upload(file)
    filename = file.filename or "evidence"
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

    if ext == "csv":
        result = parse_evidence_csv(content, source_type)
    elif ext == "jsonl":
        result = parse_evidence_jsonl(content, source_type)
    elif ext == "json":
        result = parse_evidence_json(content, source_type)
    else:
        # Try to detect format
        stripped = content.strip()
        if stripped.startswith((b"{", b"[")):
            if b"\n{" in stripped:
                result = parse_evidence_jsonl(content, source_type)
            else:
                result = parse_evidence_json(content, source_type)
        else:
            result = parse_evidence_csv(content, source_type)

    if not result.accepted and result.rejected:
        raise HTTPException(
            422,
            {
                "detail": "No valid rows parsed",
                "rejections": [
                    {"row": r.row_number, "reason": r.reason}
                    for r in result.rejected[:20]
                ],
            },
        )

    with _repo.SessionLocal.begin() as session:
        state = ensure_pilot_state(session)
        upload = create_upload(session, "evidence", filename, source_type)
        count = ingest_evidence_events(session, upload, result)
        finalize_upload(session, upload, result)
        state.evidence_uploaded = True

    return {
        "upload_id": upload.id,
        "source_type": source_type,
        "events_ingested": count,
        "rows_parsed": len(result.accepted) + len(result.rejected),
        "rows_accepted": len(result.accepted),
        "rows_rejected": len(result.rejected),
        "rejections": [
            {"row": r.row_number, "reason": r.reason}
            for r in result.rejected[:20]
        ],
    }


# ---------------------------------------------------------------------------
# Identity map upload
# ---------------------------------------------------------------------------


@router.post("/identity-map")
async def upload_identity_map(
    file: UploadFile = File(...),
) -> dict:
    """Upload an identity mapping CSV."""
    content = await _read_upload(file)
    filename = file.filename or "identity-map.csv"

    result = parse_identity_map_csv(content)

    if not result.accepted and result.rejected:
        raise HTTPException(
            422,
            {
                "detail": "No valid mappings parsed",
                "rejections": [
                    {"row": r.row_number, "reason": r.reason}
                    for r in result.rejected[:20]
                ],
            },
        )

    # Convert to IdentityMapping objects and run matching
    mappings = [
        IdentityMapping(
            conversation_id=row.data.get("conversation_id"),
            customer_id=row.data.get("customer_id"),
            account_id=row.data.get("account_id"),
            outcome_id=row.data.get("outcome_id"),
        )
        for row in result.accepted
    ]

    with _repo.SessionLocal.begin() as session:
        upload = create_upload(session, "identity_map", filename)
        finalize_upload(session, upload, result)

        # Run matching with the new identity map
        summary = run_identity_matching(session, mappings)

    return {
        "upload_id": upload.id,
        "mappings_parsed": len(result.accepted),
        "matching_summary": {
            "total_events": summary.total_events,
            "direct_matches": summary.direct_matches,
            "identity_map_matches": summary.identity_map_matches,
            "composite_matches": summary.composite_matches,
            "unresolved": summary.unresolved,
        },
    }


# ---------------------------------------------------------------------------
# Match / rematch
# ---------------------------------------------------------------------------


@router.post("/match")
def run_matching_endpoint() -> dict:
    """Run the identity matching pipeline on all pending events."""
    with _repo.SessionLocal.begin() as session:
        summary = run_identity_matching(session)
        state = ensure_pilot_state(session)
        if summary.unresolved == 0:
            state.matching_complete = True

    return {
        "total_events": summary.total_events,
        "direct_matches": summary.direct_matches,
        "identity_map_matches": summary.identity_map_matches,
        "composite_matches": summary.composite_matches,
        "unresolved": summary.unresolved,
    }


# ---------------------------------------------------------------------------
# Review workbench
# ---------------------------------------------------------------------------


@router.get("/review/unmatched")
def get_unmatched(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> dict:
    """List events that have no resolved match."""
    with _repo.SessionLocal() as session:
        total, events = get_unmatched_events(session, limit, offset)
    return {"total": total, "offset": offset, "limit": limit, "items": events}


@router.get("/review/candidates/{event_id}")
def get_candidates(event_id: str) -> dict:
    """Suggest claims an unmatched event might belong to."""
    with _repo.SessionLocal() as session:
        candidates = get_match_candidates(session, event_id)
    if not candidates:
        raise HTTPException(404, "Event not found or no candidate claims")
    return {"event_id": event_id, "candidates": candidates}


@router.post("/review/confirm")
def confirm_match(
    event_id: str,
    outcome_id: str,
    rationale: str = "",
) -> dict:
    """Manually confirm a match between an event and a claim."""
    with _repo.SessionLocal.begin() as session:
        claim = session.get(OutcomeClaimRow, outcome_id)
        if not claim:
            raise HTTPException(404, f"Claim {outcome_id} not found")
        event = session.get(OperationalEventRow, event_id)
        if not event:
            raise HTTPException(404, f"Event {event_id} not found")

        match = confirm_manual_match(
            session,
            event_id=event_id,
            outcome_id=outcome_id,
            rationale=rationale,
        )

    return {
        "match_id": match.id,
        "event_id": event_id,
        "outcome_id": outcome_id,
        "method": "manual",
        "confirmed_at": match.confirmed_at.isoformat(),
    }


# ---------------------------------------------------------------------------
# Reconciliation (reuses existing engine)
# ---------------------------------------------------------------------------


@router.post("/reconcile")
def run_pilot_reconciliation() -> dict:
    """Run reconciliation on uploaded data.

    This calls the same domain engine as the demo path.
    """
    from app.db.repository import run_reconciliation

    with _repo.SessionLocal() as session:
        state = ensure_pilot_state(session)
        claim_count = session.scalar(
            select(OutcomeClaimRow).limit(1)
        )
        if not claim_count:
            raise HTTPException(
                409,
                "No claims uploaded yet. Upload an invoice first.",
            )

    result = run_reconciliation()

    with _repo.SessionLocal.begin() as session:
        state = ensure_pilot_state(session)
        state.reconciled = True

    return result


@router.get("/reconciliation")
def get_pilot_reconciliation() -> dict:
    """Get current reconciliation summary."""
    from app.db.repository import summary

    with _repo.SessionLocal() as session:
        state = ensure_pilot_state(session)
        if not state.reconciled:
            raise HTTPException(404, "No reconciliation has been run yet")
    return summary()


# ---------------------------------------------------------------------------
# Clear
# ---------------------------------------------------------------------------


@router.post("/clear")
def clear_pilot() -> dict:
    """Clear all pilot data and start fresh."""
    with _repo.SessionLocal.begin() as session:
        clear_pilot_data(session)
    return {"cleared": True}
