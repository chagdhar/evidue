"""Authenticated API for the isolated, operator-assisted pilot workflow."""

from __future__ import annotations

import csv
import html
import io
import json
import os
import re
import uuid
import zipfile
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Annotated, Literal
from xml.etree import ElementTree

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from app.agreements.bundle import DocumentRelationType
from app.agreements.capabilities import EvidenceSourceDescriptor, build_verification_plan
from app.agreements.models import AgreementIR
from app.agreements.presentation import agreement_finance_view
from app.upload.auth import require_pilot_access
from app.upload.models import (
    PilotAIRVersionRow,
    PilotAuditLogRow,
    PilotClaimRow,
    PilotContractRow,
    PilotFactRow,
    PilotInvoiceRow,
    PilotProvenanceEdgeRow,
    PilotRawRecordRow,
    PilotRuleCompilationRow,
)
from app.upload.parsers import (
    ParseResult,
    inspect_invoice_csv,
    parse_evidence_csv,
    parse_evidence_json,
    parse_evidence_jsonl,
    parse_identity_map_csv,
    parse_invoice_csv,
)
from app.upload.pilot_db import PilotSessionLocal
from app.upload.store import (
    agreement_runtime_comparison,
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
    record_audit,
    run_identity_matching,
    run_pilot_reconciliation,
    simulate_air_version_financial_impact,
    simulate_contract_historical_replay,
    update_workspace_config,
    workspace_config_view,
)

router = APIRouter(
    prefix="/api/pilot",
    tags=["pilot"],
    dependencies=[Depends(require_pilot_access)],
)

MAX_UPLOAD_BYTES = 50 * 1024 * 1024
SAFE_SOURCE_TYPE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,99}$")


class VerificationPlanRequest(BaseModel):
    sources: list[EvidenceSourceDescriptor] = Field(default_factory=list, max_length=100)


class NativeCompileRequest(BaseModel):
    proposal: dict[str, object] | None = None


class AgreementRelationRequest(BaseModel):
    source_document_id: str
    target_document_id: str
    relation: DocumentRelationType


class SemanticFactExtractionRequest(BaseModel):
    air_version_id: str
    claim_id: str
    fact_type: str = Field(min_length=1, max_length=200)
    question: str = Field(min_length=3, max_length=1000)
    raw_record_ids: list[str] = Field(min_length=1, max_length=50)


class FactReviewRequest(BaseModel):
    truth: Literal["true", "false", "unknown", "conflicting"]
    rationale: str = Field(min_length=3, max_length=2000)
    reviewed_by: str = Field(default="pilot-operator", min_length=2, max_length=200)


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


class WorkspaceConfigRequest(BaseModel):
    company_name: str = Field(default="", max_length=200)
    default_vendor: str = Field(default="", max_length=200)
    default_currency: str = Field(default="USD", min_length=3, max_length=3)
    timezone: str = Field(default="UTC", max_length=100)
    date_locale: str = Field(default="en-US", max_length=50)
    default_contract_rate: str = Field(default="", max_length=100)
    preferred_support_system: str = Field(default="", max_length=200)
    preferred_payment_system: str = Field(default="", max_length=200)
    preferred_crm_system: str = Field(default="", max_length=200)


class ContractTextRequest(BaseModel):
    customer: str = Field(min_length=2, max_length=200)
    vendor: str = Field(min_length=2, max_length=200)
    period_start: str
    period_end: str
    price_per_outcome: Decimal = Field(default=Decimal("0.00"), ge=0)
    source_document: str = Field(default="pasted-contract.txt", min_length=1, max_length=255)
    source_text: str = Field(min_length=50, max_length=2_000_000)


def _air_lifecycle(row: PilotAIRVersionRow) -> str:
    if row.superseded_by_id:
        return "superseded"
    if row.approved_at is not None:
        return "active"
    if not bool((row.assurance_json or {}).get("hard_gate_passed", False)):
        return "validation_failed"
    return "ready_for_review"


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
        try:
            reader = PdfReader(io.BytesIO(content))
            text = "\n\n".join((page.extract_text() or "").strip() for page in reader.pages).strip()
        except Exception as exc:
            raise ValueError("PDF file is invalid or could not be read") from exc
        if not text:
            raise ValueError(
                "No extractable text was found in the PDF. Upload a text-based PDF, DOCX, "
                "TXT/Markdown file, or paste the contract language."
            )
    elif suffix == ".docx":
        try:
            with zipfile.ZipFile(io.BytesIO(content)) as archive:
                document_xml = archive.read("word/document.xml")
            root = ElementTree.fromstring(document_xml)
        except (KeyError, zipfile.BadZipFile, ElementTree.ParseError) as exc:
            raise ValueError("DOCX file is invalid or missing readable document content") from exc
        namespace = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
        paragraphs: list[str] = []
        for paragraph in root.iter(namespace + "p"):
            pieces = [node.text or "" for node in paragraph.iter(namespace + "t")]
            value = "".join(pieces).strip()
            if value:
                paragraphs.append(value)
        text = "\n\n".join(paragraphs).strip()
    else:
        raise ValueError("Contract must be UTF-8 text/Markdown, DOCX, or PDF")
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


@router.post("/contract/text")
def create_contract_from_text(request: ContractTextRequest) -> dict[str, object]:
    content = request.source_text.encode("utf-8")
    filename = _safe_filename(request.source_document, "pasted-contract.txt")
    try:
        start = _parse_iso(request.period_start, "period_start")
        end = _parse_iso(request.period_end, "period_end")
        with PilotSessionLocal.begin() as session:
            upload = create_upload(
                session,
                "contract",
                filename,
                content,
                content_type="text/plain",
            )
            contract = create_contract(
                session,
                upload,
                customer=request.customer,
                vendor=request.vendor,
                period_start=start,
                period_end=end,
                price_per_outcome=request.price_per_outcome,
                source_document=filename,
                source_text=request.source_text.strip(),
            )
            upload.status = "complete"
            upload.rows_parsed = 1
            upload.rows_accepted = 1
            contract_id = contract.id
            upload_id = upload.id
        with PilotSessionLocal() as session:
            return {"upload_id": upload_id, "contract": contract_view(session, contract_id)}
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(422, str(exc)) from exc


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


@router.get("/compilations/{compilation_id}/agreement")
def get_compiled_agreement(compilation_id: str) -> dict[str, object]:
    with PilotSessionLocal() as session:
        row = session.get(PilotRuleCompilationRow, compilation_id)
        if row is None:
            raise HTTPException(404, "Pilot compilation not found")
        raw_response = row.raw_response or {}
        return {
            "compilation_id": row.id,
            "agreement_ir": raw_response.get("agreement_ir"),
            "conformance": raw_response.get("conformance"),
        }


@router.post("/compilations/{compilation_id}/verification-plan")
def create_verification_plan(
    compilation_id: str,
    request: VerificationPlanRequest,
) -> dict[str, object]:
    with PilotSessionLocal() as session:
        row = session.get(PilotRuleCompilationRow, compilation_id)
        if row is None:
            raise HTTPException(404, "Pilot compilation not found")
        payload = (row.raw_response or {}).get("agreement_ir")
        if payload is None:
            raise HTTPException(409, "Compilation does not contain an Agreement IR")
        agreement = AgreementIR.model_validate(payload)
        plan = build_verification_plan(
            agreement.agreement_id,
            agreement.proof_requirements,
            request.sources,
        )
        return plan.model_dump(mode="json")


@router.post("/invoice/preview")
async def preview_invoice(
    file: Annotated[UploadFile, File(...)],
    column_mapping: str | None = Query(None),
) -> dict[str, object]:
    content = await _read_upload(file)
    filename = _safe_filename(file.filename, "invoice.csv")
    if Path(filename).suffix.lower() != ".csv":
        raise HTTPException(422, "Invoice must be a CSV file")
    mapping: dict[str, str] | None = None
    if column_mapping:
        try:
            raw_mapping = json.loads(column_mapping)
        except json.JSONDecodeError as exc:
            raise HTTPException(422, "column_mapping must be a JSON object") from exc
        if not isinstance(raw_mapping, dict) or not all(
            isinstance(key, str) and isinstance(value, str) for key, value in raw_mapping.items()
        ):
            raise HTTPException(422, "column_mapping must map Evidue fields to CSV headers")
        mapping = raw_mapping
    try:
        return inspect_invoice_csv(content, mapping)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.post("/invoice")
async def upload_invoice(
    file: Annotated[UploadFile, File(...)],
    contract_id: str = Query(...),
    invoice_id: str | None = Query(None, min_length=3, max_length=120),
    billing_period_start: str = Query(...),
    billing_period_end: str = Query(...),
    column_mapping: str | None = Query(None),
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
    mapping: dict[str, str] | None = None
    if column_mapping:
        try:
            raw_mapping = json.loads(column_mapping)
        except json.JSONDecodeError as exc:
            raise HTTPException(422, "column_mapping must be a JSON object") from exc
        if not isinstance(raw_mapping, dict) or not all(
            isinstance(key, str) and isinstance(value, str) for key, value in raw_mapping.items()
        ):
            raise HTTPException(422, "column_mapping must map Evidue fields to CSV headers")
        mapping = raw_mapping
    result = parse_invoice_csv(content, mapping)
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
    complete_export: bool = Query(False),
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
            coverage_complete=complete_export,
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
        "complete_export": complete_export,
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


@router.get("/reconciliations/{run_id}/agreement-comparison")
def get_agreement_runtime_comparison(run_id: str) -> dict[str, object]:
    try:
        with PilotSessionLocal() as session:
            return agreement_runtime_comparison(session, run_id)
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
        with PilotSessionLocal.begin() as session:
            payload = reconciliation_summary(session, run_id)
            record_audit(session, "export.generated", "reconciliation", run_id, kind="summary.json")
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
        with PilotSessionLocal.begin() as session:
            payload = evidence_package(session, run_id)
            record_audit(
                session, "export.generated", "reconciliation", run_id, kind="evidence.json"
            )
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    return Response(
        json.dumps(payload, indent=2),
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{run_id}-evidence.json"'},
    )


@router.get("/reconciliations/{run_id}/exports/disputes.csv")
def export_disputes(run_id: str) -> Response:
    with PilotSessionLocal.begin() as session:
        try:
            reconciliation_summary(session, run_id)
        except LookupError as exc:
            raise HTTPException(404, str(exc)) from exc
        rows = [
            row for row in reconciliation_details(session, run_id) if row["status"] == "disputed"
        ]
        record_audit(session, "export.generated", "reconciliation", run_id, kind="disputes.csv")
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


@router.get("/reconciliations/{run_id}/exports/corrected-invoice.csv")
def export_corrected_invoice(run_id: str) -> Response:
    with PilotSessionLocal.begin() as session:
        try:
            reconciliation_summary(session, run_id)
            rows = reconciliation_details(session, run_id)
        except LookupError as exc:
            raise HTTPException(404, str(exc)) from exc
        record_audit(
            session,
            "export.generated",
            "reconciliation",
            run_id,
            kind="corrected-invoice.csv",
        )
    output = io.StringIO()
    fieldnames = [
        "outcome_id",
        "billed_amount",
        "decision",
        "payable_amount",
        "disputed_amount",
        "needs_review_amount",
        "rule_id",
        "reason",
    ]
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    for row in rows:
        writer.writerow(
            {
                "outcome_id": row["outcome_id"],
                "billed_amount": row["billed_amount"],
                "decision": row["status"],
                "payable_amount": row["confirmed_payable_amount"],
                "disputed_amount": row["confirmed_disputed_amount"],
                "needs_review_amount": row["needs_review_amount"],
                "rule_id": row["rule_id"],
                "reason": row["reason"],
            }
        )
    return Response(
        output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{run_id}-corrected-invoice.csv"'},
    )


@router.get("/reconciliations/{run_id}/exports/review-report.html")
def export_review_report(run_id: str) -> Response:
    with PilotSessionLocal.begin() as session:
        try:
            summary = reconciliation_summary(session, run_id)
            rows = reconciliation_details(session, run_id)
        except LookupError as exc:
            raise HTTPException(404, str(exc)) from exc
        record_audit(
            session,
            "export.generated",
            "reconciliation",
            run_id,
            kind="review-report.html",
        )

    def esc(value: object) -> str:
        return html.escape(str(value if value is not None else ""))

    cards: list[str] = []
    for row in rows:
        clauses = (
            "".join(
                f"<blockquote><strong>{esc(item['id'])}</strong><br>{esc(item['text'])}</blockquote>"
                for item in row.get("contract_clauses", [])
            )
            or "<p class='muted'>No source clause is attached to this decision.</p>"
        )
        events = (
            "".join(
                "<li>"
                f"{esc(item['timestamp'])} · {esc(item['source_system'])} · "
                f"{esc(item['event_type'])} · {esc(item['source_record_id'])}"
                "</li>"
                for item in row.get("evidence", [])
            )
            or "<li>No decisive evidence event was required or available.</li>"
        )
        cards.append(
            "<section class='decision'>"
            f"<h2>{esc(row['outcome_id'])} <span class='pill'>{esc(row['status'])}</span></h2>"
            f"<p><strong>Billed:</strong> ${esc(row['billed_amount'])} &nbsp; "
            f"<strong>Payable:</strong> ${esc(row['confirmed_payable_amount'])} &nbsp; "
            f"<strong>Disputed:</strong> ${esc(row['confirmed_disputed_amount'])}</p>"
            f"<p>{esc(row.get('rule_description') or row['reason'])}</p>"
            f"<p class='muted'>Approved rule: {esc(row['rule_id'] or 'settlement default')}</p>"
            "<h3>Contract source</h3>"
            f"{clauses}<h3>Evidence timeline</h3><ul>{events}</ul></section>"
        )
    document = f"""<!doctype html>
<html><head><meta charset="utf-8"><title>Evidue reconciliation {esc(run_id)}</title>
<style>
body{{font:14px/1.5 system-ui,sans-serif;margin:40px auto;max-width:1000px;color:#172033;padding:0 20px}}
h1,h2,h3{{line-height:1.2}} .summary{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}}
.metric,.decision{{border:1px solid #d9e0e8;border-radius:12px;padding:18px;margin:14px 0}} .metric b{{display:block;font-size:22px}}
.muted{{color:#64748b}} blockquote{{margin:10px 0;padding:12px 16px;background:#f8fafc;border-left:4px solid #0f766e}}
.pill{{font-size:12px;border:1px solid #cbd5e1;border-radius:999px;padding:3px 8px;text-transform:uppercase}}
@media print{{body{{margin:0;max-width:none}} .decision{{break-inside:avoid}}}}
</style></head><body>
<h1>Evidue reconciliation review</h1>
<p class="muted">Run {esc(run_id)} · Customer {esc(summary.get("customer"))} · Vendor {esc(summary.get("vendor"))}</p>
<div class="summary">
<div class="metric">Vendor billed<b>${esc(summary["submitted_amount"])}</b></div>
<div class="metric">Verified payable<b>${esc(summary["confirmed_payable_amount"])}</b></div>
<div class="metric">Charges identified for dispute<b>${esc(summary["recommended_deduction"])}</b></div>
<div class="metric">Needs review<b>${esc(summary["needs_review_amount"])}</b></div>
</div>
{"".join(cards)}
<p class="muted">Generated from persisted reconciliation run {esc(run_id)} using approved AIR {esc(summary.get("air_version_id"))}. Needs-review lines are not financial deductions.</p>
</body></html>"""
    return Response(
        document,
        media_type="text/html",
        headers={"Content-Disposition": f'attachment; filename="{run_id}-review-report.html"'},
    )


@router.get("/reconciliations/{run_id}/exports/vendor-email.txt")
def export_vendor_email(run_id: str) -> Response:
    with PilotSessionLocal.begin() as session:
        try:
            summary = reconciliation_summary(session, run_id)
        except LookupError as exc:
            raise HTTPException(404, str(exc)) from exc
        record_audit(
            session,
            "export.generated",
            "reconciliation",
            run_id,
            kind="vendor-email.txt",
        )
    categories = list((summary.get("categories") or {}).values())
    subject = (
        f"Dispute on invoice {summary['invoice_id']} — "
        f"${summary['recommended_deduction']} of ${summary['submitted_amount']}"
    )
    lines = [
        f"Subject: {subject}",
        "",
        f"Hello {summary.get('vendor') or 'vendor team'},",
        "",
        (
            "We reconciled this invoice against the payment terms in our agreement and "
            "the corresponding records in our systems."
        ),
        "",
        f"Invoice: {summary['invoice_id']}",
        f"Vendor billed: ${summary['submitted_amount']}",
        f"Verified payable: ${summary['confirmed_payable_amount']}",
        f"Charges identified for dispute: ${summary['recommended_deduction']}",
        f"Needs review: ${summary['needs_review_amount']}",
        "",
        "Dispute summary:",
    ]
    if categories:
        for item in categories:
            lines.append(f"- {item['count']} claim(s), ${item['amount']}: {item['label']}")
    else:
        lines.append("- No disputed claims were identified.")
    lines.extend(
        [
            "",
            (
                "Detailed disputed line items and contract/evidence references are included "
                "in the accompanying Evidue dispute report."
            ),
            "",
            "Regards,",
            str(summary.get("customer") or "Finance team"),
        ]
    )
    return Response(
        "\n".join(lines),
        media_type="text/plain",
        headers={"Content-Disposition": f'attachment; filename="{run_id}-vendor-email.txt"'},
    )


@router.get("/reconciliations/{run_id}/exports/vendor-dispute.html")
def export_vendor_dispute_report(run_id: str) -> Response:
    with PilotSessionLocal.begin() as session:
        try:
            summary = reconciliation_summary(session, run_id)
            rows = [
                row
                for row in reconciliation_details(session, run_id)
                if row["status"] == "disputed"
            ]
        except LookupError as exc:
            raise HTTPException(404, str(exc)) from exc
        record_audit(
            session,
            "export.generated",
            "reconciliation",
            run_id,
            kind="vendor-dispute.html",
        )

    def esc(value: object) -> str:
        return html.escape(str(value if value is not None else ""))

    grouped = (
        "".join(
            "<tr>"
            f"<td>{esc(item['label'])}</td>"
            f"<td>{esc(item['count'])}</td>"
            f"<td>${esc(item['amount'])}</td>"
            "</tr>"
            for item in (summary.get("categories") or {}).values()
        )
        or "<tr><td colspan='3'>No disputed claims.</td></tr>"
    )
    detail_rows: list[str] = []
    for row in rows:
        source = (
            "<br>".join(esc(item["text"]) for item in row.get("contract_clauses", []))
            or "No source clause attached"
        )
        evidence = (
            "<br>".join(
                f"{esc(item['timestamp'])} · {esc(item['source_system'])} · "
                f"{esc(item['event_type'])} · {esc(item['source_record_id'])}"
                for item in row.get("evidence", [])
            )
            or "No decisive event required or available"
        )
        detail_rows.append(
            "<tr>"
            f"<td>{esc(row['outcome_id'])}</td>"
            f"<td>${esc(row['billed_amount'])}</td>"
            f"<td>${esc(row['confirmed_disputed_amount'])}</td>"
            f"<td>{esc(row.get('rule_description') or row['reason'])}</td>"
            f"<td>{source}</td>"
            f"<td>{evidence}</td>"
            "</tr>"
        )
    period = ""
    if summary.get("billing_period_start") and summary.get("billing_period_end"):
        period = (
            f" · Billing period {esc(summary['billing_period_start'])} through "
            f"{esc(summary['billing_period_end'])}"
        )
    document = f"""<!doctype html>
<html><head><meta charset="utf-8"><title>Evidue dispute report {esc(summary["invoice_id"])}</title>
<style>
body{{font:14px/1.45 system-ui,sans-serif;margin:36px auto;max-width:1200px;color:#172033;padding:0 20px}}
h1,h2{{line-height:1.2}} .muted{{color:#64748b}} .summary{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin:22px 0}}
.metric{{border:1px solid #d9e0e8;border-radius:10px;padding:14px}} .metric b{{display:block;font-size:21px;margin-top:4px}}
table{{width:100%;border-collapse:collapse;margin:14px 0 28px}} th,td{{border:1px solid #d9e0e8;padding:8px;vertical-align:top;text-align:left}} th{{background:#f8fafc}}
.notice{{padding:12px 16px;background:#f8fafc;border-left:4px solid #0f766e}}
@media print{{body{{margin:0;max-width:none}} .summary{{break-inside:avoid}} tr{{break-inside:avoid}}}}
</style></head><body>
<h1>Invoice dispute report</h1>
<p class="muted">{esc(summary.get("customer"))} · {esc(summary.get("vendor"))} · Invoice {esc(summary["invoice_id"])}{period}</p>
<div class="summary">
<div class="metric">Vendor billed<b>${esc(summary["submitted_amount"])}</b></div>
<div class="metric">Verified payable<b>${esc(summary["confirmed_payable_amount"])}</b></div>
<div class="metric">Charges identified for dispute<b>${esc(summary["recommended_deduction"])}</b></div>
<div class="metric">Needs review<b>${esc(summary["needs_review_amount"])}</b></div>
</div>
<p class="notice">We reconciled this invoice against the payment terms in the approved agreement and the corresponding records in the customer's systems. Needs-review amounts are excluded from both payable and disputed totals.</p>
<h2>Dispute summary</h2>
<table><thead><tr><th>Contract rule</th><th>Claims</th><th>Amount</th></tr></thead><tbody>{grouped}</tbody></table>
<h2>Disputed line items</h2>
<table><thead><tr><th>Outcome</th><th>Billed</th><th>Disputed</th><th>Reason</th><th>Contract source</th><th>Evidence</th></tr></thead><tbody>{"".join(detail_rows)}</tbody></table>
<p class="muted">Generated from persisted reconciliation run {esc(run_id)} using approved rule version {esc(summary.get("air_version_id"))}. Engine {esc(summary.get("engine_version"))}.</p>
</body></html>"""
    return Response(
        document,
        media_type="text/html",
        headers={"Content-Disposition": f'attachment; filename="{run_id}-vendor-dispute.html"'},
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


@router.get("/config")
def get_workspace_config() -> dict[str, object]:
    with PilotSessionLocal.begin() as session:
        return workspace_config_view(session)


@router.put("/config")
def put_workspace_config(request: WorkspaceConfigRequest) -> dict[str, object]:
    try:
        with PilotSessionLocal.begin() as session:
            return update_workspace_config(session, request.model_dump())
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.post("/sample/seed")
def seed_sample() -> dict[str, object]:
    from app.upload.sample import seed_sample_workspace

    with PilotSessionLocal.begin() as session:
        return seed_sample_workspace(session)


@router.get("/audit-log")
def get_audit_log(limit: int = Query(100, ge=1, le=500)) -> dict[str, object]:
    with PilotSessionLocal() as session:
        rows = session.scalars(
            select(PilotAuditLogRow).order_by(PilotAuditLogRow.occurred_at.desc()).limit(limit)
        ).all()
        return {
            "events": [
                {
                    "id": row.id,
                    "action": row.action,
                    "object_type": row.object_type,
                    "object_id": row.object_id,
                    "actor": row.actor,
                    "occurred_at": row.occurred_at.isoformat(),
                    "details": row.details,
                }
                for row in rows
            ]
        }


@router.post("/clear")
def clear_pilot() -> dict[str, bool]:
    from app.upload.store import record_audit

    with PilotSessionLocal.begin() as session:
        clear_pilot_data(session)
        record_audit(session, "workspace.cleared", "workspace", None)
    return {"cleared": True}


# ---------------------------------------------------------------------------
# Native AIR compilation and version management
# ---------------------------------------------------------------------------


@router.post("/contracts/{contract_id}/compile-native")
def compile_native_air(
    contract_id: str,
    request: NativeCompileRequest | None = None,
    mode: str = Query("auto", pattern="^(auto|live|recorded)$"),
) -> dict[str, object]:
    """Compile uploaded agreement language into native AIR.

    Live mode calls the configured server-side compiler provider for a strict
    clause-analysis proposal. Recorded mode
    is available only for the bundled demo contract. A caller-supplied proposal
    is accepted for testing, but is still source-bound before lowering.
    """

    from app.agreements.assurance import assure_agreement
    from app.agreements.compiler import lower_to_agreement_ir
    from app.agreements.compiler_models import AgreementCompilationProposal
    from app.agreements.legacy import conformance_report
    from app.agreements.native_compiler import (
        NATIVE_PROMPT_VERSION,
        bind_proposal_to_sources,
        compile_native,
        recorded_native_proposal,
    )
    from app.agreements.providers import canonical_provider_name, provider_is_configured
    from app.contracts.compiler import DEFAULT_CONTRACT_PATH, sha256_text
    from app.upload.agreement_store import (
        agreement_bundle_view,
        effective_source_documents,
        ensure_single_governing_period,
    )
    from app.upload.store import persist_air_version

    with PilotSessionLocal.begin() as session:
        contract = session.get(PilotContractRow, contract_id)
        if contract is None:
            raise HTTPException(404, "Contract not found")
        try:
            ensure_single_governing_period(session, contract.id)
            source_documents = effective_source_documents(
                session,
                contract.id,
                at=contract.period_start,
            )
        except (LookupError, ValueError) as exc:
            raise HTTPException(409, str(exc)) from exc

        bundle_view = agreement_bundle_view(session, contract.id)
        metadata = {
            "customer": contract.customer,
            "vendor": contract.vendor,
            "billing_period_start": contract.period_start.isoformat(),
            "billing_period_end_exclusive": contract.period_end.isoformat(),
            "agreement_documents": json.dumps(bundle_view["documents"], sort_keys=True),
            "agreement_relations": json.dumps(bundle_view["relations"], sort_keys=True),
        }
        manual_proposal = request.proposal if request is not None else None
        secondary_compilation = None
        secondary_compilation_error: str | None = None
        secondary_assurance_provider: str | None = None
        secondary_assurance_model: str | None = None
        compiler_consensus: dict[str, object] | None = None
        if manual_proposal is not None:
            try:
                proposal = AgreementCompilationProposal.model_validate(manual_proposal)
                proposal = bind_proposal_to_sources(
                    proposal,
                    expected_contract_id=contract.id,
                    source_documents=source_documents,
                )
            except Exception as exc:
                raise HTTPException(422, f"Invalid/source-unbound proposal: {exc}") from exc
            compiler_model = proposal.model
            provider = proposal.provider
            prompt_hash = sha256_text("manual-native-proposal")
            live_model_call = False
            raw_response: dict[str, object] = {"manual_proposal": True}
        else:
            primary_provider = os.getenv("EVIDUE_LLM_PRIMARY", "gemini")
            use_live = mode == "live" or (
                mode == "auto" and provider_is_configured(primary_provider)
            )
            try:
                if use_live:
                    result = compile_native(
                        contract_id=contract.id,
                        source_documents=source_documents,
                        metadata=metadata,
                        provider=primary_provider,
                        fallback_provider=os.getenv("EVIDUE_LLM_FALLBACK") or None,
                        pin_provider=False,
                    )
                    secondary_assurance_provider = (
                        os.getenv("EVIDUE_LLM_ASSURANCE_PROVIDER", "").strip() or None
                    )
                    secondary_assurance_model = (
                        os.getenv("EVIDUE_LLM_ASSURANCE_MODEL", "").strip() or None
                    )
                    primary_actual_provider = canonical_provider_name(result.provider)
                    secondary_actual_provider = (
                        canonical_provider_name(secondary_assurance_provider)
                        if secondary_assurance_provider
                        else None
                    )
                    should_assure = bool(
                        secondary_actual_provider
                        and (
                            secondary_actual_provider != primary_actual_provider
                            or (
                                secondary_assurance_model
                                and secondary_assurance_model != result.model
                            )
                        )
                    )
                    if should_assure and secondary_assurance_provider:
                        try:
                            secondary_compilation = compile_native(
                                contract_id=contract.id,
                                source_documents=source_documents,
                                metadata=metadata,
                                provider=secondary_assurance_provider,
                                model=secondary_assurance_model,
                                fallback_provider=None,
                                pin_provider=True,
                            )
                        except (RuntimeError, ValueError) as exc:
                            # The primary result remains a reviewable candidate. A
                            # configured dual-compiler policy fails closed at approval.
                            secondary_compilation_error = str(exc)
                else:
                    if contract.source_text.strip() != DEFAULT_CONTRACT_PATH.read_text().strip():
                        raise ValueError(
                            "Custom agreement packets require server-side LLM inference for native "
                            "compilation; recorded mode is limited to the bundled demo contract"
                        )
                    if len(source_documents) != 1:
                        raise ValueError(
                            "Recorded native mode supports only the bundled single document"
                        )
                    document_id, (title, text) = next(iter(source_documents.items()))
                    result = recorded_native_proposal(
                        contract_id=contract.id,
                        document_id=document_id,
                        title=title,
                        contract_text=text,
                    )
            except (RuntimeError, ValueError) as exc:
                raise HTTPException(422, str(exc)) from exc
            proposal = result.proposal
            compiler_model = result.model
            provider = result.provider
            prompt_hash = result.prompt_hash
            live_model_call = result.live_model_call
            raw_response = result.raw_response

        latest_version = (
            session.scalar(
                select(func.max(PilotRuleCompilationRow.version)).where(
                    PilotRuleCompilationRow.contract_id == contract.id
                )
            )
            or 0
        )
        compilation_id = f"NAIR-{uuid.uuid4().hex.upper()}"
        compilation_version = int(latest_version) + 1
        source_bundle_hash = sha256_text(
            json.dumps(
                {
                    "documents": {
                        doc_id: sha256_text(text) for doc_id, (_, text) in source_documents.items()
                    },
                    "relations": bundle_view["relations"],
                    "effective_at": contract.period_start.isoformat(),
                },
                sort_keys=True,
            )
        )
        try:
            air, conformance = lower_to_agreement_ir(
                proposal,
                compilation_id=compilation_id,
                version=compilation_version,
                source_hash=source_bundle_hash,
            )
        except Exception as exc:
            raise HTTPException(422, f"Native AIR lowering failed: {exc}") from exc

        if secondary_compilation is not None:
            from app.agreements.consensus import (
                compiler_consensus_report,
                consensus_blocking_diagnostic,
            )

            try:
                secondary_air, _ = lower_to_agreement_ir(
                    secondary_compilation.proposal,
                    compilation_id=f"{compilation_id}-ASSURANCE",
                    version=compilation_version,
                    source_hash=source_bundle_hash,
                )
                compiler_consensus = compiler_consensus_report(
                    air,
                    secondary_air,
                    primary_provenance=result.provenance,
                    secondary_provenance=secondary_compilation.provenance,
                )
                consensus_diagnostic = consensus_blocking_diagnostic(compiler_consensus)
                if consensus_diagnostic is not None:
                    air = air.model_copy(
                        update={"diagnostics": [*air.diagnostics, consensus_diagnostic]}
                    )
            except (KeyError, TypeError, ValueError) as exc:
                secondary_compilation_error = (
                    "Independent compiler output could not be lowered/compared: "
                    f"{type(exc).__name__}"
                )

        if secondary_compilation_error and secondary_assurance_provider:
            from app.agreements.consensus import assurance_provider_unavailable_diagnostic

            unavailable = assurance_provider_unavailable_diagnostic(secondary_assurance_provider)
            air = air.model_copy(update={"diagnostics": [*air.diagnostics, unavailable]})
            compiler_consensus = {
                "version": "compiler-consensus-1",
                "status": "assurance_provider_unavailable",
                "agreed": False,
                "approval_blocked": True,
                "provider": secondary_assurance_provider,
                "model": secondary_assurance_model,
                "error": secondary_compilation_error,
            }

        if compiler_consensus is not None:
            raw_response = {**raw_response, "compiler_consensus": compiler_consensus}
        conformance = conformance_report(air)

        compilation_row = PilotRuleCompilationRow(
            id=compilation_id,
            contract_id=contract.id,
            source_document="agreement-bundle",
            source_hash=source_bundle_hash,
            prompt_hash=prompt_hash,
            provider=provider,
            model=compiler_model,
            compiler_version=proposal.compiler_version,
            status="native_air_pending",
            version=compilation_version,
            live_model_call=live_model_call,
            created_at=_now(),
            approved_at=None,
            rules=[],
            raw_response={
                **raw_response,
                "native_proposal": proposal.model_dump(mode="json"),
                "agreement_ir": air.model_dump(mode="json"),
                "conformance": conformance.model_dump(mode="json"),
            },
        )
        session.add(compilation_row)
        session.flush()
        air_row = persist_air_version(
            session,
            contract_id=contract.id,
            compilation_id=compilation_id,
            air=air,
            compiler_mode="native_live" if live_model_call else "native_recorded",
            source_hash=source_bundle_hash,
            compiler_model=compiler_model,
            prompt_version=NATIVE_PROMPT_VERSION,
        )
        blocking = [item for item in air.diagnostics if item.severity == "blocking"]
        report = conformance_report(air)
        assurance = assure_agreement(air)
        return {
            "air_version_id": air_row.id,
            "version_number": air_row.version_number,
            "compiler_mode": air_row.compiler_mode,
            "clauses": len(air.clauses),
            "norms": len(air.norms),
            "proof_requirements": len(air.proof_requirements),
            "settlement_policies": len(air.settlement_policies),
            "blocking_diagnostics": len(blocking),
            "approval_ready": report.approvable and assurance.hard_gate_passed,
            "compiler_consensus": compiler_consensus,
            "assurance": assurance.model_dump(mode="json"),
            "diagnostics": [item.model_dump(mode="json") for item in air.diagnostics],
            "conformance": report.model_dump(mode="json"),
            "agreement_ir": air.model_dump(mode="json"),
        }


@router.get("/air-versions")
def list_air_versions(contract_id: str = Query(...)) -> dict[str, object]:
    with PilotSessionLocal() as session:
        rows = session.scalars(
            select(PilotAIRVersionRow)
            .where(PilotAIRVersionRow.contract_id == contract_id)
            .order_by(PilotAIRVersionRow.version_number.desc())
        ).all()
        return {
            "contract_id": contract_id,
            "versions": [
                {
                    "id": row.id,
                    "version_number": row.version_number,
                    "compiler_mode": row.compiler_mode,
                    "schema_version": row.schema_version,
                    "created_at": row.created_at.isoformat() if row.created_at else None,
                    "approved_at": row.approved_at.isoformat() if row.approved_at else None,
                    "approved_by": row.approved_by,
                    "payload_hash": row.payload_hash,
                    "lifecycle_status": _air_lifecycle(row),
                    "assurance_hard_gate_passed": bool(
                        (row.assurance_json or {}).get("hard_gate_passed", False)
                    ),
                    "superseded_by_id": row.superseded_by_id,
                }
                for row in rows
            ],
        }


@router.get("/air-versions/{version_id}")
def get_air_version(version_id: str) -> dict[str, object]:
    with PilotSessionLocal() as session:
        row = session.get(PilotAIRVersionRow, version_id)
        if row is None:
            raise HTTPException(404, "AIR version not found")
        return {
            "id": row.id,
            "contract_id": row.contract_id,
            "version_number": row.version_number,
            "compiler_mode": row.compiler_mode,
            "schema_version": row.schema_version,
            "source_bundle_hash": row.source_bundle_hash,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "approved_at": row.approved_at.isoformat() if row.approved_at else None,
            "approved_by": row.approved_by,
            "payload_hash": row.payload_hash,
            "lifecycle_status": _air_lifecycle(row),
            "assurance": row.assurance_json,
            "agreement_ir": row.air_json,
            "finance_view": agreement_finance_view(AgreementIR.model_validate(row.air_json)),
        }


@router.get("/air-versions/{version_id}/assurance")
def get_air_assurance(version_id: str) -> dict[str, object]:
    from app.agreements.assurance import assure_agreement

    with PilotSessionLocal.begin() as session:
        row = session.get(PilotAIRVersionRow, version_id)
        if row is None:
            raise HTTPException(404, "AIR version not found")
        agreement = AgreementIR.model_validate(row.air_json)
        assurance = assure_agreement(agreement)
        row.assurance_json = assurance.model_dump(mode="json")
        return assurance.model_dump(mode="json")


@router.get("/air-versions/{version_id}/conformance")
def get_air_conformance(version_id: str) -> dict[str, object]:
    from app.agreements.legacy import conformance_report

    with PilotSessionLocal() as session:
        row = session.get(PilotAIRVersionRow, version_id)
        if row is None:
            raise HTTPException(404, "AIR version not found")
        agreement = AgreementIR.model_validate(row.air_json)
        return conformance_report(agreement).model_dump(mode="json")


@router.get("/air-versions/{version_id}/financial-impact")
def get_air_financial_impact(
    version_id: str,
    invoice_id: str = Query(...),
    baseline_version_id: str | None = Query(None),
) -> dict[str, object]:
    """Preview how a candidate AIR would change one invoice before approval.

    This endpoint never changes financial authority and never invokes an LLM.
    It replays the same accepted claims/evidence through the approved baseline
    and the candidate AIR, returning exact line/totals deltas for human review.
    """

    try:
        with PilotSessionLocal() as session:
            return simulate_air_version_financial_impact(
                session,
                invoice_id=invoice_id,
                candidate_air_version_id=version_id,
                baseline_air_version_id=baseline_version_id,
            )
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


@router.get("/contracts/{contract_id}/historical-replay")
def get_contract_historical_replay(
    contract_id: str,
    air_version_id: str | None = Query(None),
) -> dict[str, object]:
    """Replay uploaded historical invoices without creating financial authority.

    The replay uses an already human-approved AIR and deterministic adjudication.
    It never invokes an LLM and never persists reconciliation runs.
    """

    try:
        with PilotSessionLocal() as session:
            return simulate_contract_historical_replay(
                session,
                contract_id=contract_id,
                air_version_id=air_version_id,
            )
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


@router.get("/contracts/{contract_id}/air-active")
def get_active_air(contract_id: str) -> dict[str, object]:
    from app.agreements.legacy import conformance_report

    with PilotSessionLocal() as session:
        row = session.scalar(
            select(PilotAIRVersionRow).where(
                PilotAIRVersionRow.contract_id == contract_id,
                PilotAIRVersionRow.approved_at.is_not(None),
                PilotAIRVersionRow.superseded_by_id.is_(None),
            )
        )
        if row is None:
            raise HTTPException(404, "No approved AIR version for contract")
        agreement = AgreementIR.model_validate(row.air_json)
        return {
            "version": {
                "id": row.id,
                "version_number": row.version_number,
                "compiler_mode": row.compiler_mode,
                "approved_at": row.approved_at.isoformat() if row.approved_at else None,
                "payload_hash": row.payload_hash,
            },
            "conformance": conformance_report(agreement).model_dump(mode="json"),
        }


@router.post("/air-versions/{version_id}/approve")
def approve_air(version_id: str) -> dict[str, object]:
    from app.upload.store import approve_air_version

    with PilotSessionLocal.begin() as session:
        try:
            row = approve_air_version(session, version_id)
        except LookupError as exc:
            raise HTTPException(404, str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc
        compilation = session.get(PilotRuleCompilationRow, row.compilation_id)
        if compilation is not None:
            compilation.status = "native_air_approved"
            compilation.approved_at = row.approved_at
        return {
            "id": row.id,
            "approved_at": row.approved_at.isoformat() if row.approved_at else None,
            "approved_by": row.approved_by,
            "lifecycle_status": _air_lifecycle(row),
        }


@router.post("/air-versions/{version_id}/verification-plan")
def persist_air_verification_plan(
    version_id: str,
    request: VerificationPlanRequest,
) -> dict[str, object]:
    from app.upload.agreement_store import persist_verification_plan, verification_plan_view

    try:
        with PilotSessionLocal.begin() as session:
            row = persist_verification_plan(
                session, air_version_id=version_id, sources=request.sources
            )
            return verification_plan_view(row)
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


@router.post("/air-versions/{version_id}/verification-plan/auto")
def persist_auto_air_verification_plan(
    version_id: str,
    invoice_id: str = Query(...),
) -> dict[str, object]:
    from app.upload.agreement_store import persist_auto_verification_plan, verification_plan_view

    try:
        with PilotSessionLocal.begin() as session:
            row = persist_auto_verification_plan(
                session, air_version_id=version_id, invoice_id=invoice_id
            )
            return verification_plan_view(row)
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


@router.get("/air-versions/{version_id}/verification-plan")
def get_air_verification_plan(version_id: str) -> dict[str, object]:
    from app.upload.agreement_store import latest_verification_plan, verification_plan_view

    with PilotSessionLocal() as session:
        row = latest_verification_plan(session, version_id)
        if row is None:
            raise HTTPException(404, "No verification plan exists for AIR version")
        return verification_plan_view(row)


@router.get("/contracts/{contract_id}/agreement-bundle")
def get_agreement_bundle(contract_id: str) -> dict[str, object]:
    from app.upload.agreement_store import agreement_bundle_view

    try:
        with PilotSessionLocal.begin() as session:
            return agreement_bundle_view(session, contract_id)
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


@router.post("/contracts/{contract_id}/agreement-bundle/documents")
async def upload_agreement_document(
    contract_id: str,
    file: Annotated[UploadFile, File(...)],
    title: str = Query(..., min_length=2, max_length=200),
    document_type: str = Query("agreement", min_length=2, max_length=100),
    effective_from: str = Query(...),
    effective_until: str | None = Query(None),
    precedence: int = Query(0, ge=-1000, le=1000),
) -> dict[str, object]:
    from app.contracts.compiler import sha256_text
    from app.upload.agreement_store import add_agreement_document, agreement_bundle_view

    content = await _read_upload(file)
    filename = _safe_filename(file.filename, "agreement.txt")
    with PilotSessionLocal.begin() as session:
        upload = create_upload(
            session,
            "agreement_document",
            filename,
            content,
            content_type=file.content_type,
        )
    try:
        source_text = _extract_contract_text(filename, content)
        start = _parse_iso(effective_from, "effective_from")
        end = _parse_iso(effective_until, "effective_until") if effective_until else None
        with PilotSessionLocal.begin() as session:
            current_upload = session.get(type(upload), upload.id)
            if current_upload is None:
                raise RuntimeError("Upload record disappeared")
            add_agreement_document(
                session,
                contract_id=contract_id,
                upload_id=current_upload.id,
                title=title,
                document_type=document_type,
                filename=filename,
                effective_from=start,
                effective_until=end,
                precedence=precedence,
                source_hash=sha256_text(source_text),
                source_text=source_text,
            )
            current_upload.status = "complete"
            current_upload.rows_parsed = 1
            current_upload.rows_accepted = 1
            return agreement_bundle_view(session, contract_id)
    except (LookupError, RuntimeError, ValueError) as exc:
        _mark_upload_failed(type(upload), upload.id, str(exc))
        status = 404 if isinstance(exc, LookupError) else 422
        raise HTTPException(status, str(exc)) from exc


@router.post("/contracts/{contract_id}/agreement-bundle/relations")
def create_agreement_relation(
    contract_id: str,
    request: AgreementRelationRequest,
) -> dict[str, object]:
    from app.upload.agreement_store import add_document_relation, agreement_bundle_view

    try:
        with PilotSessionLocal.begin() as session:
            add_document_relation(
                session,
                contract_id=contract_id,
                source_document_id=request.source_document_id,
                target_document_id=request.target_document_id,
                relation=request.relation,
            )
            return agreement_bundle_view(session, contract_id)
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.post("/invoices/{invoice_id}/facts/derive")
def derive_invoice_facts(invoice_id: str, air_version_id: str = Query(...)) -> dict[str, object]:
    from app.upload.agreement_store import derive_and_persist_facts, facts_view

    try:
        with PilotSessionLocal.begin() as session:
            rows = derive_and_persist_facts(
                session,
                invoice_id=invoice_id,
                air_version_id=air_version_id,
            )
            return {
                "invoice_id": invoice_id,
                "air_version_id": air_version_id,
                "facts": facts_view(rows),
            }
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


@router.post("/invoices/{invoice_id}/semantic-facts/extract")
def extract_semantic_fact(
    invoice_id: str,
    request: SemanticFactExtractionRequest,
) -> dict[str, object]:
    """Extract one narrow model-assisted fact without affecting settlement."""

    if os.getenv("EVIDUE_SEMANTIC_FACT_ENABLED", "false").lower() != "true":
        raise HTTPException(409, "Semantic fact extraction is disabled")

    from app.agreements.models import EvidenceAuthority
    from app.agreements.semantic import GeminiSemanticFactExtractor, SemanticFactRequest
    from app.upload.agreement_store import facts_view

    with PilotSessionLocal.begin() as session:
        invoice = session.get(PilotInvoiceRow, invoice_id)
        if invoice is None:
            raise HTTPException(404, "Invoice not found")
        air = session.get(PilotAIRVersionRow, request.air_version_id)
        if air is None or air.approved_at is None or air.contract_id != invoice.contract_id:
            raise HTTPException(409, "Semantic facts require the invoice's approved AIR version")
        claim = session.get(PilotClaimRow, request.claim_id)
        if claim is None or claim.invoice_id != invoice_id:
            raise HTTPException(404, "Claim not found for invoice")
        rows = session.scalars(
            select(PilotRawRecordRow).where(PilotRawRecordRow.id.in_(request.raw_record_ids))
        ).all()
        by_id = {row.id: row for row in rows if row.invoice_id == invoice_id}
        if set(by_id) != set(request.raw_record_ids):
            raise HTTPException(422, "Every semantic artifact must belong to the invoice")
        artifacts = {
            record_id: json.dumps(by_id[record_id].raw_payload, sort_keys=True, default=str)
            for record_id in request.raw_record_ids
        }
        semantic_request = SemanticFactRequest(
            fact_type=request.fact_type,
            question=request.question,
            artifact_ids=request.raw_record_ids,
        )
        try:
            result = GeminiSemanticFactExtractor().extract(semantic_request, artifacts)
        except (RuntimeError, ValueError) as exc:
            raise HTTPException(422, str(exc)) from exc
        fact = PilotFactRow(
            id=f"PFACT-{uuid.uuid4().hex.upper()}",
            invoice_id=invoice_id,
            claim_id=claim.id,
            air_version_id=air.id,
            fact_type=result.fact_type,
            truth=result.truth.value,
            value=None,
            evidence_ids=[citation.artifact_id for citation in result.citations],
            authority=EvidenceAuthority.MODEL_DERIVED.value,
            derivation_method="model_assisted_semantic_extraction",
            evaluator_version=result.model,
            model_name=result.model,
            prompt_version=result.prompt_version,
            confidence=result.confidence,
            explanation=result.explanation,
            input_hash=result.input_hash,
            created_at=_now(),
            review_status="pending",
        )
        session.add(fact)
        session.flush()
        for evidence_id in fact.evidence_ids:
            session.add(
                PilotProvenanceEdgeRow(
                    id=f"PPROV-{uuid.uuid4().hex.upper()}",
                    invoice_id=invoice_id,
                    source_id=evidence_id,
                    target_id=fact.id,
                    relation="supports",
                    created_at=_now(),
                )
            )
        return {"fact": facts_view([fact])[0], "financial_effect": "none_until_review"}


@router.post("/facts/{fact_id}/review")
def review_fact(fact_id: str, request: FactReviewRequest) -> dict[str, object]:
    """Record human review without overwriting the originally derived fact."""

    from app.upload.agreement_store import facts_view

    with PilotSessionLocal.begin() as session:
        fact = session.get(PilotFactRow, fact_id)
        if fact is None:
            raise HTTPException(404, "Fact not found")
        fact.reviewed_truth = request.truth
        fact.review_rationale = request.rationale.strip()
        fact.reviewed_by = request.reviewed_by.strip()
        fact.reviewed_at = _now()
        fact.review_status = "reviewed"
        session.flush()
        return {"fact": facts_view([fact])[0]}


@router.get("/invoices/{invoice_id}/facts")
def get_invoice_facts(
    invoice_id: str, air_version_id: str | None = Query(None)
) -> dict[str, object]:
    from app.upload.agreement_store import facts_view

    with PilotSessionLocal() as session:
        statement = select(PilotFactRow).where(PilotFactRow.invoice_id == invoice_id)
        if air_version_id:
            statement = statement.where(PilotFactRow.air_version_id == air_version_id)
        rows = session.scalars(statement.order_by(PilotFactRow.created_at, PilotFactRow.id)).all()
        return {"invoice_id": invoice_id, "facts": facts_view(rows)}


@router.get("/contracts/{contract_id}/conformance")
def get_conformance_report(contract_id: str) -> dict[str, object]:
    """Legacy compiler conformance retained for backwards compatibility."""
    with PilotSessionLocal() as session:
        contract = session.get(PilotContractRow, contract_id)
        if contract is None:
            raise HTTPException(404, "Contract not found")
        if not contract.active_compilation_id:
            raise HTTPException(404, "No active legacy compilation")
        compilation = session.get(PilotRuleCompilationRow, contract.active_compilation_id)
        if compilation is None:
            raise HTTPException(404, "Legacy compilation not found")
        raw = (compilation.raw_response or {}).get("conformance")
        if raw is None:
            raise HTTPException(404, "No legacy conformance report available")
        return {"compiler_path": "legacy", "conformance": raw}
