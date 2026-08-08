"""Finance-product services layered over the qualified Evidue kernel.

The kernel remains the financial authority for machine determinations.  This
module adds the recurring operational objects Finance needs around those
immutable results: vendors, review cases, settlement statements, approvals,
and dispute cases.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.product.models import (
    ProductApprovalRow,
    ProductDisputeCaseRow,
    ProductDisputeItemRow,
    ProductEngagementContractRow,
    ProductEngagementInvoiceRow,
    ProductOrganizationRow,
    ProductReconciliationStatementRow,
    ProductReviewCaseRow,
    ProductReviewDecisionRow,
    ProductVendorEngagementRow,
    ProductVendorRow,
)
from app.upload.auth import current_actor
from app.upload.models import (
    PilotAIRVersionRow,
    PilotContractRow,
    PilotDeterminationRow,
    PilotInvoiceRow,
    PilotReconciliationRunRow,
    PilotWorkspaceConfigRow,
)
from app.upload.store import record_audit

ZERO = Decimal("0.00")
REVIEW_DECISIONS = {"payable", "disputed", "escalated"}
DISPUTE_TRANSITIONS: dict[str, set[str]] = {
    "draft": {"ready", "closed"},
    "ready": {"sent", "draft", "closed"},
    "sent": {"vendor_responded", "under_review", "closed"},
    "vendor_responded": {"under_review", "accepted", "partially_accepted", "rejected", "closed"},
    "under_review": {"accepted", "partially_accepted", "rejected", "closed"},
    "accepted": {"closed"},
    "partially_accepted": {"closed", "under_review"},
    "rejected": {"closed", "under_review"},
    "closed": set(),
}


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:16].upper()}"


def _money(value: Decimal | float | str | None) -> str:
    return f"{Decimal(value or ZERO):.2f}"


def _normalized_name(value: str) -> str:
    return " ".join(value.casefold().split())


def _hash_json(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    return hashlib.sha256(encoded).hexdigest()


def ensure_organization(session: Session) -> ProductOrganizationRow:
    existing = session.scalar(select(ProductOrganizationRow).limit(1))
    config = session.get(PilotWorkspaceConfigRow, 1)
    first_contract = session.scalar(select(PilotContractRow).order_by(PilotContractRow.created_at))
    name = (
        (config.company_name.strip() if config and config.company_name else "")
        or (first_contract.customer.strip() if first_contract else "")
        or "Evidue workspace"
    )
    currency = (config.default_currency if config else "USD") or "USD"
    timezone = (config.timezone if config else "UTC") or "UTC"
    if existing is not None:
        changed = False
        if existing.name == "Evidue workspace" and name != existing.name:
            existing.name = name
            changed = True
        if existing.currency != currency:
            existing.currency = currency
            changed = True
        if existing.timezone != timezone:
            existing.timezone = timezone
            changed = True
        if changed:
            existing.updated_at = _now()
        return existing
    row = ProductOrganizationRow(
        id=_id("ORG"),
        name=name,
        currency=currency,
        timezone=timezone,
        created_at=_now(),
        updated_at=_now(),
    )
    session.add(row)
    session.flush()
    record_audit(session, "organization.created", "organization", row.id, name=row.name)
    return row


def ensure_vendor_engagement_for_contract(
    session: Session, contract: PilotContractRow
) -> ProductVendorEngagementRow:
    linked = session.scalar(
        select(ProductEngagementContractRow).where(
            ProductEngagementContractRow.contract_id == contract.id
        )
    )
    if linked is not None:
        engagement = session.get(ProductVendorEngagementRow, linked.engagement_id)
        if engagement is None:
            raise RuntimeError("Product engagement link points to a missing engagement")
        return engagement

    organization = ensure_organization(session)
    normalized = _normalized_name(contract.vendor)
    vendor = session.scalar(
        select(ProductVendorRow).where(ProductVendorRow.normalized_name == normalized)
    )
    if vendor is None:
        vendor = ProductVendorRow(
            id=_id("VEN"),
            name=contract.vendor.strip(),
            normalized_name=normalized,
            created_at=_now(),
        )
        session.add(vendor)
        session.flush()
        record_audit(session, "vendor.created", "vendor", vendor.id, name=vendor.name)

    engagement = session.scalar(
        select(ProductVendorEngagementRow).where(
            ProductVendorEngagementRow.organization_id == organization.id,
            ProductVendorEngagementRow.vendor_id == vendor.id,
        )
    )
    if engagement is None:
        engagement = ProductVendorEngagementRow(
            id=_id("ENG"),
            organization_id=organization.id,
            vendor_id=vendor.id,
            display_name=vendor.name,
            status="active",
            created_at=_now(),
            updated_at=_now(),
        )
        session.add(engagement)
        session.flush()
        record_audit(
            session,
            "vendor_engagement.created",
            "vendor_engagement",
            engagement.id,
            vendor_id=vendor.id,
            vendor=vendor.name,
        )

    session.add(
        ProductEngagementContractRow(
            id=_id("ECL"),
            engagement_id=engagement.id,
            contract_id=contract.id,
            created_at=_now(),
        )
    )
    session.flush()
    return engagement


def ensure_invoice_link(session: Session, invoice: PilotInvoiceRow) -> ProductEngagementInvoiceRow:
    existing = session.scalar(
        select(ProductEngagementInvoiceRow).where(
            ProductEngagementInvoiceRow.invoice_id == invoice.id
        )
    )
    if existing is not None:
        return existing
    contract = session.get(PilotContractRow, invoice.contract_id)
    if contract is None:
        raise LookupError("Invoice contract not found")
    engagement = ensure_vendor_engagement_for_contract(session, contract)
    link = ProductEngagementInvoiceRow(
        id=_id("EIL"),
        engagement_id=engagement.id,
        invoice_id=invoice.id,
        created_at=_now(),
    )
    session.add(link)
    session.flush()
    return link


def _review_reason_code(determination: PilotDeterminationRow) -> str:
    if determination.rule_id:
        return determination.rule_id
    reason = determination.reason.casefold()
    if "missing" in reason or "coverage" in reason:
        return "MISSING_EVIDENCE"
    if "match" in reason or "identity" in reason:
        return "AMBIGUOUS_IDENTITY"
    if "conflict" in reason:
        return "CONFLICTING_EVIDENCE"
    return "NEEDS_REVIEW"


def _review_priority(amount: Decimal) -> str:
    if amount >= Decimal(5000):
        return "critical"
    if amount >= Decimal(1000):
        return "high"
    if amount >= Decimal(100):
        return "normal"
    return "low"


def ensure_review_cases_for_run(session: Session, run_id: str) -> list[ProductReviewCaseRow]:
    run = session.get(PilotReconciliationRunRow, run_id)
    if run is None:
        raise LookupError("Reconciliation run not found")
    determinations = session.scalars(
        select(PilotDeterminationRow)
        .where(
            PilotDeterminationRow.run_id == run_id,
            PilotDeterminationRow.status == "needs_review",
        )
        .order_by(PilotDeterminationRow.external_outcome_id)
    ).all()
    created: list[ProductReviewCaseRow] = []
    for determination in determinations:
        existing = session.scalar(
            select(ProductReviewCaseRow).where(
                ProductReviewCaseRow.determination_id == determination.id
            )
        )
        if existing is not None:
            created.append(existing)
            continue
        amount = Decimal(determination.needs_review_amount or determination.billed_amount or ZERO)
        case = ProductReviewCaseRow(
            id=_id("REV"),
            run_id=run_id,
            determination_id=determination.id,
            external_outcome_id=determination.external_outcome_id,
            reason_code=_review_reason_code(determination),
            reason=determination.reason,
            exposure_amount=amount,
            priority=_review_priority(amount),
            status="open",
            assigned_to=None,
            created_at=_now(),
            updated_at=_now(),
            resolved_at=None,
        )
        session.add(case)
        created.append(case)
        record_audit(
            session,
            "review_case.created",
            "review_case",
            case.id,
            run_id=run_id,
            outcome_id=case.external_outcome_id,
            exposure_amount=_money(amount),
            reason_code=case.reason_code,
        )
    session.flush()
    return created


def _latest_decision(session: Session, review_case_id: str) -> ProductReviewDecisionRow | None:
    return session.scalar(
        select(ProductReviewDecisionRow)
        .where(ProductReviewDecisionRow.review_case_id == review_case_id)
        .order_by(ProductReviewDecisionRow.sequence.desc())
    )


def _run_calculation_hash(session: Session, run: PilotReconciliationRunRow) -> str:
    existing = getattr(run, "calculation_hash", None)
    if existing:
        return str(existing)
    determinations = session.scalars(
        select(PilotDeterminationRow)
        .where(PilotDeterminationRow.run_id == run.id)
        .order_by(PilotDeterminationRow.external_outcome_id)
    ).all()
    return _hash_json(
        {
            "invoice_id": run.invoice_id,
            "air_version_id": run.air_version_id,
            "engine_version": run.engine_version,
            "rule_program_version": run.rule_program_version,
            "determinations": [
                {
                    "outcome_id": item.external_outcome_id,
                    "status": item.status,
                    "rule_id": item.rule_id,
                    "payable": _money(item.confirmed_payable_amount),
                    "disputed": _money(item.confirmed_disputed_amount),
                    "review": _money(item.needs_review_amount),
                }
                for item in determinations
            ],
        }
    )


def refresh_statement(session: Session, run_id: str) -> ProductReconciliationStatementRow:
    run = session.get(PilotReconciliationRunRow, run_id)
    if run is None:
        raise LookupError("Reconciliation run not found")
    ensure_review_cases_for_run(session, run_id)
    review_cases = session.scalars(
        select(ProductReviewCaseRow).where(ProductReviewCaseRow.run_id == run_id)
    ).all()
    resolved_payable = ZERO
    resolved_disputed = ZERO
    open_amount = ZERO
    decisions_for_hash: list[dict[str, object]] = []
    for case in review_cases:
        decision = _latest_decision(session, case.id)
        if decision is None or decision.decision == "escalated":
            open_amount += Decimal(case.exposure_amount)
            if decision is not None:
                decisions_for_hash.append(
                    {"case": case.id, "sequence": decision.sequence, "decision": decision.decision}
                )
            continue
        amount = Decimal(case.exposure_amount)
        if decision.decision == "payable":
            resolved_payable += amount
        elif decision.decision == "disputed":
            resolved_disputed += amount
        decisions_for_hash.append(
            {"case": case.id, "sequence": decision.sequence, "decision": decision.decision}
        )

    machine_payable = Decimal(run.confirmed_payable_amount)
    machine_disputed = Decimal(run.recommended_deduction)
    review_amount = Decimal(run.needs_review_amount)
    final_payable = machine_payable + resolved_payable
    final_disputed = machine_disputed + resolved_disputed
    calculation_hash = _hash_json(
        {
            "kernel_calculation_hash": _run_calculation_hash(session, run),
            "review_decisions": sorted(decisions_for_hash, key=lambda item: str(item["case"])),
            "final_payable": _money(final_payable),
            "final_disputed": _money(final_disputed),
            "open_review": _money(open_amount),
        }
    )
    row = session.scalar(
        select(ProductReconciliationStatementRow).where(
            ProductReconciliationStatementRow.run_id == run_id
        )
    )
    approved = session.scalar(select(ProductApprovalRow).where(ProductApprovalRow.run_id == run_id))
    status = "approved" if approved else ("ready" if open_amount == ZERO else "draft")
    if row is None:
        row = ProductReconciliationStatementRow(
            id=_id("STM"),
            run_id=run_id,
            submitted_amount=run.submitted_amount,
            machine_payable_amount=machine_payable,
            machine_disputed_amount=machine_disputed,
            review_amount=review_amount,
            review_resolved_payable_amount=resolved_payable,
            review_resolved_disputed_amount=resolved_disputed,
            open_review_amount=open_amount,
            recommended_final_payable_amount=final_payable,
            recommended_final_disputed_amount=final_disputed,
            status=status,
            calculation_hash=calculation_hash,
            created_at=_now(),
            updated_at=_now(),
        )
        session.add(row)
    elif approved is None:
        row.review_resolved_payable_amount = resolved_payable
        row.review_resolved_disputed_amount = resolved_disputed
        row.open_review_amount = open_amount
        row.recommended_final_payable_amount = final_payable
        row.recommended_final_disputed_amount = final_disputed
        row.status = status
        row.calculation_hash = calculation_hash
        row.updated_at = _now()
    session.flush()
    return row


def bootstrap_product(session: Session) -> dict[str, int | str]:
    organization = ensure_organization(session)
    contracts = session.scalars(
        select(PilotContractRow).order_by(PilotContractRow.created_at)
    ).all()
    for contract in contracts:
        ensure_vendor_engagement_for_contract(session, contract)
    invoices = session.scalars(select(PilotInvoiceRow).order_by(PilotInvoiceRow.created_at)).all()
    for invoice in invoices:
        ensure_invoice_link(session, invoice)
    runs = session.scalars(
        select(PilotReconciliationRunRow).order_by(PilotReconciliationRunRow.completed_at)
    ).all()
    for run in runs:
        ensure_review_cases_for_run(session, run.id)
        refresh_statement(session, run.id)
    session.flush()
    return {
        "organization_id": organization.id,
        "vendors": session.scalar(select(func.count()).select_from(ProductVendorRow)) or 0,
        "engagements": session.scalar(select(func.count()).select_from(ProductVendorEngagementRow))
        or 0,
        "invoices": session.scalar(select(func.count()).select_from(ProductEngagementInvoiceRow))
        or 0,
        "reconciliations": len(runs),
        "review_cases": session.scalar(select(func.count()).select_from(ProductReviewCaseRow)) or 0,
    }


def organization_view(row: ProductOrganizationRow) -> dict[str, object]:
    return {
        "id": row.id,
        "name": row.name,
        "currency": row.currency,
        "timezone": row.timezone,
        "created_at": row.created_at.isoformat(),
        "updated_at": row.updated_at.isoformat(),
    }


def _latest_run_for_invoice(session: Session, invoice_id: str) -> PilotReconciliationRunRow | None:
    return session.scalar(
        select(PilotReconciliationRunRow)
        .where(PilotReconciliationRunRow.invoice_id == invoice_id)
        .order_by(PilotReconciliationRunRow.run_number.desc())
    )


def _engagement_vendor(
    session: Session, engagement: ProductVendorEngagementRow
) -> ProductVendorRow:
    vendor = session.get(ProductVendorRow, engagement.vendor_id)
    if vendor is None:
        raise RuntimeError("Vendor engagement points to a missing vendor")
    return vendor


def list_vendors(session: Session) -> list[dict[str, object]]:
    bootstrap_product(session)
    engagements = session.scalars(
        select(ProductVendorEngagementRow).order_by(ProductVendorEngagementRow.display_name)
    ).all()
    result: list[dict[str, object]] = []
    for engagement in engagements:
        vendor = _engagement_vendor(session, engagement)
        contract_ids = list(
            session.scalars(
                select(ProductEngagementContractRow.contract_id).where(
                    ProductEngagementContractRow.engagement_id == engagement.id
                )
            ).all()
        )
        invoice_ids = list(
            session.scalars(
                select(ProductEngagementInvoiceRow.invoice_id).where(
                    ProductEngagementInvoiceRow.engagement_id == engagement.id
                )
            ).all()
        )
        latest_runs = [
            run
            for invoice_id in invoice_ids
            if (run := _latest_run_for_invoice(session, invoice_id))
        ]
        submitted = sum((Decimal(run.submitted_amount) for run in latest_runs), ZERO)
        payable = sum((Decimal(run.confirmed_payable_amount) for run in latest_runs), ZERO)
        disputed = sum((Decimal(run.recommended_deduction) for run in latest_runs), ZERO)
        open_reviews = (
            session.scalar(
                select(func.count())
                .select_from(ProductReviewCaseRow)
                .where(
                    ProductReviewCaseRow.run_id.in_(
                        [run.id for run in latest_runs] or ["__none__"]
                    ),
                    ProductReviewCaseRow.status.in_(["open", "escalated"]),
                )
            )
            or 0
        )
        result.append(
            {
                "id": engagement.id,
                "vendor_id": vendor.id,
                "name": vendor.name,
                "status": engagement.status,
                "contracts": len(contract_ids),
                "invoices": len(invoice_ids),
                "latest_reconciliations": len(latest_runs),
                "submitted_amount": _money(submitted),
                "machine_payable_amount": _money(payable),
                "machine_disputed_amount": _money(disputed),
                "open_review_cases": int(open_reviews),
            }
        )
    return result


def list_invoices(session: Session, engagement_id: str | None = None) -> list[dict[str, object]]:
    bootstrap_product(session)
    query = select(ProductEngagementInvoiceRow).order_by(
        ProductEngagementInvoiceRow.created_at.desc()
    )
    if engagement_id:
        query = query.where(ProductEngagementInvoiceRow.engagement_id == engagement_id)
    links = session.scalars(query).all()
    result: list[dict[str, object]] = []
    for link in links:
        invoice = session.get(PilotInvoiceRow, link.invoice_id)
        engagement = session.get(ProductVendorEngagementRow, link.engagement_id)
        if invoice is None or engagement is None:
            continue
        vendor = _engagement_vendor(session, engagement)
        run = _latest_run_for_invoice(session, invoice.id)
        statement = refresh_statement(session, run.id) if run else None
        result.append(
            {
                "invoice_id": invoice.id,
                "engagement_id": engagement.id,
                "vendor": vendor.name,
                "billing_period_start": invoice.billing_period_start.isoformat(),
                "billing_period_end": invoice.billing_period_end.isoformat(),
                "submitted_at": invoice.submitted_at.isoformat(),
                "latest_run_id": run.id if run else None,
                "run_number": run.run_number if run else None,
                "submitted_amount": _money(run.submitted_amount) if run else None,
                "recommended_payable_amount": (
                    _money(statement.recommended_final_payable_amount) if statement else None
                ),
                "disputed_amount": (
                    _money(statement.recommended_final_disputed_amount) if statement else None
                ),
                "open_review_amount": _money(statement.open_review_amount) if statement else None,
                "statement_status": statement.status if statement else "not_reconciled",
            }
        )
    return result


def review_case_view(session: Session, row: ProductReviewCaseRow) -> dict[str, object]:
    determination = session.get(PilotDeterminationRow, row.determination_id)
    decision = _latest_decision(session, row.id)
    return {
        "id": row.id,
        "run_id": row.run_id,
        "determination_id": row.determination_id,
        "outcome_id": row.external_outcome_id,
        "reason_code": row.reason_code,
        "reason": row.reason,
        "exposure_amount": _money(row.exposure_amount),
        "priority": row.priority,
        "status": row.status,
        "assigned_to": row.assigned_to,
        "machine_status": determination.status if determination else "needs_review",
        "machine_rule_id": determination.rule_id if determination else None,
        "created_at": row.created_at.isoformat(),
        "updated_at": row.updated_at.isoformat(),
        "resolved_at": row.resolved_at.isoformat() if row.resolved_at else None,
        "latest_decision": (
            {
                "id": decision.id,
                "decision": decision.decision,
                "rationale": decision.rationale,
                "decided_by": decision.decided_by,
                "decided_at": decision.decided_at.isoformat(),
                "sequence": decision.sequence,
            }
            if decision
            else None
        ),
    }


def list_review_cases(
    session: Session, *, status: str | None = None, run_id: str | None = None
) -> list[dict[str, object]]:
    bootstrap_product(session)
    query = select(ProductReviewCaseRow).order_by(
        ProductReviewCaseRow.created_at.desc(), ProductReviewCaseRow.external_outcome_id
    )
    if status:
        query = query.where(ProductReviewCaseRow.status == status)
    if run_id:
        query = query.where(ProductReviewCaseRow.run_id == run_id)
    return [review_case_view(session, row) for row in session.scalars(query).all()]


def decide_review_case(
    session: Session,
    review_case_id: str,
    *,
    decision: str,
    rationale: str,
    decided_by: str,
) -> dict[str, object]:
    if decision not in REVIEW_DECISIONS:
        raise ValueError(f"Unsupported review decision: {decision}")
    row = session.get(ProductReviewCaseRow, review_case_id)
    if row is None:
        raise LookupError("Review case not found")
    if session.scalar(select(ProductApprovalRow).where(ProductApprovalRow.run_id == row.run_id)):
        raise ValueError("Approved reconciliation decisions are immutable")
    sequence = (
        session.scalar(
            select(func.max(ProductReviewDecisionRow.sequence)).where(
                ProductReviewDecisionRow.review_case_id == row.id
            )
        )
        or 0
    ) + 1
    decision_row = ProductReviewDecisionRow(
        id=_id("RVD"),
        review_case_id=row.id,
        decision=decision,
        rationale=rationale.strip(),
        decided_by=decided_by.strip() or current_actor(),
        decided_at=_now(),
        sequence=sequence,
    )
    session.add(decision_row)
    row.status = "escalated" if decision == "escalated" else f"resolved_{decision}"
    row.updated_at = _now()
    row.resolved_at = None if decision == "escalated" else _now()
    record_audit(
        session,
        "review_case.decided",
        "review_case",
        row.id,
        run_id=row.run_id,
        decision=decision,
        rationale=rationale,
        sequence=sequence,
    )
    statement = refresh_statement(session, row.run_id)
    session.flush()
    return {
        "review_case": review_case_view(session, row),
        "statement": statement_view(session, statement),
    }


def assign_review_case(
    session: Session, review_case_id: str, *, assigned_to: str | None
) -> dict[str, object]:
    row = session.get(ProductReviewCaseRow, review_case_id)
    if row is None:
        raise LookupError("Review case not found")
    row.assigned_to = assigned_to.strip() if assigned_to else None
    row.updated_at = _now()
    record_audit(
        session,
        "review_case.assigned",
        "review_case",
        row.id,
        assigned_to=row.assigned_to,
    )
    session.flush()
    return review_case_view(session, row)


def statement_view(session: Session, row: ProductReconciliationStatementRow) -> dict[str, object]:
    run = session.get(PilotReconciliationRunRow, row.run_id)
    approval = session.scalar(
        select(ProductApprovalRow).where(ProductApprovalRow.run_id == row.run_id)
    )
    return {
        "id": row.id,
        "run_id": row.run_id,
        "invoice_id": run.invoice_id if run else None,
        "status": row.status,
        "submitted_amount": _money(row.submitted_amount),
        "machine_payable_amount": _money(row.machine_payable_amount),
        "machine_disputed_amount": _money(row.machine_disputed_amount),
        "review_amount": _money(row.review_amount),
        "review_resolved_payable_amount": _money(row.review_resolved_payable_amount),
        "review_resolved_disputed_amount": _money(row.review_resolved_disputed_amount),
        "open_review_amount": _money(row.open_review_amount),
        "recommended_final_payable_amount": _money(row.recommended_final_payable_amount),
        "recommended_final_disputed_amount": _money(row.recommended_final_disputed_amount),
        "calculation_hash": row.calculation_hash,
        "kernel_input_manifest_hash": getattr(run, "input_manifest_hash", None) if run else None,
        "kernel_calculation_hash": getattr(run, "calculation_hash", None) if run else None,
        "created_at": row.created_at.isoformat(),
        "updated_at": row.updated_at.isoformat(),
        "approval": approval_view(approval) if approval else None,
    }


def get_statement(session: Session, run_id: str) -> dict[str, object]:
    return statement_view(session, refresh_statement(session, run_id))


def approval_view(row: ProductApprovalRow) -> dict[str, object]:
    return {
        "id": row.id,
        "run_id": row.run_id,
        "statement_id": row.statement_id,
        "approved_payable_amount": _money(row.approved_payable_amount),
        "approved_disputed_amount": _money(row.approved_disputed_amount),
        "approved_by": row.approved_by,
        "approved_at": row.approved_at.isoformat(),
        "calculation_hash": row.calculation_hash,
        "note": row.note,
    }


def approve_reconciliation(
    session: Session, run_id: str, *, approved_by: str, note: str = ""
) -> dict[str, object]:
    existing = session.scalar(select(ProductApprovalRow).where(ProductApprovalRow.run_id == run_id))
    if existing is not None:
        return approval_view(existing)
    statement = refresh_statement(session, run_id)
    if Decimal(statement.open_review_amount) != ZERO:
        raise ValueError("Resolve or explicitly disposition every review case before approval")
    if statement.status != "ready":
        raise ValueError("Reconciliation statement is not ready for approval")
    row = ProductApprovalRow(
        id=_id("APR"),
        run_id=run_id,
        statement_id=statement.id,
        approved_payable_amount=statement.recommended_final_payable_amount,
        approved_disputed_amount=statement.recommended_final_disputed_amount,
        approved_by=approved_by.strip() or current_actor(),
        approved_at=_now(),
        calculation_hash=statement.calculation_hash,
        note=note.strip(),
    )
    session.add(row)
    statement.status = "approved"
    statement.updated_at = _now()
    record_audit(
        session,
        "reconciliation.approved",
        "reconciliation",
        run_id,
        approval_id=row.id,
        payable_amount=_money(row.approved_payable_amount),
        disputed_amount=_money(row.approved_disputed_amount),
        calculation_hash=row.calculation_hash,
    )
    session.flush()
    return approval_view(row)


def _disputed_determinations(
    session: Session, run_id: str
) -> list[tuple[PilotDeterminationRow, str]]:
    determinations = session.scalars(
        select(PilotDeterminationRow)
        .where(PilotDeterminationRow.run_id == run_id)
        .order_by(PilotDeterminationRow.external_outcome_id)
    ).all()
    review_by_determination = {
        row.determination_id: row
        for row in session.scalars(
            select(ProductReviewCaseRow).where(ProductReviewCaseRow.run_id == run_id)
        ).all()
    }
    result: list[tuple[PilotDeterminationRow, str]] = []
    for determination in determinations:
        if determination.status == "disputed":
            result.append((determination, "machine"))
        elif determination.status == "needs_review":
            case = review_by_determination.get(determination.id)
            decision = _latest_decision(session, case.id) if case else None
            if decision and decision.decision == "disputed":
                result.append((determination, "review"))
    return result


def _next_case_number(session: Session) -> str:
    year = _now().year
    prefix = f"D-{year}-"
    existing = session.scalars(
        select(ProductDisputeCaseRow.case_number).where(
            ProductDisputeCaseRow.case_number.like(f"{prefix}%")
        )
    ).all()
    highest = 0
    for value in existing:
        try:
            highest = max(highest, int(value.rsplit("-", 1)[1]))
        except (IndexError, ValueError):
            continue
    return f"{prefix}{highest + 1:04d}"


def create_dispute_case(
    session: Session, run_id: str, *, created_by: str, subject: str | None = None
) -> dict[str, object]:
    approval = session.scalar(select(ProductApprovalRow).where(ProductApprovalRow.run_id == run_id))
    if approval is None:
        raise ValueError("Approve the payable amount before opening a vendor dispute")
    existing = session.scalar(
        select(ProductDisputeCaseRow)
        .where(ProductDisputeCaseRow.run_id == run_id)
        .order_by(ProductDisputeCaseRow.created_at.desc())
    )
    if existing is not None and existing.status != "closed":
        return dispute_case_view(session, existing)
    run = session.get(PilotReconciliationRunRow, run_id)
    if run is None:
        raise LookupError("Reconciliation run not found")
    invoice = session.get(PilotInvoiceRow, run.invoice_id)
    if invoice is None:
        raise LookupError("Invoice not found")
    contract = session.get(PilotContractRow, invoice.contract_id)
    if contract is None:
        raise LookupError("Contract not found")
    disputed = _disputed_determinations(session, run_id)
    total = sum(
        (
            Decimal(item.confirmed_disputed_amount)
            if source == "machine"
            else Decimal(item.needs_review_amount)
            for item, source in disputed
        ),
        ZERO,
    )
    if not disputed or total <= ZERO:
        raise ValueError("There are no approved disputed items to send to the vendor")
    row = ProductDisputeCaseRow(
        id=_id("DSP"),
        case_number=_next_case_number(session),
        run_id=run_id,
        approval_id=approval.id,
        status="draft",
        subject=(
            subject or f"{contract.vendor} invoice {invoice.id} - unsupported charges"
        ).strip(),
        disputed_amount=total,
        item_count=len(disputed),
        vendor_response="",
        vendor_response_at=None,
        created_by=created_by.strip() or current_actor(),
        created_at=_now(),
        updated_at=_now(),
        closed_at=None,
    )
    session.add(row)
    session.flush()
    for determination, source in disputed:
        amount = (
            Decimal(determination.confirmed_disputed_amount)
            if source == "machine"
            else Decimal(determination.needs_review_amount)
        )
        session.add(
            ProductDisputeItemRow(
                id=_id("DSI"),
                dispute_case_id=row.id,
                determination_id=determination.id,
                external_outcome_id=determination.external_outcome_id,
                amount=amount,
                reason_code=determination.rule_id or _review_reason_code(determination),
                reason=determination.reason,
                source=source,
                accepted_by_vendor=None,
            )
        )
    record_audit(
        session,
        "dispute_case.created",
        "dispute_case",
        row.id,
        case_number=row.case_number,
        run_id=run_id,
        disputed_amount=_money(total),
        item_count=len(disputed),
    )
    session.flush()
    return dispute_case_view(session, row)


def dispute_case_view(session: Session, row: ProductDisputeCaseRow) -> dict[str, object]:
    items = session.scalars(
        select(ProductDisputeItemRow)
        .where(ProductDisputeItemRow.dispute_case_id == row.id)
        .order_by(ProductDisputeItemRow.external_outcome_id)
    ).all()
    return {
        "id": row.id,
        "case_number": row.case_number,
        "run_id": row.run_id,
        "approval_id": row.approval_id,
        "status": row.status,
        "subject": row.subject,
        "disputed_amount": _money(row.disputed_amount),
        "item_count": row.item_count,
        "vendor_response": row.vendor_response,
        "vendor_response_at": (
            row.vendor_response_at.isoformat() if row.vendor_response_at else None
        ),
        "created_by": row.created_by,
        "created_at": row.created_at.isoformat(),
        "updated_at": row.updated_at.isoformat(),
        "closed_at": row.closed_at.isoformat() if row.closed_at else None,
        "items": [
            {
                "id": item.id,
                "determination_id": item.determination_id,
                "outcome_id": item.external_outcome_id,
                "amount": _money(item.amount),
                "reason_code": item.reason_code,
                "reason": item.reason,
                "source": item.source,
                "accepted_by_vendor": item.accepted_by_vendor,
            }
            for item in items
        ],
    }


def list_dispute_cases(session: Session) -> list[dict[str, object]]:
    bootstrap_product(session)
    rows = session.scalars(
        select(ProductDisputeCaseRow).order_by(ProductDisputeCaseRow.created_at.desc())
    ).all()
    return [dispute_case_view(session, row) for row in rows]


def update_dispute_case(
    session: Session,
    dispute_case_id: str,
    *,
    status: str,
    vendor_response: str | None = None,
) -> dict[str, object]:
    row = session.get(ProductDisputeCaseRow, dispute_case_id)
    if row is None:
        raise LookupError("Dispute case not found")
    allowed = DISPUTE_TRANSITIONS.get(row.status)
    if allowed is None or status not in allowed:
        raise ValueError(f"Cannot transition dispute case from {row.status} to {status}")
    previous = row.status
    row.status = status
    row.updated_at = _now()
    if vendor_response is not None:
        row.vendor_response = vendor_response.strip()
        row.vendor_response_at = _now()
    if status == "vendor_responded" and not row.vendor_response:
        raise ValueError("Vendor response text is required for vendor_responded status")
    if status == "closed":
        row.closed_at = _now()
    record_audit(
        session,
        "dispute_case.status_changed",
        "dispute_case",
        row.id,
        previous_status=previous,
        status=status,
        vendor_response_recorded=bool(vendor_response),
    )
    session.flush()
    return dispute_case_view(session, row)


def product_overview(session: Session) -> dict[str, object]:
    bootstrap = bootstrap_product(session)
    organization = ensure_organization(session)
    invoice_links = session.scalars(select(ProductEngagementInvoiceRow)).all()
    latest_runs = [
        run
        for link in invoice_links
        if (run := _latest_run_for_invoice(session, link.invoice_id)) is not None
    ]
    statements = [refresh_statement(session, run.id) for run in latest_runs]
    submitted = sum((Decimal(item.submitted_amount) for item in statements), ZERO)
    recommended_payable = sum(
        (Decimal(item.recommended_final_payable_amount) for item in statements), ZERO
    )
    disputed = sum((Decimal(item.recommended_final_disputed_amount) for item in statements), ZERO)
    open_review = sum((Decimal(item.open_review_amount) for item in statements), ZERO)
    open_review_cases = (
        session.scalar(
            select(func.count())
            .select_from(ProductReviewCaseRow)
            .where(ProductReviewCaseRow.status.in_(["open", "escalated"]))
        )
        or 0
    )
    active_disputes = (
        session.scalar(
            select(func.count())
            .select_from(ProductDisputeCaseRow)
            .where(ProductDisputeCaseRow.status != "closed")
        )
        or 0
    )
    approvals = session.scalar(select(func.count()).select_from(ProductApprovalRow)) or 0
    return {
        "organization": organization_view(organization),
        "counts": {
            **bootstrap,
            "open_review_cases": int(open_review_cases),
            "active_disputes": int(active_disputes),
            "approvals": int(approvals),
        },
        "latest_invoice_totals": {
            "submitted_amount": _money(submitted),
            "recommended_payable_amount": _money(recommended_payable),
            "disputed_amount": _money(disputed),
            "open_review_amount": _money(open_review),
        },
        "vendors": list_vendors(session),
        "invoices": list_invoices(session)[:10],
    }


def active_air_for_run(session: Session, run_id: str) -> dict[str, object] | None:
    run = session.get(PilotReconciliationRunRow, run_id)
    if run is None or not run.air_version_id:
        return None
    air = session.get(PilotAIRVersionRow, run.air_version_id)
    if air is None:
        return None
    return {
        "id": air.id,
        "version_number": air.version_number,
        "payload_hash": air.payload_hash,
        "approved_at": air.approved_at.isoformat() if air.approved_at else None,
        "approved_by": air.approved_by,
    }
