"""Deterministic sample workspace used by onboarding and product smoke tests."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.agreements.compiler import lower_to_agreement_ir
from app.agreements.native_compiler import NATIVE_PROMPT_VERSION, recorded_native_proposal
from app.contracts.compiler import DEFAULT_CONTRACT_PATH, sha256_text
from app.upload.agreement_store import (
    agreement_bundle_view,
    effective_source_documents,
    persist_auto_verification_plan,
)
from app.upload.models import PilotRuleCompilationRow
from app.upload.parsers import parse_evidence_jsonl, parse_invoice_csv
from app.upload.store import (
    approve_air_version,
    approve_contract_compilation,
    clear_pilot_data,
    compile_contract,
    create_contract,
    create_invoice,
    create_upload,
    finalize_upload,
    ingest_evidence_events,
    ingest_invoice_claims,
    persist_air_version,
    record_audit,
    run_identity_matching,
    run_pilot_reconciliation,
)

ROOT = Path(__file__).parents[3]

SAMPLE_INVOICE = """outcome_id,customer_reference,account_reference,claimed_outcome_type,claimed_completion_time,billed_amount,vendor_claim_id,vendor_disposition,conversation_id,agent_version
OUT-SAMPLE-001,CUST-SAMPLE-001,ACC-SAMPLE-001,order_support,2026-06-02T08:01:00,1.50,CLM-SAMPLE-001,resolved,CONV-SAMPLE-001,v4.2
OUT-SAMPLE-002,CUST-SAMPLE-002,ACC-SAMPLE-002,refund,2026-06-03T09:00:00,1.50,CLM-SAMPLE-002,resolved,CONV-SAMPLE-002,v4.2
OUT-SAMPLE-003,CUST-SAMPLE-003,ACC-SAMPLE-003,refund,2026-06-04T10:00:00,1.50,CLM-SAMPLE-003,resolved,CONV-SAMPLE-003,v4.2
"""

SAMPLE_EVIDENCE_ROWS = [
    {
        "event_id": "EV-S1-CLOSE",
        "event_type": "ai_closed",
        "occurred_at": "2026-06-02T08:01:00Z",
        "customer_id": "CUST-SAMPLE-001",
        "outcome_id": "OUT-SAMPLE-001",
    },
    {
        "event_id": "EV-S1-SUCCESS",
        "event_type": "downstream_succeeded",
        "occurred_at": "2026-06-02T08:31:00Z",
        "customer_id": "CUST-SAMPLE-001",
        "outcome_id": "OUT-SAMPLE-001",
        "account_id": "ACC-SAMPLE-001",
        "action": "order_support",
    },
    {
        "event_id": "EV-S2-CLOSE",
        "event_type": "ai_closed",
        "occurred_at": "2026-06-03T09:00:00Z",
        "customer_id": "CUST-SAMPLE-002",
        "outcome_id": "OUT-SAMPLE-002",
    },
    {
        "event_id": "EV-S2-RECONTACT",
        "event_type": "customer_recontact",
        "occurred_at": "2026-06-04T11:00:00Z",
        "customer_id": "CUST-SAMPLE-002",
        "outcome_id": "OUT-SAMPLE-002",
        "intent": "refund",
    },
    {
        "event_id": "EV-S2-HUMAN",
        "event_type": "human_completion",
        "occurred_at": "2026-06-03T12:00:00Z",
        "customer_id": "CUST-SAMPLE-002",
        "outcome_id": "OUT-SAMPLE-002",
        "action": "refund",
    },
    {
        "event_id": "EV-S2-SUCCESS",
        "event_type": "downstream_succeeded",
        "occurred_at": "2026-06-03T09:30:00Z",
        "customer_id": "CUST-SAMPLE-002",
        "outcome_id": "OUT-SAMPLE-002",
        "account_id": "ACC-SAMPLE-002",
        "action": "refund",
    },
    {
        "event_id": "EV-S2-MATCH",
        "event_type": "account_action_mismatch",
        "occurred_at": "2026-06-03T09:31:00Z",
        "customer_id": "CUST-SAMPLE-002",
        "outcome_id": "OUT-SAMPLE-002",
        "account_id": "ACC-SAMPLE-002",
        "action": "refund",
        "observed_account_id": "ACC-SAMPLE-002",
        "observed_action": "refund",
    },
    {
        "event_id": "EV-S3-CLOSE",
        "event_type": "ai_closed",
        "occurred_at": "2026-06-04T10:00:00Z",
        "customer_id": "CUST-SAMPLE-003",
        "outcome_id": "OUT-SAMPLE-003",
    },
]
SAMPLE_EVIDENCE = (
    "\n".join(json.dumps(row, separators=(",", ":")) for row in SAMPLE_EVIDENCE_ROWS) + "\n"
)


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def seed_sample_workspace(session: Session) -> dict[str, object]:
    """Reset the current workspace and seed a complete, auditable product journey."""
    clear_pilot_data(session)
    contract_text = DEFAULT_CONTRACT_PATH.read_text()
    contract_upload = create_upload(
        session,
        "contract",
        "sample-outcome-pricing-order-form.txt",
        contract_text.encode(),
        content_type="text/plain",
        uploaded_by="sample-onboarding",
    )
    contract_upload.status = "complete"
    contract_upload.rows_parsed = 1
    contract_upload.rows_accepted = 1
    contract = create_contract(
        session,
        contract_upload,
        customer="Acme Sample Co.",
        vendor="Nova AI (Sample)",
        period_start=datetime(2026, 6, 1),
        period_end=datetime(2026, 7, 1),
        price_per_outcome=Decimal("1.50"),
        source_document="sample-outcome-pricing-order-form.txt",
        source_text=contract_text,
    )

    # Retain a legacy compilation strictly for migration comparison/provenance.
    legacy = compile_contract(session, contract.id, mode="recorded")
    approve_contract_compilation(session, legacy.id)

    sources = effective_source_documents(session, contract.id, at=contract.period_start)
    bundle = agreement_bundle_view(session, contract.id)
    document_id, (title, text) = next(iter(sources.items()))
    native = recorded_native_proposal(
        contract_id=contract.id,
        document_id=document_id,
        title=title,
        contract_text=text,
    )
    latest_version = (
        session.scalar(
            select(func.max(PilotRuleCompilationRow.version)).where(
                PilotRuleCompilationRow.contract_id == contract.id
            )
        )
        or 0
    )
    compilation_id = f"NAIR-{uuid.uuid4().hex.upper()}"
    source_bundle_hash = sha256_text(
        json.dumps(
            {
                "documents": {
                    doc_id: sha256_text(doc_text) for doc_id, (_, doc_text) in sources.items()
                },
                "relations": bundle["relations"],
                "effective_at": contract.period_start.isoformat(),
            },
            sort_keys=True,
        )
    )
    air, conformance = lower_to_agreement_ir(
        native.proposal,
        compilation_id=compilation_id,
        version=int(latest_version) + 1,
        source_hash=source_bundle_hash,
    )
    compilation = PilotRuleCompilationRow(
        id=compilation_id,
        contract_id=contract.id,
        source_document="agreement-bundle",
        source_hash=source_bundle_hash,
        prompt_hash=native.prompt_hash,
        provider=native.provider,
        model=native.model,
        compiler_version=native.proposal.compiler_version,
        status="native_air_pending",
        version=int(latest_version) + 1,
        live_model_call=False,
        created_at=_now(),
        approved_at=None,
        rules=[],
        raw_response={
            **native.raw_response,
            "native_proposal": native.proposal.model_dump(mode="json"),
            "agreement_ir": air.model_dump(mode="json"),
            "conformance": conformance.model_dump(mode="json"),
        },
    )
    session.add(compilation)
    session.flush()
    air_row = persist_air_version(
        session,
        contract_id=contract.id,
        compilation_id=compilation_id,
        air=air,
        compiler_mode="native_recorded",
        source_hash=source_bundle_hash,
        compiler_model=native.model,
        prompt_version=NATIVE_PROMPT_VERSION,
    )
    approve_air_version(session, air_row.id, approved_by="sample-onboarding")
    compilation.status = "native_air_approved"
    compilation.approved_at = air_row.approved_at

    invoice_upload = create_upload(
        session,
        "invoice",
        "sample-invoice.csv",
        SAMPLE_INVOICE.encode(),
        content_type="text/csv",
        uploaded_by="sample-onboarding",
    )
    invoice_parse = parse_invoice_csv(SAMPLE_INVOICE)
    finalize_upload(session, invoice_upload, invoice_parse)
    invoice = create_invoice(
        session,
        invoice_upload,
        invoice_id="INV-SAMPLE-2026-06",
        contract_id=contract.id,
        billing_period_start=datetime(2026, 6, 1),
        billing_period_end=datetime(2026, 7, 1),
    )
    ingest_invoice_claims(session, invoice_upload, invoice_parse, invoice.id)

    evidence_upload = create_upload(
        session,
        "evidence",
        "sample-customer-evidence.jsonl",
        SAMPLE_EVIDENCE.encode(),
        "customer_systems",
        content_type="application/x-ndjson",
        uploaded_by="sample-onboarding",
        invoice_id=invoice.id,
        coverage_complete=True,
    )
    evidence_parse = parse_evidence_jsonl(SAMPLE_EVIDENCE, "customer_systems")
    finalize_upload(session, evidence_upload, evidence_parse)
    ingest_evidence_events(session, evidence_upload, evidence_parse, invoice.id)
    matching = run_identity_matching(session, invoice.id)
    plan = persist_auto_verification_plan(
        session,
        air_version_id=air_row.id,
        invoice_id=invoice.id,
    )
    reconciliation = run_pilot_reconciliation(session, invoice.id)
    record_audit(
        session,
        "workspace.sample_seeded",
        "workspace",
        None,
        contract_id=contract.id,
        invoice_id=invoice.id,
        air_version_id=air_row.id,
        verification_plan_id=plan.id,
    )
    return {
        "sample": True,
        "contract_id": contract.id,
        "invoice_id": invoice.id,
        "air_version_id": air_row.id,
        "verification_plan_id": plan.id,
        "matching": {
            "total_events": matching.total_events,
            "direct_matches": matching.direct_matches,
            "unresolved": matching.unresolved,
        },
        "reconciliation": reconciliation,
    }
