"""Authenticated finance-product API.

This router intentionally lives beside, not inside, the agreement compiler.  It
turns qualified kernel output into recurring Finance operations while preserving
immutable machine determinations.
"""

from __future__ import annotations

import html
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel, Field

from app.product.models import ProductDisputeCaseRow
from app.product.pdf import render_dispute_pdf
from app.product.store import (
    active_air_for_run,
    approve_reconciliation,
    assign_review_case,
    bootstrap_product,
    create_dispute_case,
    decide_review_case,
    dispute_case_view,
    get_statement,
    list_dispute_cases,
    list_invoices,
    list_review_cases,
    list_vendors,
    product_overview,
    update_dispute_case,
)
from app.upload.auth import current_actor, require_pilot_access
from app.upload.pilot_db import PilotSessionLocal

router = APIRouter(
    prefix="/api/pilot/product",
    tags=["product"],
    dependencies=[Depends(require_pilot_access)],
)


class ReviewDecisionRequest(BaseModel):
    decision: Literal["payable", "disputed", "escalated"]
    rationale: str = Field(min_length=3, max_length=4000)
    decided_by: str = Field(default="", max_length=200)


class ReviewAssignmentRequest(BaseModel):
    assigned_to: str | None = Field(default=None, max_length=200)


class ApprovalRequest(BaseModel):
    approved_by: str = Field(default="", max_length=200)
    note: str = Field(default="", max_length=4000)


class CreateDisputeRequest(BaseModel):
    created_by: str = Field(default="", max_length=200)
    subject: str | None = Field(default=None, max_length=500)


class DisputeTransitionRequest(BaseModel):
    status: Literal[
        "draft",
        "ready",
        "sent",
        "vendor_responded",
        "under_review",
        "accepted",
        "partially_accepted",
        "rejected",
        "closed",
    ]
    vendor_response: str | None = Field(default=None, max_length=20_000)


def _not_found(exc: LookupError) -> HTTPException:
    return HTTPException(status_code=404, detail=str(exc))


def _invalid(exc: ValueError) -> HTTPException:
    return HTTPException(status_code=409, detail=str(exc))


@router.post("/bootstrap")
def bootstrap() -> dict[str, object]:
    with PilotSessionLocal.begin() as session:
        return {"productized": True, **bootstrap_product(session)}


@router.get("/overview")
def overview() -> dict[str, object]:
    with PilotSessionLocal.begin() as session:
        return product_overview(session)


@router.get("/vendors")
def vendors() -> dict[str, object]:
    with PilotSessionLocal.begin() as session:
        items = list_vendors(session)
        return {"total": len(items), "items": items}


@router.get("/invoices")
def invoices(engagement_id: str | None = Query(default=None)) -> dict[str, object]:
    with PilotSessionLocal.begin() as session:
        items = list_invoices(session, engagement_id)
        return {"total": len(items), "items": items}


@router.get("/review-cases")
def review_cases(
    status: str | None = Query(default=None), run_id: str | None = Query(default=None)
) -> dict[str, object]:
    with PilotSessionLocal.begin() as session:
        items = list_review_cases(session, status=status, run_id=run_id)
        return {"total": len(items), "items": items}


@router.post("/review-cases/{review_case_id}/assign")
def assign_review(review_case_id: str, request: ReviewAssignmentRequest) -> dict[str, object]:
    try:
        with PilotSessionLocal.begin() as session:
            return assign_review_case(session, review_case_id, assigned_to=request.assigned_to)
    except LookupError as exc:
        raise _not_found(exc) from exc


@router.post("/review-cases/{review_case_id}/decision")
def decide_review(review_case_id: str, request: ReviewDecisionRequest) -> dict[str, object]:
    try:
        with PilotSessionLocal.begin() as session:
            return decide_review_case(
                session,
                review_case_id,
                decision=request.decision,
                rationale=request.rationale,
                decided_by=request.decided_by or current_actor(),
            )
    except LookupError as exc:
        raise _not_found(exc) from exc
    except ValueError as exc:
        raise _invalid(exc) from exc


@router.get("/reconciliations/{run_id}/statement")
def reconciliation_statement(run_id: str) -> dict[str, object]:
    try:
        with PilotSessionLocal.begin() as session:
            return get_statement(session, run_id)
    except LookupError as exc:
        raise _not_found(exc) from exc


@router.get("/reconciliations/{run_id}/trust")
def reconciliation_trust(run_id: str) -> dict[str, object]:
    try:
        with PilotSessionLocal.begin() as session:
            statement = get_statement(session, run_id)
            return {
                "run_id": run_id,
                "agreement": active_air_for_run(session, run_id),
                "input_manifest_hash": statement["kernel_input_manifest_hash"],
                "kernel_calculation_hash": statement["kernel_calculation_hash"],
                "settlement_calculation_hash": statement["calculation_hash"],
                "invariant": (
                    "Approved AIR + evidence manifest + deterministic review overlay -> dollars"
                ),
            }
    except LookupError as exc:
        raise _not_found(exc) from exc


@router.post("/reconciliations/{run_id}/approve")
def approve(run_id: str, request: ApprovalRequest) -> dict[str, object]:
    try:
        with PilotSessionLocal.begin() as session:
            approval = approve_reconciliation(
                session,
                run_id,
                approved_by=request.approved_by or current_actor(),
                note=request.note,
            )
            return {"approval": approval, "statement": get_statement(session, run_id)}
    except LookupError as exc:
        raise _not_found(exc) from exc
    except ValueError as exc:
        raise _invalid(exc) from exc


@router.get("/disputes")
def disputes() -> dict[str, object]:
    with PilotSessionLocal.begin() as session:
        items = list_dispute_cases(session)
        return {"total": len(items), "items": items}


@router.post("/reconciliations/{run_id}/disputes")
def create_dispute(run_id: str, request: CreateDisputeRequest) -> dict[str, object]:
    try:
        with PilotSessionLocal.begin() as session:
            return create_dispute_case(
                session,
                run_id,
                created_by=request.created_by or current_actor(),
                subject=request.subject,
            )
    except LookupError as exc:
        raise _not_found(exc) from exc
    except ValueError as exc:
        raise _invalid(exc) from exc


@router.get("/disputes/{dispute_case_id}")
def dispute(dispute_case_id: str) -> dict[str, object]:
    with PilotSessionLocal.begin() as session:
        row = session.get(ProductDisputeCaseRow, dispute_case_id)
        if row is None:
            raise HTTPException(status_code=404, detail="Dispute case not found")
        return dispute_case_view(session, row)


@router.post("/disputes/{dispute_case_id}/transition")
def transition_dispute(
    dispute_case_id: str, request: DisputeTransitionRequest
) -> dict[str, object]:
    try:
        with PilotSessionLocal.begin() as session:
            return update_dispute_case(
                session,
                dispute_case_id,
                status=request.status,
                vendor_response=request.vendor_response,
            )
    except LookupError as exc:
        raise _not_found(exc) from exc
    except ValueError as exc:
        raise _invalid(exc) from exc


@router.get("/disputes/{dispute_case_id}/print.html")
def printable_dispute(dispute_case_id: str) -> Response:
    with PilotSessionLocal.begin() as session:
        row = session.get(ProductDisputeCaseRow, dispute_case_id)
        if row is None:
            raise HTTPException(status_code=404, detail="Dispute case not found")
        payload = dispute_case_view(session, row)
        items = "".join(
            "<tr>"
            f"<td>{html.escape(str(item['outcome_id']))}</td>"
            f"<td>{html.escape(str(item['reason_code']))}</td>"
            f"<td>{html.escape(str(item['reason']))}</td>"
            f"<td style='text-align:right'>${html.escape(str(item['amount']))}</td>"
            "</tr>"
            for item in payload["items"]
        )
        case_number = html.escape(str(payload["case_number"]))
        status = html.escape(str(payload["status"]))
        subject = html.escape(str(payload["subject"]))
        disputed_amount = html.escape(str(payload["disputed_amount"]))
        run_id = html.escape(str(payload["run_id"]))
        approval_id = html.escape(str(payload["approval_id"]))
        body = f"""<!doctype html>
<html>
<head>
<meta charset='utf-8'>
<title>{case_number}</title>
<style>
body{{font-family:Arial,sans-serif;margin:40px;color:#17202a}}
h1{{margin-bottom:4px}}
.meta{{color:#566573;margin-bottom:28px}}
table{{width:100%;border-collapse:collapse;margin-top:24px}}
th,td{{padding:9px;border-bottom:1px solid #ddd;text-align:left;font-size:12px}}
.total{{font-size:22px;font-weight:700}}
@media print{{body{{margin:18mm}}}}
</style>
</head>
<body>
<h1>Evidue vendor dispute package</h1>
<div class='meta'>{case_number} · {status}</div>
<h2>{subject}</h2>
<p class='total'>Disputed amount: ${disputed_amount}</p>
<p>
This package records deterministic invoice findings and any reviewed exceptions
included in the approved settlement.
</p>
<table>
<thead><tr><th>Outcome</th><th>Reason code</th><th>Finding</th><th>Amount</th></tr></thead>
<tbody>{items}</tbody>
</table>
<p class='meta'>Run: {run_id} · Approval: {approval_id}</p>
</body>
</html>"""
        return Response(content=body, media_type="text/html")


@router.get("/disputes/{dispute_case_id}/package.pdf")
def dispute_pdf(dispute_case_id: str) -> Response:
    with PilotSessionLocal.begin() as session:
        row = session.get(ProductDisputeCaseRow, dispute_case_id)
        if row is None:
            raise HTTPException(status_code=404, detail="Dispute case not found")
        payload = dispute_case_view(session, row)
        content = render_dispute_pdf(payload)
        return Response(
            content=content,
            media_type="application/pdf",
            headers={
                "Content-Disposition": (
                    f'attachment; filename="{payload["case_number"]}-dispute.pdf"'
                )
            },
        )
