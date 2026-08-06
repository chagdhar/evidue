"""Persistence and orchestration for the isolated real-data pilot path."""

from __future__ import annotations

import hashlib
import os
import re
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session

from app.contracts.compiler import (
    DEFAULT_CONTRACT_PATH,
    compile_with_gemini,
    load_recorded_proposal,
    sha256_text,
)
from app.domain.engine import reconcile
from app.domain.models import ExecutableRule, OperationalEvent, OutcomeClaim, RuleProgram
from app.upload.match import (
    ClaimIdentity,
    IdentityMapping,
    MatchCandidate,
    MatchingSummary,
    run_matching,
)
from app.upload.models import (
    PilotClaimRow,
    PilotContractRow,
    PilotContractRuleRow,
    PilotCustomerReviewRow,
    PilotDeterminationRow,
    PilotEventRow,
    PilotEvidenceReferenceRow,
    PilotIdentityMappingRow,
    PilotInvoiceRow,
    PilotManualMatchRow,
    PilotRawRecordRow,
    PilotReconciliationRunRow,
    PilotRuleCompilationRow,
    PilotStateRow,
    PilotUploadRejectionRow,
    PilotUploadRow,
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


def ensure_pilot_state(session: Session) -> PilotStateRow:
    state = session.get(PilotStateRow, 1)
    if state is None:
        state = PilotStateRow(id=1, initialized=True, updated_at=_now())
        session.add(state)
        session.flush()
    return state


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
        invoice_id=invoice_id,
        sha256=_hash_bytes(content),
    )
    session.add(upload)
    session.flush()
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
    state = ensure_pilot_state(session)
    state.active_contract_id = contract.id
    state.updated_at = _now()
    session.flush()
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
            "Custom pilot contracts require GEMINI_API_KEY. The recorded proposal may only be "
            "used with the bundled demo contract."
        )
    if use_live:
        result = compile_with_gemini(
            contract.source_text,
            contract.id,
            contract.source_document,
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
    row = PilotRuleCompilationRow(
        id=_id("PCOMP"),
        contract_id=contract.id,
        source_document=contract.source_document,
        source_hash=result.source_hash,
        prompt_hash=result.prompt_hash,
        provider=result.proposal.provider,
        model=result.proposal.model,
        compiler_version=result.proposal.compiler_version,
        status="pending_approval",
        version=int(latest_version) + 1,
        live_model_call=result.live_model_call,
        created_at=_now(),
        approved_at=None,
        rules=[rule.model_dump(mode="json") for rule in result.proposal.rules],
        raw_response={**result.raw_response, "source_text": contract.source_text},
    )
    session.add(row)
    session.flush()
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


def run_pilot_reconciliation(session: Session, invoice_id: str) -> dict[str, object]:
    invoice = session.get(PilotInvoiceRow, invoice_id)
    if invoice is None:
        raise LookupError("Pilot invoice not found")
    contract = session.get(PilotContractRow, invoice.contract_id)
    if contract is None:
        raise LookupError("Pilot contract not found")
    program = _rule_program(session, contract)
    claims = session.scalars(
        select(PilotClaimRow)
        .where(PilotClaimRow.invoice_id == invoice.id)
        .order_by(PilotClaimRow.external_outcome_id)
    ).all()
    if not claims:
        raise ValueError("Pilot invoice has no accepted claims")
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
    results = reconcile(
        [
            (
                _domain_claim(claim),
                [_domain_event(event, claim) for event in events_by_claim.get(claim.id, [])],
            )
            for claim in claims
        ],
        program=program,
    )
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
        compilation_id=program.compilation_id,
        run_number=run_number,
        started_at=_now(),
        completed_at=_now(),
        engine_version=program.engine_version,
        rule_program_version=program.version,
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
    )
    session.add(run)
    session.flush()
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
            rule_program_version=program.version,
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
    session.flush()
    return reconciliation_summary(session, run.id)


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
        "status": "completed",
        "claimed_outcomes": run.claimed_outcomes,
        "payable_outcomes": run.payable_outcomes,
        "disputed_outcomes": run.disputed_outcomes,
        "needs_review_outcomes": run.needs_review_outcomes,
        "submitted_amount": _money(run.submitted_amount),
        "confirmed_payable_amount": _money(run.confirmed_payable_amount),
        "recommended_deduction": _money(run.recommended_deduction),
        "needs_review_amount": _money(run.needs_review_amount),
        "categories": categories,
        "engine_version": run.engine_version,
        "rule_program_version": run.rule_program_version,
        "compilation_id": run.compilation_id,
        "normalizer_version": run.normalizer_version,
        "matching_version": run.matching_version,
        "real_data_disclosure": (
            "Pilot output generated from operator-uploaded data. Verify source permissions, "
            "identity matches, approved rules, and needs-review items before acting on money."
        ),
    }


def reconciliation_details(session: Session, run_id: str) -> list[dict[str, object]]:
    rows = session.scalars(
        select(PilotDeterminationRow)
        .where(PilotDeterminationRow.run_id == run_id)
        .order_by(PilotDeterminationRow.external_outcome_id)
    ).all()
    return [
        {
            "outcome_id": row.external_outcome_id,
            "status": row.status,
            "rule_id": row.rule_id,
            "reason": row.reason,
            "billed_amount": _money(row.billed_amount),
            "confirmed_payable_amount": _money(row.confirmed_payable_amount),
            "confirmed_disputed_amount": _money(row.confirmed_disputed_amount),
            "needs_review_amount": _money(row.needs_review_amount),
            "engine_version": row.engine_version,
            "rule_program_version": row.rule_program_version,
            "normalizer_version": row.normalizer_version,
            "matching_version": row.matching_version,
        }
        for row in rows
    ]


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
    contract = (
        session.get(PilotContractRow, state.active_contract_id)
        if state.active_contract_id
        else None
    )
    return {
        "initialized": state.initialized,
        "active_contract_id": state.active_contract_id,
        "contract_approved": bool(contract and contract.active_compilation_id),
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
        PilotEvidenceReferenceRow,
        PilotCustomerReviewRow,
        PilotDeterminationRow,
        PilotReconciliationRunRow,
        PilotManualMatchRow,
        PilotIdentityMappingRow,
        PilotEventRow,
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
