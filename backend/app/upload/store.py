"""Persistence and orchestration for the isolated real-data pilot path."""

from __future__ import annotations

import hashlib
import json
import os
import re
import uuid
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session

from app.agreements.adjudication import reconcile_agreement
from app.agreements.assurance import assure_agreement
from app.agreements.evaluation import dual_run
from app.agreements.impact import simulate_agreement_financial_impact
from app.agreements.legacy import conformance_report
from app.agreements.models import AgreementIR
from app.agreements.presentation import rule_description_for_id
from app.agreements.providers import provider_configuration_status
from app.agreements.traceability import build_decision_trace
from app.contracts.compiler import (
    DEFAULT_CONTRACT_PATH,
    agreement_artifacts_for_proposal,
    compile_with_gemini,
    load_recorded_proposal,
    sha256_text,
)
from app.domain.models import ExecutableRule, OperationalEvent, OutcomeClaim, RuleProgram
from app.upload.auth import current_actor, current_workspace_id
from app.upload.match import (
    ClaimIdentity,
    IdentityMapping,
    MatchCandidate,
    MatchingSummary,
    run_matching,
)
from app.upload.models import (
    PilotAgreementBundleRow,
    PilotAgreementDocumentRelationRow,
    PilotAgreementDocumentRow,
    PilotAgreementRuntimeComparisonRow,
    PilotAIRVersionRow,
    PilotAuditLogRow,
    PilotClaimRow,
    PilotContractRow,
    PilotContractRuleRow,
    PilotCustomerReviewRow,
    PilotDeterminationRow,
    PilotEventRow,
    PilotEvidenceReferenceRow,
    PilotEvidenceSourceDescriptorRow,
    PilotFactRow,
    PilotIdentityMappingRow,
    PilotInvoiceRow,
    PilotManualMatchRow,
    PilotProvenanceEdgeRow,
    PilotRawRecordRow,
    PilotReconciliationRunRow,
    PilotRuleCompilationRow,
    PilotStateRow,
    PilotUploadRejectionRow,
    PilotUploadRow,
    PilotVerificationPlanRow,
    PilotWorkspaceConfigRow,
)
from app.upload.parsers import ParseResult

PARSER_VERSION = "upload-v2"
MAPPING_VERSION = "mapping-v2"
MATCHING_VERSION = "matching-v2"


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex.upper()}"


def _money(value: Decimal) -> str:
    return f"{value:.2f}"


def _jsonable(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    return value


def _hash_bytes(content: bytes) -> str:
    return "sha256:" + hashlib.sha256(content).hexdigest()


def record_audit(
    session: Session,
    action: str,
    object_type: str,
    object_id: str | None = None,
    **details: Any,
) -> PilotAuditLogRow:
    row = PilotAuditLogRow(
        id=_id("PAUDIT"),
        action=action,
        object_type=object_type,
        object_id=object_id,
        actor=current_actor(),
        occurred_at=_now(),
        details=_jsonable(details),
    )
    session.add(row)
    return row


def ensure_pilot_state(session: Session) -> PilotStateRow:
    state = session.get(PilotStateRow, 1)
    if state is None:
        state = PilotStateRow(id=1, initialized=True, updated_at=_now())
        session.add(state)
        session.flush()
    return state


def ensure_workspace_config(session: Session) -> PilotWorkspaceConfigRow:
    row = session.get(PilotWorkspaceConfigRow, 1)
    if row is None:
        row = PilotWorkspaceConfigRow(id=1, updated_at=_now())
        session.add(row)
        session.flush()
    return row


def workspace_config_view(session: Session) -> dict[str, object]:
    row = ensure_workspace_config(session)
    return {
        "workspace_id": current_workspace_id(),
        "company_name": row.company_name,
        "default_vendor": row.default_vendor,
        "default_currency": row.default_currency,
        "timezone": row.timezone,
        "date_locale": row.date_locale,
        "default_contract_rate": row.default_contract_rate,
        "preferred_support_system": row.preferred_support_system,
        "preferred_payment_system": row.preferred_payment_system,
        "preferred_crm_system": row.preferred_crm_system,
        "updated_at": row.updated_at.isoformat(),
        "integrations": {
            "contract_ai": provider_configuration_status(os.getenv("EVIDUE_LLM_PRIMARY", "gemini")),
            "workspace_access": {
                "configured": bool(
                    os.getenv("EVIDUE_WORKSPACE_TOKENS") or os.getenv("EVIDUE_PILOT_TOKEN")
                ),
                "mode": "multi_workspace"
                if os.getenv("EVIDUE_WORKSPACE_TOKENS")
                else "single_workspace",
                "secret_location": "server_environment",
            },
        },
    }


def update_workspace_config(session: Session, values: dict[str, str]) -> dict[str, object]:
    row = ensure_workspace_config(session)
    allowed = {
        "company_name",
        "default_vendor",
        "default_currency",
        "timezone",
        "date_locale",
        "default_contract_rate",
        "preferred_support_system",
        "preferred_payment_system",
        "preferred_crm_system",
    }
    unknown = set(values) - allowed
    if unknown:
        raise ValueError(f"Unsupported configuration fields: {sorted(unknown)}")
    for key, value in values.items():
        clean = value.strip()
        if key == "default_currency":
            clean = clean.upper()
            if len(clean) != 3 or not clean.isalpha():
                raise ValueError("Default currency must be a three-letter ISO currency code")
        if key == "timezone" and clean:
            try:
                ZoneInfo(clean)
            except ZoneInfoNotFoundError as exc:
                raise ValueError(
                    "Timezone must be a valid IANA timezone, such as UTC or America/New_York"
                ) from exc
        if key == "default_contract_rate" and clean:
            try:
                rate = Decimal(clean)
            except InvalidOperation as exc:
                raise ValueError("Default contract rate must be a non-negative number") from exc
            if rate < 0:
                raise ValueError("Default contract rate must be a non-negative number")
            clean = format(rate, "f")
        if len(clean) > 200:
            raise ValueError(f"{key} is too long")
        setattr(row, key, clean)
    row.updated_at = _now()
    record_audit(
        session,
        "workspace.configuration_updated",
        "workspace",
        current_workspace_id(),
        fields=sorted(values),
    )
    session.flush()
    return workspace_config_view(session)


def create_upload(
    session: Session,
    upload_type: str,
    filename: str,
    content: bytes = b"",
    source_type: str | None = None,
    *,
    content_type: str | None = None,
    uploaded_by: str = "operator",
    invoice_id: str | None = None,
    coverage_complete: bool = False,
) -> PilotUploadRow:
    upload = PilotUploadRow(
        id=_id("UPL"),
        upload_type=upload_type,
        filename=filename,
        content_type=content_type,
        uploaded_by=uploaded_by,
        uploaded_at=_now(),
        status="processing",
        rows_parsed=0,
        rows_accepted=0,
        rows_rejected=0,
        error_summary=None,
        source_type=source_type,
        coverage_complete=coverage_complete,
        invoice_id=invoice_id,
        sha256=_hash_bytes(content),
    )
    session.add(upload)
    session.flush()
    record_audit(
        session,
        "upload.received",
        "upload",
        upload.id,
        upload_type=upload_type,
        filename=filename,
        sha256=upload.sha256,
        coverage_complete=coverage_complete,
    )
    return upload


def finalize_upload(session: Session, upload: PilotUploadRow, result: ParseResult) -> None:
    upload.rows_parsed = len(result.accepted) + len(result.rejected)
    upload.rows_accepted = len(result.accepted)
    upload.rows_rejected = len(result.rejected)
    upload.status = (
        "complete"
        if result.accepted and not result.rejected
        else ("partial" if result.accepted else "failed")
    )
    upload.error_summary = f"{len(result.rejected)} rows rejected" if result.rejected else None
    for rejection in result.rejected:
        session.add(
            PilotUploadRejectionRow(
                upload_id=upload.id,
                row_number=rejection.row_number,
                reason=rejection.reason,
                raw_data=_jsonable(rejection.raw_data),
            )
        )


def fail_upload(session: Session, upload: PilotUploadRow, reason: str) -> None:
    upload.status = "failed"
    upload.error_summary = reason[:2000]


def create_contract(
    session: Session,
    upload: PilotUploadRow,
    *,
    customer: str,
    vendor: str,
    period_start: datetime,
    period_end: datetime,
    price_per_outcome: Decimal,
    source_document: str,
    source_text: str,
) -> PilotContractRow:
    if period_end <= period_start:
        raise ValueError("Contract period end must be after period start")
    contract = PilotContractRow(
        id=_id("PCON"),
        customer=customer.strip(),
        vendor=vendor.strip(),
        period_start=period_start,
        period_end=period_end,
        price_per_outcome=price_per_outcome,
        source_document=source_document,
        source_text=source_text,
        source_hash=sha256_text(source_text),
        upload_id=upload.id,
        active_compilation_id=None,
        created_at=_now(),
    )
    session.add(contract)
    session.flush()
    from app.upload.agreement_store import ensure_contract_bundle

    ensure_contract_bundle(session, contract)
    state = ensure_pilot_state(session)
    state.active_contract_id = contract.id
    state.updated_at = _now()
    session.flush()
    record_audit(
        session,
        "contract.created",
        "contract",
        contract.id,
        customer=contract.customer,
        vendor=contract.vendor,
        source_hash=contract.source_hash,
    )
    return contract


def contract_view(session: Session, contract_id: str) -> dict[str, object]:
    contract = session.get(PilotContractRow, contract_id)
    if contract is None:
        raise LookupError("Pilot contract not found")
    compilations = session.scalars(
        select(PilotRuleCompilationRow)
        .where(PilotRuleCompilationRow.contract_id == contract.id)
        .order_by(PilotRuleCompilationRow.version.desc())
    ).all()
    return {
        "id": contract.id,
        "customer": contract.customer,
        "vendor": contract.vendor,
        "period_start": contract.period_start.isoformat(),
        "period_end": contract.period_end.isoformat(),
        "price_per_outcome": _money(contract.price_per_outcome),
        "source_document": contract.source_document,
        "source_hash": contract.source_hash,
        "active_compilation_id": contract.active_compilation_id,
        "agreement_bundle_id": contract.agreement_bundle_id,
        "created_at": contract.created_at.isoformat(),
        "compilations": [compilation_view(row) for row in compilations],
    }


def compilation_view(row: PilotRuleCompilationRow) -> dict[str, object]:
    return {
        "id": row.id,
        "contract_id": row.contract_id,
        "source_document": row.source_document,
        "source_hash": row.source_hash,
        "prompt_hash": row.prompt_hash,
        "provider": row.provider,
        "model": row.model,
        "compiler_version": row.compiler_version,
        "status": row.status,
        "version": row.version,
        "live_model_call": row.live_model_call,
        "created_at": row.created_at.isoformat(),
        "approved_at": row.approved_at.isoformat() if row.approved_at else None,
        "rules": sorted(row.rules, key=lambda item: item["priority"]),
        "diagnostics": (row.raw_response or {}).get("compiler_diagnostics", []),
        "clause_coverage": (row.raw_response or {}).get("clause_coverage", []),
        "approval_ready": bool((row.raw_response or {}).get("approval_ready", True)),
        "agreement_ir": (row.raw_response or {}).get("agreement_ir"),
        "conformance": (row.raw_response or {}).get("conformance"),
        "blocking_diagnostic_count": sum(
            item.get("severity") == "blocking"
            for item in (row.raw_response or {}).get("compiler_diagnostics", [])
        ),
        "safety_boundary": (
            "The LLM proposes schema-validated rules. A human approves an immutable version; "
            "only the deterministic interpreter evaluates invoice claims."
        ),
    }


def compile_contract(
    session: Session,
    contract_id: str,
    *,
    mode: str = "auto",
) -> PilotRuleCompilationRow:
    contract = session.get(PilotContractRow, contract_id)
    if contract is None:
        raise LookupError("Pilot contract not found")
    is_demo_contract = contract.source_text.strip() == DEFAULT_CONTRACT_PATH.read_text().strip()
    use_live = mode == "live" or (mode == "auto" and bool(os.getenv("GEMINI_API_KEY")))
    if not use_live and not is_demo_contract:
        raise ValueError(
            "This legacy compiler route requires a server-side Gemini configuration for custom "
            "contracts. Use /compile-native for provider-independent product compilation; "
            "customers never provide model credentials."
        )
    if use_live:
        result = compile_with_gemini(
            contract.source_text,
            contract.id,
            contract.source_document,
            contract_metadata={
                "customer": contract.customer,
                "vendor": contract.vendor,
                "billing_period_start": contract.period_start.isoformat(),
                "billing_period_end_exclusive": contract.period_end.isoformat(),
                "price_per_outcome": _money(contract.price_per_outcome),
            },
        )
    else:
        result = load_recorded_proposal(contract.source_text)

    latest_version = (
        session.scalar(
            select(func.max(PilotRuleCompilationRow.version)).where(
                PilotRuleCompilationRow.contract_id == contract.id
            )
        )
        or 0
    )
    session.execute(
        update(PilotRuleCompilationRow)
        .where(
            PilotRuleCompilationRow.contract_id == contract.id,
            PilotRuleCompilationRow.status == "pending_approval",
        )
        .values(status="superseded")
    )
    compilation_id = _id("PCOMP")
    version = int(latest_version) + 1
    agreement_ir, conformance = agreement_artifacts_for_proposal(
        result.proposal,
        compilation_id=compilation_id,
        version=version,
        source_hash=result.source_hash,
    )
    row = PilotRuleCompilationRow(
        id=compilation_id,
        contract_id=contract.id,
        source_document=contract.source_document,
        source_hash=result.source_hash,
        prompt_hash=result.prompt_hash,
        provider=result.proposal.provider,
        model=result.proposal.model,
        compiler_version=result.proposal.compiler_version,
        status="pending_approval",
        version=version,
        live_model_call=result.live_model_call,
        created_at=_now(),
        approved_at=None,
        rules=[rule.model_dump(mode="json") for rule in result.proposal.rules],
        raw_response={
            **result.raw_response,
            "source_text": contract.source_text,
            "compiler_diagnostics": [
                item.model_dump(mode="json") for item in result.proposal.diagnostics
            ],
            "clause_coverage": [
                item.model_dump(mode="json") for item in result.proposal.clause_coverage
            ],
            "approval_ready": result.proposal.approval_ready,
            "agreement_ir": agreement_ir.model_dump(mode="json"),
            "conformance": conformance.model_dump(mode="json"),
        },
    )
    session.add(row)
    session.flush()
    record_audit(
        session,
        "rule_proposal.generated",
        "compilation",
        row.id,
        contract_id=contract.id,
        version=row.version,
        live_model_call=row.live_model_call,
    )
    return row


def approve_contract_compilation(
    session: Session,
    compilation_id: str,
) -> PilotRuleCompilationRow:
    compilation = session.get(PilotRuleCompilationRow, compilation_id)
    if compilation is None:
        raise LookupError("Pilot compilation not found")
    if compilation.status != "pending_approval":
        raise ValueError("Only a pending pilot compilation can be approved")
    raw_response = compilation.raw_response or {}
    if not raw_response.get("approval_ready", True):
        blocking = [
            item.get("message", "Unresolved contract term")
            for item in raw_response.get("compiler_diagnostics", [])
            if item.get("severity") == "blocking"
        ]
        detail = "; ".join(blocking[:3]) or "Unresolved contract coverage remains"
        raise ValueError(f"Compilation cannot be approved: {detail}")
    latest = session.scalar(
        select(PilotRuleCompilationRow)
        .where(
            PilotRuleCompilationRow.contract_id == compilation.contract_id,
            PilotRuleCompilationRow.status == "pending_approval",
        )
        .order_by(PilotRuleCompilationRow.version.desc())
    )
    if latest is not None and latest.id != compilation.id:
        raise ValueError("A newer pending compilation exists")
    session.execute(
        update(PilotRuleCompilationRow)
        .where(
            PilotRuleCompilationRow.contract_id == compilation.contract_id,
            PilotRuleCompilationRow.status == "approved",
        )
        .values(status="superseded")
    )
    for payload in sorted(compilation.rules, key=lambda item: item["priority"]):
        session.add(
            PilotContractRuleRow(
                id=_id("PRULE"),
                compilation_id=compilation.id,
                rule_id=payload["id"],
                title=payload["title"],
                description=payload["description"],
                clause_text=payload["clause_text"],
                operation=payload["operation"],
                parameters=payload["parameters"],
                evidence_required=payload["evidence_required"],
                priority=payload["priority"],
                consequence=payload["consequence"],
            )
        )
    compilation.status = "approved"
    compilation.approved_at = _now()
    contract = session.get(PilotContractRow, compilation.contract_id)
    if contract is None:
        raise LookupError("Pilot contract not found")
    contract.active_compilation_id = compilation.id
    session.flush()
    record_audit(
        session,
        "rule_version.approved",
        "compilation",
        compilation.id,
        contract_id=contract.id,
        version=compilation.version,
    )
    return compilation


def _rule_program(session: Session, contract: PilotContractRow) -> RuleProgram:
    if not contract.active_compilation_id:
        raise LookupError("Pilot contract has no approved rule compilation")
    compilation = session.get(PilotRuleCompilationRow, contract.active_compilation_id)
    if compilation is None or compilation.status != "approved":
        raise LookupError("The pilot contract's active compilation is not approved")
    rows = session.scalars(
        select(PilotContractRuleRow)
        .where(PilotContractRuleRow.compilation_id == compilation.id)
        .order_by(PilotContractRuleRow.priority)
    ).all()
    if not rows:
        raise LookupError("Approved pilot compilation has no persisted rules")
    return RuleProgram(
        compilation_id=compilation.id,
        version=compilation.version,
        source_hash=compilation.source_hash,
        rules=tuple(
            ExecutableRule(
                id=row.rule_id,
                title=row.title,
                description=row.description,
                clause_text=row.clause_text,
                operation=row.operation,
                parameters=row.parameters,
                evidence_required=tuple(row.evidence_required),
                priority=row.priority,
                consequence=row.consequence,
                compilation_id=row.compilation_id,
            )
            for row in rows
        ),
    )


def create_invoice(
    session: Session,
    upload: PilotUploadRow,
    *,
    invoice_id: str,
    contract_id: str,
    billing_period_start: datetime,
    billing_period_end: datetime,
) -> PilotInvoiceRow:
    contract = session.get(PilotContractRow, contract_id)
    if contract is None:
        raise LookupError("Pilot contract not found")
    if billing_period_end <= billing_period_start:
        raise ValueError("Billing period end must be after billing period start")
    if session.get(PilotInvoiceRow, invoice_id):
        raise ValueError(f"Pilot invoice {invoice_id} already exists")
    invoice = PilotInvoiceRow(
        id=invoice_id,
        contract_id=contract.id,
        invoice_upload_id=upload.id,
        billing_period_start=billing_period_start,
        billing_period_end=billing_period_end,
        submitted_at=_now(),
        created_at=_now(),
    )
    session.add(invoice)
    upload.invoice_id = invoice.id
    state = ensure_pilot_state(session)
    state.active_contract_id = contract.id
    state.active_invoice_id = invoice.id
    state.updated_at = _now()
    session.flush()
    record_audit(
        session,
        "invoice.created",
        "invoice",
        invoice.id,
        contract_id=contract.id,
        billing_period_start=billing_period_start.isoformat(),
        billing_period_end=billing_period_end.isoformat(),
    )
    return invoice


def _normalization_warnings(data: dict[str, Any]) -> list[str]:
    warnings: list[str] = []
    raw = data.get("raw") or {}
    timestamp_fields = [
        raw.get(name)
        for name in (
            "timestamp",
            "occurred_at",
            "created_at",
            "claimed_completion_time",
            "closed_at",
        )
        if raw.get(name)
    ]
    if timestamp_fields and not re.search(
        r"(?:Z|[+-]\d{2}:?\d{2})$", str(timestamp_fields[0]).strip()
    ):
        warnings.append("Source timestamp had no explicit timezone; treated as source-local/naive")
    return warnings


def _add_raw_record(
    session: Session,
    *,
    upload: PilotUploadRow,
    invoice_id: str | None,
    row_number: int,
    source_record_id: str,
    record_type: str,
    source_system: str,
    occurred_at: datetime | None,
    raw: dict[str, Any],
    normalized: dict[str, Any],
    payload_hash: str,
) -> PilotRawRecordRow:
    row = PilotRawRecordRow(
        id=_id("PRAW"),
        upload_id=upload.id,
        invoice_id=invoice_id,
        row_number=row_number,
        source_record_id=source_record_id,
        record_type=record_type,
        source_system=source_system,
        occurred_at=occurred_at,
        received_at=_now(),
        raw_payload=_jsonable(raw),
        normalized_payload=_jsonable(normalized),
        payload_hash=payload_hash,
        parser_version=PARSER_VERSION,
        mapping_version=MAPPING_VERSION,
        normalization_warnings=_normalization_warnings(normalized),
    )
    session.add(row)
    session.flush()
    return row


def ingest_invoice_claims(
    session: Session,
    upload: PilotUploadRow,
    result: ParseResult,
    invoice_id: str,
) -> int:
    count = 0
    for parsed in result.accepted:
        data = parsed.data
        duplicate = session.scalar(
            select(PilotClaimRow).where(
                PilotClaimRow.invoice_id == invoice_id,
                PilotClaimRow.external_outcome_id == data["outcome_id"],
            )
        )
        if duplicate:
            session.add(
                PilotUploadRejectionRow(
                    upload_id=upload.id,
                    row_number=parsed.row_number,
                    reason="Duplicate outcome_id within invoice",
                    raw_data=_jsonable(data.get("raw", {})),
                )
            )
            upload.rows_rejected += 1
            upload.status = "partial"
            continue
        raw = _add_raw_record(
            session,
            upload=upload,
            invoice_id=invoice_id,
            row_number=parsed.row_number,
            source_record_id=data["vendor_claim_id"],
            record_type="invoice_claim",
            source_system="vendor_invoice",
            occurred_at=data["closed_at"],
            raw=data.get("raw", {}),
            normalized=data,
            payload_hash=data["payload_hash"],
        )
        session.add(
            PilotClaimRow(
                id=_id("PCLM"),
                invoice_id=invoice_id,
                raw_record_id=raw.id,
                external_outcome_id=data["outcome_id"],
                vendor_claim_id=data["vendor_claim_id"],
                external_conversation_id=data.get("conversation_id", ""),
                agent_version=data.get("agent_version", "unknown"),
                customer_id=data["customer_id"],
                intent=data["intent"],
                vendor_claim=data["vendor_claim"],
                closed_at=data["closed_at"],
                expected_action=data["expected_action"],
                account_id=data["account_id"],
                billed_amount=data["billed_amount"],
            )
        )
        count += 1
    upload.rows_accepted = count
    record_audit(
        session,
        "invoice.claims_ingested",
        "invoice",
        invoice_id,
        upload_id=upload.id,
        accepted=count,
        rejected=upload.rows_rejected,
    )
    return count


def ingest_evidence_events(
    session: Session,
    upload: PilotUploadRow,
    result: ParseResult,
    invoice_id: str,
) -> int:
    if session.get(PilotInvoiceRow, invoice_id) is None:
        raise LookupError("Pilot invoice not found")
    count = 0
    for parsed in result.accepted:
        data = parsed.data
        dedupe_source = f"{data['source_system']}|{data['source_record_id']}|{data['payload_hash']}"
        dedupe_key = hashlib.sha256(dedupe_source.encode()).hexdigest()
        duplicate = session.scalar(
            select(PilotEventRow).where(
                PilotEventRow.invoice_id == invoice_id,
                PilotEventRow.dedupe_key == dedupe_key,
            )
        )
        if duplicate:
            session.add(
                PilotUploadRejectionRow(
                    upload_id=upload.id,
                    row_number=parsed.row_number,
                    reason="Duplicate evidence record for this invoice",
                    raw_data=_jsonable(data.get("raw", {})),
                )
            )
            upload.rows_rejected += 1
            upload.status = "partial"
            continue
        raw = _add_raw_record(
            session,
            upload=upload,
            invoice_id=invoice_id,
            row_number=parsed.row_number,
            source_record_id=data["source_record_id"],
            record_type="operational_event",
            source_system=data["source_system"],
            occurred_at=data["timestamp"],
            raw=data.get("raw", {}),
            normalized=data,
            payload_hash=data["payload_hash"],
        )
        session.add(
            PilotEventRow(
                id=_id("PEVT"),
                invoice_id=invoice_id,
                upload_id=upload.id,
                raw_record_id=raw.id,
                source_system=data["source_system"],
                source_record_id=data["source_record_id"],
                dedupe_key=dedupe_key,
                event_type=data["event_type"],
                timestamp=data["timestamp"],
                customer_id=data["customer_id"],
                claimed_outcome_id=data.get("outcome_id"),
                matched_claim_id=None,
                values=data.get("values", {}),
                ingested_at=_now(),
                match_status="pending",
                match_method="pending",
                match_confidence=Decimal("0.0000"),
                match_reason="Awaiting identity matching",
                payload_hash=data["payload_hash"],
                parser_version=PARSER_VERSION,
                mapping_version=MAPPING_VERSION,
            )
        )
        count += 1
    upload.invoice_id = invoice_id
    upload.rows_accepted = count
    record_audit(
        session,
        "evidence.ingested",
        "invoice",
        invoice_id,
        upload_id=upload.id,
        source_type=upload.source_type,
        complete_export=bool(upload.coverage_complete),
        accepted=count,
        rejected=upload.rows_rejected,
    )
    return count


def persist_identity_mappings(
    session: Session,
    upload: PilotUploadRow,
    result: ParseResult,
    invoice_id: str,
) -> int:
    count = 0
    valid_outcomes = {
        row.external_outcome_id
        for row in session.scalars(
            select(PilotClaimRow).where(PilotClaimRow.invoice_id == invoice_id)
        ).all()
    }
    for parsed in result.accepted:
        data = parsed.data
        outcome_id = data.get("outcome_id")
        if not outcome_id:
            session.add(
                PilotUploadRejectionRow(
                    upload_id=upload.id,
                    row_number=parsed.row_number,
                    reason="Identity mapping requires outcome_id",
                    raw_data=_jsonable(data),
                )
            )
            upload.rows_rejected += 1
            upload.status = "partial"
            continue
        if outcome_id not in valid_outcomes:
            session.add(
                PilotUploadRejectionRow(
                    upload_id=upload.id,
                    row_number=parsed.row_number,
                    reason=f"Identity mapping references unknown outcome_id {outcome_id}",
                    raw_data=_jsonable(data),
                )
            )
            upload.rows_rejected += 1
            upload.status = "partial"
            continue
        if not data.get("conversation_id") and not (
            data.get("customer_id") and data.get("account_id")
        ):
            session.add(
                PilotUploadRejectionRow(
                    upload_id=upload.id,
                    row_number=parsed.row_number,
                    reason="Mapping needs conversation_id or exact customer_id + account_id",
                    raw_data=_jsonable(data),
                )
            )
            upload.rows_rejected += 1
            upload.status = "partial"
            continue
        session.add(
            PilotIdentityMappingRow(
                id=_id("PMAP"),
                invoice_id=invoice_id,
                upload_id=upload.id,
                conversation_id=data.get("conversation_id"),
                customer_id=data.get("customer_id"),
                account_id=data.get("account_id"),
                outcome_id=outcome_id,
                mapping_version=MAPPING_VERSION,
                created_at=_now(),
            )
        )
        count += 1
    upload.invoice_id = invoice_id
    upload.rows_accepted = count
    return count


def run_identity_matching(session: Session, invoice_id: str) -> MatchingSummary:
    claims = session.scalars(
        select(PilotClaimRow).where(PilotClaimRow.invoice_id == invoice_id)
    ).all()
    events = session.scalars(
        select(PilotEventRow).where(
            PilotEventRow.invoice_id == invoice_id,
            PilotEventRow.match_status.in_(["pending", "unresolved", "suggested"]),
        )
    ).all()
    mappings = session.scalars(
        select(PilotIdentityMappingRow).where(PilotIdentityMappingRow.invoice_id == invoice_id)
    ).all()
    claim_by_external = {claim.external_outcome_id: claim for claim in claims}
    claim_identities = [
        ClaimIdentity(
            outcome_id=claim.external_outcome_id,
            customer_id=claim.customer_id,
            conversation_id=claim.external_conversation_id,
            account_id=claim.account_id,
            closed_at=claim.closed_at.isoformat(),
            intent=claim.intent,
        )
        for claim in claims
    ]
    candidates = [
        MatchCandidate(
            event_id=event.id,
            event_outcome_id=event.claimed_outcome_id,
            event_customer_id=event.customer_id,
            event_timestamp=event.timestamp.isoformat(),
            event_type=event.event_type,
            event_values=event.values or {},
        )
        for event in events
    ]
    identity_mappings = [
        IdentityMapping(
            conversation_id=row.conversation_id,
            customer_id=row.customer_id,
            account_id=row.account_id,
            outcome_id=row.outcome_id,
        )
        for row in mappings
    ]
    results, summary = run_matching(candidates, claim_identities, identity_mappings)
    event_by_id = {event.id: event for event in events}
    for result in results:
        event = event_by_id[result.event_id]
        claim = claim_by_external.get(result.outcome_id or "")
        event.match_method = result.method
        event.match_confidence = result.confidence
        event.match_reason = result.reason
        if (
            result.method
            in {
                "direct_outcome_id",
                "identity_map_conversation",
                "identity_map_customer_account",
            }
            and claim is not None
        ):
            event.matched_claim_id = claim.id
            event.match_status = "accepted"
        elif result.method == "composite_customer_time" and claim is not None:
            # Heuristic matching may suggest a candidate, but it cannot affect money
            # until a human explicitly confirms it.
            event.matched_claim_id = None
            event.match_status = "suggested"
            event.match_reason += f"; suggested outcome_id={claim.external_outcome_id}"
        else:
            event.matched_claim_id = None
            event.match_status = "unresolved"
    record_audit(
        session,
        "evidence.matched",
        "invoice",
        invoice_id,
        total_events=summary.total_events,
        direct_matches=summary.direct_matches,
        identity_map_matches=summary.identity_map_matches,
        suggested_matches=summary.composite_matches,
        unresolved=summary.unresolved,
    )
    return summary


def get_unmatched_events(
    session: Session,
    invoice_id: str,
    limit: int = 50,
    offset: int = 0,
) -> tuple[int, list[dict[str, object]]]:
    base = select(PilotEventRow).where(
        PilotEventRow.invoice_id == invoice_id,
        PilotEventRow.match_status.in_(["pending", "unresolved", "suggested"]),
    )
    total = session.scalar(select(func.count()).select_from(base.subquery())) or 0
    rows = session.scalars(base.order_by(PilotEventRow.timestamp).offset(offset).limit(limit)).all()
    return total, [
        {
            "event_id": row.id,
            "source_system": row.source_system,
            "source_record_id": row.source_record_id,
            "event_type": row.event_type,
            "timestamp": row.timestamp.isoformat(),
            "customer_id": row.customer_id,
            "claimed_outcome_id": row.claimed_outcome_id,
            "match_status": row.match_status,
            "match_method": row.match_method,
            "match_confidence": f"{row.match_confidence:.4f}",
            "match_reason": row.match_reason,
            "values": row.values,
        }
        for row in rows
    ]


def get_match_candidates(
    session: Session,
    invoice_id: str,
    event_id: str,
    limit: int = 10,
) -> list[dict[str, object]]:
    event = session.get(PilotEventRow, event_id)
    if event is None or event.invoice_id != invoice_id:
        return []
    claims = session.scalars(
        select(PilotClaimRow)
        .where(
            PilotClaimRow.invoice_id == invoice_id,
            PilotClaimRow.customer_id == event.customer_id,
        )
        .order_by(PilotClaimRow.closed_at)
        .limit(limit)
    ).all()
    items = []
    for claim in claims:
        delta = abs((event.timestamp - claim.closed_at).total_seconds())
        items.append(
            {
                "claim_id": claim.id,
                "outcome_id": claim.external_outcome_id,
                "customer_id": claim.customer_id,
                "intent": claim.intent,
                "closed_at": claim.closed_at.isoformat(),
                "expected_action": claim.expected_action,
                "account_id": claim.account_id,
                "time_delta_seconds": int(delta),
                "time_delta_human": _format_delta(delta),
            }
        )
    return sorted(items, key=lambda item: item["time_delta_seconds"])


def confirm_manual_match(
    session: Session,
    *,
    invoice_id: str,
    event_id: str,
    claim_id: str,
    rationale: str,
    confirmed_by: str,
) -> PilotManualMatchRow:
    event = session.get(PilotEventRow, event_id)
    claim = session.get(PilotClaimRow, claim_id)
    if event is None or event.invoice_id != invoice_id:
        raise LookupError("Pilot event not found for this invoice")
    if claim is None or claim.invoice_id != invoice_id:
        raise LookupError("Pilot claim not found for this invoice")
    session.execute(
        update(PilotManualMatchRow)
        .where(PilotManualMatchRow.event_id == event.id, PilotManualMatchRow.active.is_(True))
        .values(active=False)
    )
    row = PilotManualMatchRow(
        id=_id("PMAN"),
        invoice_id=invoice_id,
        event_id=event.id,
        claim_id=claim.id,
        confirmed_by=confirmed_by,
        confirmed_at=_now(),
        rationale=rationale.strip() or "Operator confirmed evidence-to-claim identity",
        active=True,
    )
    session.add(row)
    event.matched_claim_id = claim.id
    event.match_status = "accepted"
    event.match_method = "manual"
    event.match_confidence = Decimal("1.0000")
    event.match_reason = row.rationale
    record_audit(
        session,
        "match.confirmed",
        "event",
        event.id,
        invoice_id=invoice_id,
        claim_id=claim.id,
        confirmed_by=confirmed_by,
        rationale=row.rationale,
    )
    session.flush()
    return row


def _format_delta(seconds: float) -> str:
    if seconds < 60:
        return f"{int(seconds)}s"
    if seconds < 3600:
        return f"{int(seconds / 60)}m"
    if seconds < 86400:
        return f"{seconds / 3600:.1f}h"
    return f"{seconds / 86400:.1f}d"


def _domain_claim(row: PilotClaimRow) -> OutcomeClaim:
    return OutcomeClaim(
        row.external_outcome_id,
        row.invoice_id,
        row.customer_id,
        row.intent,
        row.vendor_claim,
        row.closed_at,
        row.expected_action,
        row.account_id,
        row.billed_amount,
    )


def _domain_event(row: PilotEventRow, claim: PilotClaimRow) -> OperationalEvent:
    return OperationalEvent(
        row.id,
        row.source_system,
        row.source_record_id,
        row.event_type,
        row.timestamp,
        row.customer_id,
        claim.external_outcome_id,
        row.values,
        row.ingested_at,
    )


def _runtime_flag(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "on"}


# ---------------------------------------------------------------------------
# M5: Persisted Agreement IR versions
# ---------------------------------------------------------------------------


def persist_air_version(
    session: Session,
    *,
    contract_id: str,
    compilation_id: str,
    air: AgreementIR,
    compiler_mode: str,
    source_hash: str,
    compiler_model: str | None = None,
    prompt_version: str | None = None,
) -> PilotAIRVersionRow:
    """Persist an Agreement IR version. Immutable once approved."""
    latest = session.scalar(
        select(PilotAIRVersionRow)
        .where(PilotAIRVersionRow.contract_id == contract_id)
        .order_by(PilotAIRVersionRow.version_number.desc())
    )
    version_number = (latest.version_number if latest else 0) + 1
    payload = air.model_dump(mode="json")
    payload_hash = sha256_text(json.dumps(payload, sort_keys=True, separators=(",", ":")))
    assurance = assure_agreement(air)
    row = PilotAIRVersionRow(
        id=_id("PAIR"),
        contract_id=contract_id,
        compilation_id=compilation_id,
        version_number=version_number,
        schema_version=air.schema_version,
        source_bundle_hash=source_hash,
        compiler_mode=compiler_mode,
        compiler_model=compiler_model,
        prompt_version=prompt_version,
        created_at=_now(),
        payload_hash=payload_hash,
        assurance_json=assurance.model_dump(mode="json"),
        air_json=payload,
    )
    session.add(row)
    session.flush()
    record_audit(
        session,
        "air_version.created",
        "air_version",
        row.id,
        contract_id=contract_id,
        version_number=version_number,
        payload_hash=payload_hash,
        assurance_hard_gate_passed=assurance.hard_gate_passed,
    )
    return row


def approve_air_version(
    session: Session,
    air_version_id: str,
    approved_by: str = "operator",
) -> PilotAIRVersionRow:
    """Approve an AIR version. Once approved, payload is immutable."""
    row = session.get(PilotAIRVersionRow, air_version_id)
    if row is None:
        raise LookupError("AIR version not found")
    if row.approved_at is not None:
        raise ValueError("AIR version is already approved")
    agreement = AgreementIR.model_validate(row.air_json)
    expected_hash = sha256_text(
        json.dumps(agreement.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
    )
    if row.payload_hash != expected_hash:
        raise ValueError("AIR payload hash does not match the persisted immutable payload")
    report = conformance_report(agreement)
    assurance = assure_agreement(agreement)
    row.assurance_json = assurance.model_dump(mode="json")
    if not assurance.hard_gate_passed:
        failed = [
            check.id for check in assurance.checks if check.hard_gate and check.status != "pass"
        ]
        raise ValueError("AIR compiler assurance failed: " + ", ".join(failed[:5]))
    if not report.approvable:
        raise ValueError(
            "AIR version is not approvable: "
            f"{report.blocking_diagnostic_count} blocking diagnostics, "
            f"{report.unsupported_count} unsupported clauses, "
            f"{report.unrepresented_material_clause_count} unrepresented material clauses"
        )
    row.approved_at = _now()
    row.approved_by = approved_by
    # Supersede any previously approved version for the same contract
    prior = session.scalar(
        select(PilotAIRVersionRow).where(
            PilotAIRVersionRow.contract_id == row.contract_id,
            PilotAIRVersionRow.approved_at.is_not(None),
            PilotAIRVersionRow.id != row.id,
            PilotAIRVersionRow.superseded_by_id.is_(None),
        )
    )
    if prior is not None:
        prior.superseded_by_id = row.id
    record_audit(
        session,
        "air_version.approved",
        "air_version",
        row.id,
        contract_id=row.contract_id,
        version_number=row.version_number,
        assurance_hard_gate_passed=assurance.hard_gate_passed,
    )
    return row


def get_approved_air(session: Session, contract_id: str) -> AgreementIR | None:
    """Load the currently approved AIR version for a contract."""
    row = session.scalar(
        select(PilotAIRVersionRow).where(
            PilotAIRVersionRow.contract_id == contract_id,
            PilotAIRVersionRow.approved_at.is_not(None),
            PilotAIRVersionRow.superseded_by_id.is_(None),
        )
    )
    if row is None:
        return None
    return AgreementIR.model_validate(row.air_json)


def get_approved_air_version_id(session: Session, contract_id: str) -> str | None:
    """Get the ID of the currently approved AIR version."""
    row = session.scalar(
        select(PilotAIRVersionRow).where(
            PilotAIRVersionRow.contract_id == contract_id,
            PilotAIRVersionRow.approved_at.is_not(None),
            PilotAIRVersionRow.superseded_by_id.is_(None),
        )
    )
    return row.id if row else None


def _comparison_payload(report: dict[str, Any]) -> dict[str, Any]:
    return {
        key: _jsonable(value)
        for key, value in report.items()
        if key not in {"legacy_results", "air_results"}
    }


def _invoice_claim_rows(
    session: Session,
    invoice: PilotInvoiceRow,
) -> list[PilotClaimRow]:
    claims = list(
        session.scalars(
            select(PilotClaimRow)
            .where(PilotClaimRow.invoice_id == invoice.id)
            .order_by(PilotClaimRow.external_outcome_id)
        ).all()
    )
    if not claims:
        raise ValueError("Pilot invoice has no accepted claims")
    return claims


def _claim_evidence_for_invoice(
    session: Session,
    invoice: PilotInvoiceRow,
    *,
    claims: list[PilotClaimRow] | None = None,
) -> list[tuple[OutcomeClaim, list[OperationalEvent]]]:
    claim_rows = claims if claims is not None else _invoice_claim_rows(session, invoice)
    events = session.scalars(
        select(PilotEventRow).where(
            PilotEventRow.invoice_id == invoice.id,
            PilotEventRow.match_status == "accepted",
            PilotEventRow.matched_claim_id.is_not(None),
        )
    ).all()
    events_by_claim: dict[str, list[PilotEventRow]] = {}
    for event in events:
        if event.matched_claim_id:
            events_by_claim.setdefault(event.matched_claim_id, []).append(event)
    return [
        (
            _domain_claim(claim),
            [_domain_event(event, claim) for event in events_by_claim.get(claim.id, [])],
        )
        for claim in claim_rows
    ]


def simulate_air_version_financial_impact(
    session: Session,
    *,
    invoice_id: str,
    candidate_air_version_id: str,
    baseline_air_version_id: str | None = None,
) -> dict[str, object]:
    """Replay one invoice against approved and candidate AIR versions without persisting money.

    This is a pre-approval control surface for contract/amendment changes. The
    baseline must be human-approved; the candidate must pass deterministic
    compiler assurance/conformance, but it may still be pending human approval.
    No provider or LLM is invoked.
    """

    invoice = session.get(PilotInvoiceRow, invoice_id)
    if invoice is None:
        raise LookupError("Pilot invoice not found")
    contract = session.get(PilotContractRow, invoice.contract_id)
    if contract is None:
        raise LookupError("Pilot contract not found")

    candidate_row = session.get(PilotAIRVersionRow, candidate_air_version_id)
    if candidate_row is None:
        raise LookupError("Candidate AIR version not found")
    if candidate_row.contract_id != contract.id:
        raise ValueError("Candidate AIR version does not belong to the invoice contract")

    if baseline_air_version_id:
        baseline_row = session.get(PilotAIRVersionRow, baseline_air_version_id)
        if baseline_row is None:
            raise LookupError("Baseline AIR version not found")
    else:
        baseline_row = session.scalar(
            select(PilotAIRVersionRow).where(
                PilotAIRVersionRow.contract_id == contract.id,
                PilotAIRVersionRow.approved_at.is_not(None),
                PilotAIRVersionRow.superseded_by_id.is_(None),
            )
        )
        if baseline_row is None:
            # If the candidate is the current approved version, compare against
            # the most recent older approved version when one exists.
            baseline_row = session.scalar(
                select(PilotAIRVersionRow)
                .where(
                    PilotAIRVersionRow.contract_id == contract.id,
                    PilotAIRVersionRow.approved_at.is_not(None),
                    PilotAIRVersionRow.id != candidate_row.id,
                )
                .order_by(PilotAIRVersionRow.version_number.desc())
            )
    if baseline_row is None:
        raise ValueError("Financial impact requires an approved baseline AIR version")
    if baseline_row.contract_id != contract.id:
        raise ValueError("Baseline AIR version does not belong to the invoice contract")
    if baseline_row.approved_at is None:
        raise ValueError("Financial impact baseline must be a human-approved AIR version")

    baseline_air = AgreementIR.model_validate(baseline_row.air_json)
    candidate_air = AgreementIR.model_validate(candidate_row.air_json)
    baseline_assurance = assure_agreement(baseline_air)
    candidate_assurance = assure_agreement(candidate_air)
    candidate_conformance = conformance_report(candidate_air)
    if not baseline_assurance.hard_gate_passed:
        raise ValueError("Approved baseline AIR no longer passes compiler assurance")
    if not candidate_assurance.hard_gate_passed or not candidate_conformance.approvable:
        raise ValueError(
            "Candidate AIR must pass deterministic assurance and conformance before impact analysis"
        )

    claim_evidence = _claim_evidence_for_invoice(session, invoice)
    impact = simulate_agreement_financial_impact(
        claim_evidence,
        baseline_air,
        candidate_air,
    )

    from app.upload.agreement_store import agreement_bundle_source_hash

    current_source_hash = agreement_bundle_source_hash(session, contract.id)
    impact.update(
        {
            "invoice_id": invoice.id,
            "contract_id": contract.id,
            "baseline_air_version": {
                "id": baseline_row.id,
                "version_number": baseline_row.version_number,
                "source_bundle_hash": baseline_row.source_bundle_hash,
                "approved_at": (
                    baseline_row.approved_at.isoformat() if baseline_row.approved_at else None
                ),
            },
            "candidate_air_version": {
                "id": candidate_row.id,
                "version_number": candidate_row.version_number,
                "source_bundle_hash": candidate_row.source_bundle_hash,
                "approved_at": (
                    candidate_row.approved_at.isoformat() if candidate_row.approved_at else None
                ),
                "matches_current_agreement_bundle": (
                    candidate_row.source_bundle_hash == current_source_hash
                ),
            },
            "current_agreement_bundle_hash": current_source_hash,
            "financial_authority_air_version_id": baseline_row.id,
            "warning": (
                "Simulation only. Candidate rules do not become financial authority until a human "
                "approves that AIR version."
            ),
        }
    )
    return impact


def simulate_contract_historical_replay(
    session: Session,
    *,
    contract_id: str,
    air_version_id: str | None = None,
) -> dict[str, object]:
    """Replay all accepted historical invoices through one approved AIR without persistence.

    This is the low-friction pilot/diagnostic path: Finance can upload historical
    invoice and evidence exports, approve the governing AIR once, and see the
    aggregate contractual result without creating reconciliation runs.
    """

    contract = session.get(PilotContractRow, contract_id)
    if contract is None:
        raise LookupError("Pilot contract not found")

    if air_version_id:
        air_row = session.get(PilotAIRVersionRow, air_version_id)
        if air_row is None:
            raise LookupError("AIR version not found")
    else:
        air_row = session.scalar(
            select(PilotAIRVersionRow).where(
                PilotAIRVersionRow.contract_id == contract.id,
                PilotAIRVersionRow.approved_at.is_not(None),
                PilotAIRVersionRow.superseded_by_id.is_(None),
            )
        )
    if air_row is None:
        raise ValueError("Historical replay requires a human-approved AIR version")
    if air_row.contract_id != contract.id:
        raise ValueError("AIR version does not belong to the requested contract")
    if air_row.approved_at is None:
        raise ValueError("Historical replay requires a human-approved AIR version")

    from app.upload.agreement_store import (
        agreement_bundle_source_hash,
        ensure_single_governing_period,
    )

    ensure_single_governing_period(session, contract.id)
    current_source_hash = agreement_bundle_source_hash(session, contract.id)
    if air_row.source_bundle_hash != current_source_hash:
        raise ValueError(
            "Historical replay is blocked because the approved AIR is stale for the current "
            "agreement bundle. Approve the governing contract version before replaying invoices."
        )

    agreement = AgreementIR.model_validate(air_row.air_json)
    assurance = assure_agreement(agreement)
    if not assurance.hard_gate_passed:
        raise ValueError("Approved Agreement IR no longer passes compiler assurance")

    settlement_currencies = sorted({policy.currency for policy in agreement.settlement_policies})
    if len(settlement_currencies) > 1:
        raise ValueError(
            "Historical replay cannot aggregate an AIR with multiple currencies without a "
            "contract-authorized FX conversion policy. Split the replay by currency/contract "
            "period instead."
        )
    currency = settlement_currencies[0] if settlement_currencies else None

    invoices = session.scalars(
        select(PilotInvoiceRow)
        .where(PilotInvoiceRow.contract_id == contract.id)
        .order_by(PilotInvoiceRow.billing_period_start, PilotInvoiceRow.id)
    ).all()
    if not invoices:
        raise ValueError("No invoices are available for historical replay")

    billed_total = Decimal()
    payable_total = Decimal()
    disputed_total = Decimal()
    review_total = Decimal()
    replayed = 0
    invoice_rows: list[dict[str, object]] = []

    for invoice in invoices:
        try:
            claim_evidence = _claim_evidence_for_invoice(session, invoice)
        except ValueError as exc:
            invoice_rows.append(
                {
                    "invoice_id": invoice.id,
                    "status": "not_ready",
                    "reason": str(exc),
                }
            )
            continue

        results = reconcile_agreement(claim_evidence, agreement)
        billed = sum((item.claim.billed_amount for item in results), Decimal())
        payable = sum((item.confirmed_payable_amount for item in results), Decimal())
        disputed = sum((item.confirmed_disputed_amount for item in results), Decimal())
        review = sum((item.needs_review_amount for item in results), Decimal())
        conservation = billed == payable + disputed + review
        if not conservation:
            raise ValueError(f"Historical replay violated money conservation for {invoice.id}")

        billed_total += billed
        payable_total += payable
        disputed_total += disputed
        review_total += review
        replayed += 1
        invoice_rows.append(
            {
                "invoice_id": invoice.id,
                "status": "replayed",
                "billing_period_start": invoice.billing_period_start.isoformat(),
                "billing_period_end": invoice.billing_period_end.isoformat(),
                "claimed_outcomes": len(results),
                "payable_outcomes": sum(item.status == "payable" for item in results),
                "disputed_outcomes": sum(item.status == "disputed" for item in results),
                "needs_review_outcomes": sum(item.status == "needs_review" for item in results),
                "billed": _money(billed),
                "payable": _money(payable),
                "disputed": _money(disputed),
                "needs_review": _money(review),
                "conservation_passed": conservation,
            }
        )

    aggregate_conservation = billed_total == payable_total + disputed_total + review_total
    return {
        "version": "historical-replay-1",
        "historical_replay": True,
        "simulation_only": True,
        "contract_id": contract.id,
        "customer": contract.customer,
        "vendor": contract.vendor,
        "air_version_id": air_row.id,
        "air_version_number": air_row.version_number,
        "financial_authority": "approved_air",
        "currency": currency,
        "currency_consistent": True,
        "invoices_total": len(invoices),
        "invoices_replayed": replayed,
        "invoices_not_ready": len(invoices) - replayed,
        "totals": {
            "billed": _money(billed_total),
            "payable": _money(payable_total),
            "disputed": _money(disputed_total),
            "needs_review": _money(review_total),
            "conservation_passed": aggregate_conservation,
        },
        "invoices": invoice_rows,
        "warning": (
            "Historical replay is an analysis over uploaded historical exports. It does not "
            "create a payable instruction or claim recovered savings."
        ),
    }


def run_pilot_reconciliation(session: Session, invoice_id: str) -> dict[str, object]:
    """Reconcile using the approved AIR as the contractual financial authority.

    The legacy rule program is retained only for migration comparison when it is
    available.  No LLM is invoked here and no legacy rule ID is consulted by the
    authority evaluator.
    """
    invoice = session.get(PilotInvoiceRow, invoice_id)
    if invoice is None:
        raise LookupError("Pilot invoice not found")
    contract = session.get(PilotContractRow, invoice.contract_id)
    if contract is None:
        raise LookupError("Pilot contract not found")

    air_row = session.scalar(
        select(PilotAIRVersionRow).where(
            PilotAIRVersionRow.contract_id == contract.id,
            PilotAIRVersionRow.approved_at.is_not(None),
            PilotAIRVersionRow.superseded_by_id.is_(None),
        )
    )
    if air_row is None:
        raise ValueError(
            "Reconciliation requires a human-approved Agreement IR version. "
            "Compile, review, and approve the contract rules first."
        )
    from app.upload.agreement_store import (
        agreement_bundle_source_hash,
        ensure_single_governing_period,
    )

    ensure_single_governing_period(session, contract.id)
    current_source_hash = agreement_bundle_source_hash(session, contract.id)
    if air_row.source_bundle_hash != current_source_hash:
        raise ValueError(
            "The governing agreement documents changed after these contract rules were approved. "
            "Analyze the current agreement bundle and approve a new rule version before "
            "reconciling."
        )
    approved_air = AgreementIR.model_validate(air_row.air_json)
    assurance = assure_agreement(approved_air)
    if not assurance.hard_gate_passed:
        raise ValueError("Approved Agreement IR no longer passes compiler assurance")

    claims = _invoice_claim_rows(session, invoice)
    claim_evidence = _claim_evidence_for_invoice(session, invoice, claims=claims)
    results = reconcile_agreement(claim_evidence, approved_air)
    air_version_id = air_row.id

    from app.upload.agreement_store import latest_verification_plan

    plan = latest_verification_plan(session, air_version_id)
    verification_plan_id = plan.id if plan is not None else None

    # Optional migration observability.  This can never override AIR decisions.
    comparison_report: dict[str, Any] | None = None
    if _runtime_flag("EVIDUE_AGREEMENT_RUNTIME_DUAL_RUN"):
        try:
            program = _rule_program(session, contract)
        except (LookupError, ValueError):
            program = None
        if program is not None:
            comparison_report = dual_run(claim_evidence, approved_air, program)
            comparison_report["air_version_id"] = air_version_id
            comparison_report["verification_plan_id"] = verification_plan_id
            comparison_report["financial_authority"] = "approved_air"

    latest = session.scalar(
        select(PilotReconciliationRunRow)
        .where(PilotReconciliationRunRow.invoice_id == invoice.id)
        .order_by(PilotReconciliationRunRow.run_number.desc())
    )
    run_number = (latest.run_number if latest else 0) + 1
    submitted = sum((result.claim.billed_amount for result in results), Decimal())
    payable = sum((result.confirmed_payable_amount for result in results), Decimal())
    disputed = sum((result.confirmed_disputed_amount for result in results), Decimal())
    review = sum((result.needs_review_amount for result in results), Decimal())
    run = PilotReconciliationRunRow(
        id=_id("PRUN"),
        invoice_id=invoice.id,
        compilation_id=air_row.compilation_id,
        run_number=run_number,
        started_at=_now(),
        completed_at=_now(),
        engine_version=(
            results[0].engine_version if results else f"air-generic-{approved_air.schema_version}"
        ),
        rule_program_version=air_row.version_number,
        normalizer_version=MAPPING_VERSION,
        matching_version=MATCHING_VERSION,
        claimed_outcomes=len(results),
        payable_outcomes=sum(result.status == "payable" for result in results),
        disputed_outcomes=sum(result.status == "disputed" for result in results),
        needs_review_outcomes=sum(result.status == "needs_review" for result in results),
        submitted_amount=submitted,
        confirmed_payable_amount=payable,
        recommended_deduction=disputed,
        needs_review_amount=review,
        supersedes_run_id=latest.id if latest else None,
        air_version_id=air_version_id,
        verification_plan_id=verification_plan_id,
    )
    session.add(run)
    session.flush()

    if comparison_report is not None:
        payload = _comparison_payload(comparison_report)
        session.add(
            PilotAgreementRuntimeComparisonRow(
                id=_id("PAIRCMP"),
                run_id=run.id,
                created_at=_now(),
                air_version=air_version_id,
                exact_match=(
                    comparison_report["exact_mismatches"] == 0
                    and comparison_report["amounts_match"] is True
                ),
                mismatch_count=int(comparison_report["exact_mismatches"]),
                report=payload,
            )
        )

    claim_by_external = {claim.external_outcome_id: claim for claim in claims}
    for result in results:
        claim = claim_by_external[result.claim.outcome_id]
        determination = PilotDeterminationRow(
            id=_id("PDET"),
            run_id=run.id,
            claim_id=claim.id,
            external_outcome_id=claim.external_outcome_id,
            rule_id=result.rule_id,
            status=result.status,
            reason=result.reason,
            billed_amount=result.claim.billed_amount,
            confirmed_payable_amount=result.confirmed_payable_amount,
            confirmed_disputed_amount=result.confirmed_disputed_amount,
            needs_review_amount=result.needs_review_amount,
            duplicate_winner_outcome_id=(
                result.duplicate_decision.winner_outcome_id if result.duplicate_decision else None
            ),
            evaluated_at=result.evaluated_at,
            engine_version=result.engine_version,
            rule_program_version=air_row.version_number,
            normalizer_version=MAPPING_VERSION,
            matching_version=MATCHING_VERSION,
        )
        session.add(determination)
        session.flush()
        for reference in result.evidence:
            session.add(
                PilotEvidenceReferenceRow(
                    determination_id=determination.id,
                    event_id=reference.event_id,
                    purpose=reference.purpose,
                )
            )
    state = ensure_pilot_state(session)
    state.active_invoice_id = invoice.id
    state.active_contract_id = contract.id
    state.updated_at = _now()
    record_audit(
        session,
        "reconciliation.completed",
        "reconciliation",
        run.id,
        invoice_id=invoice.id,
        air_version_id=air_version_id,
        submitted_amount=_money(submitted),
        payable_amount=_money(payable),
        disputed_amount=_money(disputed),
        needs_review_amount=_money(review),
    )
    session.flush()
    return reconciliation_summary(session, run.id)


def agreement_runtime_comparison(session: Session, run_id: str) -> dict[str, object]:
    run = session.get(PilotReconciliationRunRow, run_id)
    if run is None:
        raise LookupError("Pilot reconciliation run not found")
    row = session.scalar(
        select(PilotAgreementRuntimeComparisonRow).where(
            PilotAgreementRuntimeComparisonRow.run_id == run_id
        )
    )
    if row is None:
        raise LookupError("No Agreement IR comparison exists for this reconciliation run")
    return {
        "run_id": row.run_id,
        "created_at": row.created_at.isoformat(),
        "air_version": row.air_version,
        "exact_match": row.exact_match,
        "mismatch_count": row.mismatch_count,
        "report": row.report,
    }


def reconciliation_summary(session: Session, run_id: str | None = None) -> dict[str, object]:
    if run_id:
        run = session.get(PilotReconciliationRunRow, run_id)
    else:
        state = ensure_pilot_state(session)
        run = (
            session.scalar(
                select(PilotReconciliationRunRow)
                .where(PilotReconciliationRunRow.invoice_id == state.active_invoice_id)
                .order_by(PilotReconciliationRunRow.run_number.desc())
            )
            if state.active_invoice_id
            else None
        )
    if run is None:
        raise LookupError("No pilot reconciliation has been run")
    invoice = session.get(PilotInvoiceRow, run.invoice_id)
    contract = session.get(PilotContractRow, invoice.contract_id) if invoice else None
    determinations = session.scalars(
        select(PilotDeterminationRow)
        .where(PilotDeterminationRow.run_id == run.id)
        .order_by(PilotDeterminationRow.external_outcome_id)
    ).all()
    agreement: AgreementIR | None = None
    if run.air_version_id:
        air_row = session.get(PilotAIRVersionRow, run.air_version_id)
        if air_row is not None:
            agreement = AgreementIR.model_validate(air_row.air_json)
    currencies = (
        sorted({policy.currency for policy in agreement.settlement_policies}) if agreement else []
    )
    currency = currencies[0] if len(currencies) == 1 else ("MULTI" if currencies else "USD")
    categories: dict[str, dict[str, object]] = {}
    for row in determinations:
        if row.status == "disputed" and row.rule_id:
            item = categories.setdefault(
                row.rule_id,
                {"label": row.rule_id, "count": 0, "amount": Decimal()},
            )
            item["count"] = int(item["count"]) + 1
            item["amount"] = Decimal(str(item["amount"])) + row.confirmed_disputed_amount
    for item in categories.values():
        item["amount"] = _money(Decimal(str(item["amount"])))
    return {
        "reconciliation_id": run.id,
        "run_number": run.run_number,
        "supersedes_run_id": run.supersedes_run_id,
        "invoice_id": run.invoice_id,
        "contract_id": contract.id if contract else None,
        "customer": contract.customer if contract else None,
        "vendor": contract.vendor if contract else None,
        "billing_period_start": invoice.billing_period_start.isoformat() if invoice else None,
        "billing_period_end": invoice.billing_period_end.isoformat() if invoice else None,
        "status": "completed",
        "claimed_outcomes": run.claimed_outcomes,
        "payable_outcomes": run.payable_outcomes,
        "disputed_outcomes": run.disputed_outcomes,
        "needs_review_outcomes": run.needs_review_outcomes,
        "submitted_amount": _money(run.submitted_amount),
        "confirmed_payable_amount": _money(run.confirmed_payable_amount),
        "recommended_deduction": _money(run.recommended_deduction),
        "needs_review_amount": _money(run.needs_review_amount),
        "currency": currency,
        "currency_consistent": len(currencies) <= 1,
        "identified_dispute_percent": (
            f"{(run.recommended_deduction / run.submitted_amount * Decimal(100)):.1f}"
            if run.submitted_amount
            else "0.0"
        ),
        "categories": categories,
        "engine_version": run.engine_version,
        "rule_program_version": run.rule_program_version,
        "compilation_id": run.compilation_id,
        "normalizer_version": run.normalizer_version,
        "matching_version": run.matching_version,
        "air_version_id": run.air_version_id,
        "verification_plan_id": run.verification_plan_id,
        "real_data_disclosure": (
            "Pilot output generated from operator-uploaded data. Verify source permissions, "
            "identity matches, approved rules, and needs-review items before acting on money."
        ),
    }


def reconciliation_details(session: Session, run_id: str) -> list[dict[str, object]]:
    run = session.get(PilotReconciliationRunRow, run_id)
    if run is None:
        raise LookupError("Pilot reconciliation run not found")
    agreement: AgreementIR | None = None
    if run.air_version_id:
        air_row = session.get(PilotAIRVersionRow, run.air_version_id)
        if air_row is not None:
            agreement = AgreementIR.model_validate(air_row.air_json)
    clause_by_id = {clause.id: clause for clause in (agreement.clauses if agreement else [])}

    source_clause_ids_by_rule: dict[str, list[str]] = {}
    if agreement is not None:
        for norm in agreement.norms:
            aliases = {
                norm.id,
                norm.violation_reason_code,
                norm.indeterminate_rule_id,
            }
            for alias in [item for item in aliases if item]:
                source_clause_ids_by_rule[str(alias)] = list(norm.source_clause_ids)
        for policy in agreement.settlement_policies:
            source_clause_ids_by_rule[policy.id] = list(policy.source_clause_ids)

    rows = session.scalars(
        select(PilotDeterminationRow)
        .where(PilotDeterminationRow.run_id == run_id)
        .order_by(PilotDeterminationRow.external_outcome_id)
    ).all()
    result: list[dict[str, object]] = []
    for row in rows:
        evidence_rows = session.execute(
            select(PilotEvidenceReferenceRow, PilotEventRow)
            .join(PilotEventRow, PilotEvidenceReferenceRow.event_id == PilotEventRow.id)
            .where(PilotEvidenceReferenceRow.determination_id == row.id)
            .order_by(PilotEventRow.timestamp, PilotEventRow.id)
        ).all()
        source_clause_ids = source_clause_ids_by_rule.get(row.rule_id or "", [])
        contract_clauses = [
            {
                "id": clause_id,
                "text": clause_by_id[clause_id].text,
                "document_id": clause_by_id[clause_id].document_id,
                "source_start": clause_by_id[clause_id].source_start,
                "source_end": clause_by_id[clause_id].source_end,
                "text_hash": clause_by_id[clause_id].text_hash,
            }
            for clause_id in source_clause_ids
            if clause_id in clause_by_id
        ]
        evidence = [
            {
                "event_id": event.id,
                "purpose": reference.purpose,
                "source_system": event.source_system,
                "source_record_id": event.source_record_id,
                "event_type": event.event_type,
                "timestamp": event.timestamp.isoformat(),
                "match_method": event.match_method,
                "match_confidence": f"{event.match_confidence:.4f}",
            }
            for reference, event in evidence_rows
        ]
        trace = build_decision_trace(
            agreement,
            outcome_id=row.external_outcome_id,
            status=row.status,
            rule_id=row.rule_id,
            billed_amount=row.billed_amount,
            payable_amount=row.confirmed_payable_amount,
            disputed_amount=row.confirmed_disputed_amount,
            needs_review_amount=row.needs_review_amount,
            evidence=evidence,
        )
        result.append(
            {
                "outcome_id": row.external_outcome_id,
                "status": row.status,
                "rule_id": row.rule_id,
                "reason": row.reason,
                "rule_description": rule_description_for_id(agreement, row.rule_id),
                "billed_amount": _money(row.billed_amount),
                "confirmed_payable_amount": _money(row.confirmed_payable_amount),
                "confirmed_disputed_amount": _money(row.confirmed_disputed_amount),
                "needs_review_amount": _money(row.needs_review_amount),
                "engine_version": row.engine_version,
                "rule_program_version": row.rule_program_version,
                "normalizer_version": row.normalizer_version,
                "matching_version": row.matching_version,
                "contract_clauses": contract_clauses,
                "evidence": evidence,
                "trace": trace,
            }
        )
    return result


def evidence_package(session: Session, run_id: str) -> dict[str, object]:
    summary = reconciliation_summary(session, run_id)
    determinations = session.scalars(
        select(PilotDeterminationRow)
        .where(PilotDeterminationRow.run_id == run_id)
        .order_by(PilotDeterminationRow.external_outcome_id)
    ).all()
    items = []
    for determination in determinations:
        references = session.execute(
            select(PilotEvidenceReferenceRow, PilotEventRow, PilotRawRecordRow)
            .join(PilotEventRow, PilotEvidenceReferenceRow.event_id == PilotEventRow.id)
            .join(PilotRawRecordRow, PilotEventRow.raw_record_id == PilotRawRecordRow.id)
            .where(PilotEvidenceReferenceRow.determination_id == determination.id)
        ).all()
        items.append(
            {
                "outcome_id": determination.external_outcome_id,
                "status": determination.status,
                "rule_id": determination.rule_id,
                "reason": determination.reason,
                "evidence": [
                    {
                        "event_id": event.id,
                        "purpose": reference.purpose,
                        "source_system": event.source_system,
                        "source_record_id": event.source_record_id,
                        "timestamp": event.timestamp.isoformat(),
                        "event_type": event.event_type,
                        "raw_payload_hash": raw.payload_hash,
                        "raw_payload": raw.raw_payload,
                        "normalized_payload": raw.normalized_payload,
                        "parser_version": raw.parser_version,
                        "mapping_version": raw.mapping_version,
                        "normalization_warnings": raw.normalization_warnings,
                        "match_method": event.match_method,
                        "match_confidence": f"{event.match_confidence:.4f}",
                        "match_reason": event.match_reason,
                    }
                    for reference, event, raw in references
                ],
            }
        )
    return {"summary": summary, "determinations": items}


def compare_reconciliation_runs(
    session: Session,
    run_id: str,
    prior_run_id: str,
) -> dict[str, object]:
    current = session.get(PilotReconciliationRunRow, run_id)
    prior = session.get(PilotReconciliationRunRow, prior_run_id)
    if current is None or prior is None:
        raise LookupError("Pilot reconciliation run not found")
    if current.invoice_id != prior.invoice_id:
        raise ValueError("Only runs for the same invoice can be compared")
    current_rows = {
        row.external_outcome_id: row
        for row in session.scalars(
            select(PilotDeterminationRow).where(PilotDeterminationRow.run_id == current.id)
        ).all()
    }
    prior_rows = {
        row.external_outcome_id: row
        for row in session.scalars(
            select(PilotDeterminationRow).where(PilotDeterminationRow.run_id == prior.id)
        ).all()
    }
    outcome_ids = sorted(set(current_rows) | set(prior_rows))
    changes = []
    for outcome_id in outcome_ids:
        now_row = current_rows.get(outcome_id)
        old_row = prior_rows.get(outcome_id)
        before = old_row.status if old_row else None
        after = now_row.status if now_row else None
        before_disputed = old_row.confirmed_disputed_amount if old_row else Decimal()
        after_disputed = now_row.confirmed_disputed_amount if now_row else Decimal()
        if before == after and before_disputed == after_disputed:
            continue
        changes.append(
            {
                "outcome_id": outcome_id,
                "status_before": before,
                "status_after": after,
                "rule_before": old_row.rule_id if old_row else None,
                "rule_after": now_row.rule_id if now_row else None,
                "disputed_amount_before": _money(before_disputed),
                "disputed_amount_after": _money(after_disputed),
                "reason_before": old_row.reason if old_row else None,
                "reason_after": now_row.reason if now_row else None,
            }
        )
    return {
        "invoice_id": current.invoice_id,
        "run_id": current.id,
        "prior_run_id": prior.id,
        "changed_outcomes": len(changes),
        "recommended_deduction_before": _money(prior.recommended_deduction),
        "recommended_deduction_after": _money(current.recommended_deduction),
        "changes": changes,
    }


def create_customer_review(
    session: Session,
    *,
    run_id: str,
    reviewed_by: str,
    claims_sampled: int,
    confirmed_disputes: int,
    rejected_disputes: int,
    missing_disputes: int,
    estimated_overpayment_prevented: Decimal,
    estimated_hours_saved: Decimal,
    would_use_next_month: bool,
    willingness_to_pay: str,
    permission_to_quote: bool,
    notes: str,
) -> PilotCustomerReviewRow:
    if session.get(PilotReconciliationRunRow, run_id) is None:
        raise LookupError("Pilot reconciliation run not found")
    row = PilotCustomerReviewRow(
        id=_id("PREV"),
        run_id=run_id,
        reviewed_by=reviewed_by.strip(),
        reviewed_at=_now(),
        claims_sampled=claims_sampled,
        confirmed_disputes=confirmed_disputes,
        rejected_disputes=rejected_disputes,
        missing_disputes=missing_disputes,
        estimated_overpayment_prevented=estimated_overpayment_prevented,
        estimated_hours_saved=estimated_hours_saved,
        would_use_next_month=would_use_next_month,
        willingness_to_pay=willingness_to_pay.strip(),
        permission_to_quote=permission_to_quote,
        notes=notes.strip(),
    )
    session.add(row)
    record_audit(
        session,
        "reconciliation.reviewed",
        "reconciliation",
        run_id,
        review_id=row.id,
        reviewed_by=row.reviewed_by,
        confirmed_disputes=confirmed_disputes,
        rejected_disputes=rejected_disputes,
        missing_disputes=missing_disputes,
    )
    session.flush()
    return row


def customer_review_view(row: PilotCustomerReviewRow) -> dict[str, object]:
    return {
        "id": row.id,
        "run_id": row.run_id,
        "reviewed_by": row.reviewed_by,
        "reviewed_at": row.reviewed_at.isoformat(),
        "claims_sampled": row.claims_sampled,
        "confirmed_disputes": row.confirmed_disputes,
        "rejected_disputes": row.rejected_disputes,
        "missing_disputes": row.missing_disputes,
        "estimated_overpayment_prevented": _money(row.estimated_overpayment_prevented),
        "estimated_hours_saved": _money(row.estimated_hours_saved),
        "would_use_next_month": row.would_use_next_month,
        "willingness_to_pay": row.willingness_to_pay,
        "permission_to_quote": row.permission_to_quote,
        "notes": row.notes,
    }


def latest_customer_review(session: Session, run_id: str) -> dict[str, object]:
    row = session.scalar(
        select(PilotCustomerReviewRow)
        .where(PilotCustomerReviewRow.run_id == run_id)
        .order_by(PilotCustomerReviewRow.reviewed_at.desc())
    )
    if row is None:
        raise LookupError("No customer review recorded for this run")
    return customer_review_view(row)


def pilot_status(session: Session) -> dict[str, object]:
    state = ensure_pilot_state(session)
    invoice_id = state.active_invoice_id
    claim_count = (
        session.scalar(
            select(func.count())
            .select_from(PilotClaimRow)
            .where(PilotClaimRow.invoice_id == invoice_id)
        )
        if invoice_id
        else 0
    )
    event_count = (
        session.scalar(
            select(func.count())
            .select_from(PilotEventRow)
            .where(PilotEventRow.invoice_id == invoice_id)
        )
        if invoice_id
        else 0
    )
    accepted = (
        session.scalar(
            select(func.count())
            .select_from(PilotEventRow)
            .where(PilotEventRow.invoice_id == invoice_id, PilotEventRow.match_status == "accepted")
        )
        if invoice_id
        else 0
    )
    suggested = (
        session.scalar(
            select(func.count())
            .select_from(PilotEventRow)
            .where(
                PilotEventRow.invoice_id == invoice_id, PilotEventRow.match_status == "suggested"
            )
        )
        if invoice_id
        else 0
    )
    unresolved = (
        session.scalar(
            select(func.count())
            .select_from(PilotEventRow)
            .where(
                PilotEventRow.invoice_id == invoice_id,
                PilotEventRow.match_status.in_(["pending", "unresolved"]),
            )
        )
        if invoice_id
        else 0
    )
    latest_run = (
        session.scalar(
            select(PilotReconciliationRunRow)
            .where(PilotReconciliationRunRow.invoice_id == invoice_id)
            .order_by(PilotReconciliationRunRow.run_number.desc())
        )
        if invoice_id
        else None
    )
    uploads = session.scalars(
        select(PilotUploadRow).order_by(PilotUploadRow.uploaded_at.desc()).limit(50)
    ).all()
    approved_air = (
        session.scalar(
            select(PilotAIRVersionRow).where(
                PilotAIRVersionRow.contract_id == state.active_contract_id,
                PilotAIRVersionRow.approved_at.is_not(None),
                PilotAIRVersionRow.superseded_by_id.is_(None),
            )
        )
        if state.active_contract_id
        else None
    )
    approved_rules_current = False
    if approved_air is not None and state.active_contract_id:
        from app.upload.agreement_store import agreement_bundle_source_hash

        approved_rules_current = approved_air.source_bundle_hash == agreement_bundle_source_hash(
            session, state.active_contract_id
        )
    return {
        "workspace_id": current_workspace_id(),
        "initialized": state.initialized,
        "active_contract_id": state.active_contract_id,
        "contract_approved": bool(approved_air and approved_rules_current),
        "approved_rules_current": approved_rules_current,
        "approved_rules_stale": bool(approved_air and not approved_rules_current),
        "active_air_version_id": (
            approved_air.id if approved_air and approved_rules_current else None
        ),
        "active_invoice_id": invoice_id,
        "claims": int(claim_count or 0),
        "events": int(event_count or 0),
        "accepted_matches": int(accepted or 0),
        "suggested_matches": int(suggested or 0),
        "unresolved_events": int(unresolved or 0),
        "accepted_match_rate": (
            f"{int(accepted or 0) / int(event_count or 1) * 100:.1f}" if event_count else "0.0"
        ),
        "latest_reconciliation_id": latest_run.id if latest_run else None,
        "latest_run_number": latest_run.run_number if latest_run else None,
        "uploads": [
            {
                "id": row.id,
                "type": row.upload_type,
                "filename": row.filename,
                "uploaded_at": row.uploaded_at.isoformat(),
                "uploaded_by": row.uploaded_by,
                "status": row.status,
                "rows_accepted": row.rows_accepted,
                "rows_rejected": row.rows_rejected,
                "source_type": row.source_type,
                "coverage_complete": row.coverage_complete,
                "invoice_id": row.invoice_id,
                "sha256": row.sha256,
                "error_summary": row.error_summary,
            }
            for row in uploads
        ],
    }


def clear_pilot_data(session: Session) -> None:
    """Clear only the isolated pilot database. Demo state is unreachable here."""
    for model in (
        PilotAuditLogRow,
        PilotProvenanceEdgeRow,
        PilotFactRow,
        PilotEvidenceReferenceRow,
        PilotCustomerReviewRow,
        PilotDeterminationRow,
        PilotAgreementRuntimeComparisonRow,
        PilotReconciliationRunRow,
        PilotVerificationPlanRow,
        PilotEvidenceSourceDescriptorRow,
        PilotManualMatchRow,
        PilotIdentityMappingRow,
        PilotEventRow,
        PilotAIRVersionRow,
        PilotAgreementDocumentRelationRow,
        PilotAgreementDocumentRow,
        PilotAgreementBundleRow,
        PilotClaimRow,
        PilotRawRecordRow,
        PilotInvoiceRow,
        PilotContractRuleRow,
        PilotRuleCompilationRow,
        PilotContractRow,
        PilotUploadRejectionRow,
        PilotUploadRow,
        PilotStateRow,
    ):
        session.execute(delete(model))
    ensure_pilot_state(session)
