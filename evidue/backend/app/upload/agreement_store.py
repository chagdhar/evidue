"""Persistence for generalized agreement bundles, proof plans, and derived facts."""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.agreements.bundle import (
    AgreementBundle,
    AgreementDocument,
    DocumentRelation,
    DocumentRelationType,
    applicable_documents,
)
from app.agreements.capabilities import (
    EvidenceCapability,
    EvidenceSourceDescriptor,
    VerificationPlan,
    build_verification_plan,
    verification_readiness_summary,
)
from app.agreements.facts import FACT_DERIVER_VERSION, derive_facts
from app.agreements.models import AgreementIR, CommercialClaim, EvidenceAuthority, Expression
from app.upload.models import (
    PilotAgreementBundleRow,
    PilotAgreementDocumentRelationRow,
    PilotAgreementDocumentRow,
    PilotAIRVersionRow,
    PilotClaimRow,
    PilotContractRow,
    PilotEventRow,
    PilotEvidenceSourceDescriptorRow,
    PilotFactRow,
    PilotInvoiceRow,
    PilotProvenanceEdgeRow,
    PilotUploadRow,
    PilotVerificationPlanRow,
)


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex.upper()}"


def _hash_payload(payload: object) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def ensure_contract_bundle(session: Session, contract: PilotContractRow) -> PilotAgreementBundleRow:
    if contract.agreement_bundle_id:
        existing = session.get(PilotAgreementBundleRow, contract.agreement_bundle_id)
        if existing is not None:
            return existing
    bundle = PilotAgreementBundleRow(id=_id("PBUNDLE"), contract_id=contract.id, created_at=_now())
    session.add(bundle)
    session.flush()
    primary = PilotAgreementDocumentRow(
        id=_id("PDOC"),
        bundle_id=bundle.id,
        upload_id=contract.upload_id,
        title=contract.source_document,
        document_type="primary_agreement",
        filename=contract.source_document,
        effective_from=contract.period_start,
        effective_until=contract.period_end,
        precedence=100,
        source_hash=contract.source_hash,
        source_text=contract.source_text,
        parser_version="agreement-text-v1",
        created_at=_now(),
    )
    session.add(primary)
    contract.agreement_bundle_id = bundle.id
    session.flush()
    return bundle


def add_agreement_document(
    session: Session,
    *,
    contract_id: str,
    upload_id: str,
    title: str,
    document_type: str,
    filename: str,
    effective_from: datetime,
    effective_until: datetime | None,
    precedence: int,
    source_hash: str,
    source_text: str,
) -> PilotAgreementDocumentRow:
    contract = session.get(PilotContractRow, contract_id)
    if contract is None:
        raise LookupError("Pilot contract not found")
    if effective_until is not None and effective_until <= effective_from:
        raise ValueError("Document effective_until must be after effective_from")
    bundle = ensure_contract_bundle(session, contract)
    row = PilotAgreementDocumentRow(
        id=_id("PDOC"),
        bundle_id=bundle.id,
        upload_id=upload_id,
        title=title.strip(),
        document_type=document_type.strip(),
        filename=filename,
        effective_from=effective_from,
        effective_until=effective_until,
        precedence=precedence,
        source_hash=source_hash,
        source_text=source_text,
        parser_version="agreement-text-v1",
        created_at=_now(),
    )
    session.add(row)
    session.flush()
    return row


def add_document_relation(
    session: Session,
    *,
    contract_id: str,
    source_document_id: str,
    target_document_id: str,
    relation: DocumentRelationType,
) -> PilotAgreementDocumentRelationRow:
    contract = session.get(PilotContractRow, contract_id)
    if contract is None:
        raise LookupError("Pilot contract not found")
    bundle = ensure_contract_bundle(session, contract)
    source = session.get(PilotAgreementDocumentRow, source_document_id)
    target = session.get(PilotAgreementDocumentRow, target_document_id)
    if (
        source is None
        or target is None
        or source.bundle_id != bundle.id
        or target.bundle_id != bundle.id
    ):
        raise ValueError("Agreement relation documents must belong to the contract bundle")
    if source.id == target.id:
        raise ValueError("Agreement relation cannot reference the same document")
    if relation in {DocumentRelationType.AMENDS, DocumentRelationType.SUPERSEDES}:
        if source.effective_from < target.effective_from:
            raise ValueError("An amendment/superseding document cannot predate its target")
        if source.precedence <= target.precedence:
            raise ValueError("An amendment/superseding document must have higher precedence")
    row = PilotAgreementDocumentRelationRow(
        id=_id("PREL"),
        bundle_id=bundle.id,
        source_document_id=source.id,
        target_document_id=target.id,
        relation=relation.value,
        created_at=_now(),
    )
    session.add(row)
    session.flush()
    # Validate cycle/reference semantics against the full Pydantic bundle.
    _load_bundle(session, contract.id)
    return row


def _load_bundle(session: Session, contract_id: str) -> AgreementBundle:
    contract = session.get(PilotContractRow, contract_id)
    if contract is None:
        raise LookupError("Pilot contract not found")
    bundle_row = ensure_contract_bundle(session, contract)
    documents = session.scalars(
        select(PilotAgreementDocumentRow)
        .where(PilotAgreementDocumentRow.bundle_id == bundle_row.id)
        .order_by(PilotAgreementDocumentRow.precedence.desc(), PilotAgreementDocumentRow.created_at)
    ).all()
    relations = session.scalars(
        select(PilotAgreementDocumentRelationRow).where(
            PilotAgreementDocumentRelationRow.bundle_id == bundle_row.id
        )
    ).all()
    return AgreementBundle(
        id=bundle_row.id,
        parties={"customer": contract.customer, "vendor": contract.vendor},
        documents=[
            AgreementDocument(
                id=row.id,
                title=row.title,
                text=row.source_text,
                effective_from=row.effective_from,
                effective_until=row.effective_until,
                precedence=row.precedence,
                source_hash=row.source_hash,
            )
            for row in documents
        ],
        relations=[
            DocumentRelation(
                source_document_id=row.source_document_id,
                target_document_id=row.target_document_id,
                relation=DocumentRelationType(row.relation),
            )
            for row in relations
        ],
    )


def effective_source_documents(
    session: Session,
    contract_id: str,
    *,
    at: datetime,
) -> dict[str, tuple[str, str]]:
    bundle = _load_bundle(session, contract_id)
    docs = applicable_documents(bundle, at)
    if not docs:
        raise ValueError("Agreement bundle has no documents effective for the contract period")
    return {document.id: (document.title, document.text) for document in docs}


def agreement_bundle_internal_boundaries(
    session: Session, contract_id: str
) -> list[dict[str, str]]:
    """Return governing-document effective boundaries inside the configured contract period.

    The current pilot binds one approved AIR version to one configured contract period.
    A governing document that starts or ends inside that period would require temporal
    policy selection that this version does not silently approximate.
    """
    contract = session.get(PilotContractRow, contract_id)
    if contract is None:
        raise LookupError("Pilot contract not found")
    bundle = ensure_contract_bundle(session, contract)
    rows = session.scalars(
        select(PilotAgreementDocumentRow).where(PilotAgreementDocumentRow.bundle_id == bundle.id)
    ).all()
    boundaries: list[dict[str, str]] = []
    for row in rows:
        if contract.period_start < row.effective_from < contract.period_end:
            boundaries.append(
                {
                    "document_id": row.id,
                    "title": row.title,
                    "boundary": row.effective_from.isoformat(),
                    "kind": "starts",
                }
            )
        if (
            row.effective_until is not None
            and contract.period_start < row.effective_until < contract.period_end
        ):
            boundaries.append(
                {
                    "document_id": row.id,
                    "title": row.title,
                    "boundary": row.effective_until.isoformat(),
                    "kind": "ends",
                }
            )
    return sorted(boundaries, key=lambda item: (item["boundary"], item["title"]))


def ensure_single_governing_period(session: Session, contract_id: str) -> None:
    boundaries = agreement_bundle_internal_boundaries(session, contract_id)
    if not boundaries:
        return
    first = boundaries[0]
    raise ValueError(
        "The governing agreement changes inside the configured agreement period "
        f"({first['title']} {first['kind']} on {first['boundary'][:10]}). "
        "This pilot intentionally fails closed rather than applying one rule set across a "
        "mid-period contract change. Split the reconciliation into agreement periods that "
        "each have one governing rule set, then analyze and approve each period separately."
    )


def agreement_bundle_source_hash(session: Session, contract_id: str) -> str:
    """Hash the effective governing document set exactly as native compilation does."""
    from app.contracts.compiler import sha256_text

    contract = session.get(PilotContractRow, contract_id)
    if contract is None:
        raise LookupError("Pilot contract not found")
    source_documents = effective_source_documents(session, contract_id, at=contract.period_start)
    bundle = _load_bundle(session, contract_id)
    payload = {
        "documents": {doc_id: sha256_text(text) for doc_id, (_, text) in source_documents.items()},
        "relations": [item.model_dump(mode="json") for item in bundle.relations],
        "effective_at": contract.period_start.isoformat(),
    }
    return sha256_text(json.dumps(payload, sort_keys=True))


def agreement_bundle_view(session: Session, contract_id: str) -> dict[str, object]:
    contract = session.get(PilotContractRow, contract_id)
    if contract is None:
        raise LookupError("Pilot contract not found")
    bundle = _load_bundle(session, contract_id)
    effective_ids = {item.id for item in applicable_documents(bundle, contract.period_start)}
    rows = session.scalars(
        select(PilotAgreementDocumentRow).where(PilotAgreementDocumentRow.bundle_id == bundle.id)
    ).all()
    metadata_by_id = {row.id: row for row in rows}
    return {
        "id": bundle.id,
        "contract_id": contract.id,
        "parties": bundle.parties,
        "effective_at": contract.period_start.isoformat(),
        "internal_effective_boundaries": agreement_bundle_internal_boundaries(session, contract.id),
        "documents": [
            {
                "id": item.id,
                "title": item.title,
                "document_type": metadata_by_id[item.id].document_type
                if item.id in metadata_by_id
                else "agreement",
                "filename": metadata_by_id[item.id].filename
                if item.id in metadata_by_id
                else item.title,
                "effective_from": item.effective_from.isoformat(),
                "effective_until": item.effective_until.isoformat()
                if item.effective_until
                else None,
                "precedence": item.precedence,
                "source_hash": item.source_hash,
                "effective": item.id in effective_ids,
            }
            for item in bundle.documents
        ],
        "relations": [item.model_dump(mode="json") for item in bundle.relations],
    }


def persist_verification_plan(
    session: Session,
    *,
    air_version_id: str,
    sources: list[EvidenceSourceDescriptor],
) -> PilotVerificationPlanRow:
    air_row = session.get(PilotAIRVersionRow, air_version_id)
    if air_row is None:
        raise LookupError("AIR version not found")
    if air_row.approved_at is None:
        raise ValueError("Verification plans require an approved AIR version")
    agreement = AgreementIR.model_validate(air_row.air_json)
    plan = build_verification_plan(agreement.agreement_id, agreement.proof_requirements, sources)
    source_version = (
        session.scalar(
            select(func.max(PilotEvidenceSourceDescriptorRow.version)).where(
                PilotEvidenceSourceDescriptorRow.contract_id == air_row.contract_id
            )
        )
        or 0
    ) + 1
    for source in sources:
        payload = source.model_dump(mode="json")
        session.add(
            PilotEvidenceSourceDescriptorRow(
                id=_id("PSRC"),
                contract_id=air_row.contract_id,
                version=int(source_version),
                source_id=source.source_id,
                descriptor=payload,
                payload_hash=_hash_payload(payload),
                created_at=_now(),
            )
        )
    plan_version = (
        session.scalar(
            select(func.max(PilotVerificationPlanRow.version)).where(
                PilotVerificationPlanRow.air_version_id == air_version_id
            )
        )
        or 0
    ) + 1
    payload = plan.model_dump(mode="json")
    row = PilotVerificationPlanRow(
        id=_id("PPLAN"),
        contract_id=air_row.contract_id,
        air_version_id=air_version_id,
        version=int(plan_version),
        plan_json=payload,
        payload_hash=_hash_payload(payload),
        created_at=_now(),
    )
    session.add(row)
    session.flush()
    return row


def verification_plan_view(row: PilotVerificationPlanRow) -> dict[str, object]:
    plan = VerificationPlan.model_validate(row.plan_json)
    return {
        "id": row.id,
        "contract_id": row.contract_id,
        "air_version_id": row.air_version_id,
        "version": row.version,
        "created_at": row.created_at.isoformat(),
        "payload_hash": row.payload_hash,
        "plan": row.plan_json,
        "readiness": verification_readiness_summary(plan),
    }


def latest_verification_plan(
    session: Session, air_version_id: str
) -> PilotVerificationPlanRow | None:
    return session.scalar(
        select(PilotVerificationPlanRow)
        .where(PilotVerificationPlanRow.air_version_id == air_version_id)
        .order_by(PilotVerificationPlanRow.version.desc())
    )


def _expression_event_types(expression: Expression) -> set[str]:
    event_types: set[str] = set()
    if expression.operator in {"exists_event", "not_exists_event"}:
        event_types.update(str(item) for item in expression.parameters.get("event_types", []))
    elif expression.operator == "terminal_event_outcome":
        event_types.update(
            str(item) for item in expression.parameters.get("success_event_types", [])
        )
        event_types.update(
            str(item) for item in expression.parameters.get("failure_event_types", [])
        )
    for operand in expression.operands:
        event_types.update(_expression_event_types(operand))
    return event_types


def infer_evidence_sources(
    session: Session,
    *,
    air_version_id: str,
    invoice_id: str,
) -> list[EvidenceSourceDescriptor]:
    """Infer conservative source capabilities from normalized uploaded data.

    Inference never invents absence guarantees: a source can prove absence only
    when the operator explicitly marked the upload as a complete export.  A
    capability is advertised only for event types actually observed somewhere
    in that source export, so a sparse upload cannot masquerade as a system of
    record.
    """
    air_row = session.get(PilotAIRVersionRow, air_version_id)
    if air_row is None or air_row.approved_at is None:
        raise ValueError("Automatic verification planning requires an approved AIR version")
    invoice = session.get(PilotInvoiceRow, invoice_id)
    if invoice is None:
        raise LookupError("Pilot invoice not found")
    if invoice.contract_id != air_row.contract_id:
        raise ValueError("Invoice and AIR version belong to different contracts")
    agreement = AgreementIR.model_validate(air_row.air_json)
    predicate_by_id = {item.id: item for item in agreement.predicates}

    descriptors: list[EvidenceSourceDescriptor] = []

    # Invoice claims are intentionally represented as vendor assertions.  This
    # allows the planner to expose when the agreement demands independent or
    # customer-side corroboration rather than silently upgrading invoice data.
    claim_fields = {
        "invoice_id",
        "outcome_id",
        "customer_id",
        "intent",
        "vendor_claim",
        "closed_at",
        "expected_action",
        "account_id",
        "billed_amount",
    }
    invoice_caps: list[EvidenceCapability] = []
    for requirement in agreement.proof_requirements:
        predicate = predicate_by_id.get(requirement.predicate_id)
        if predicate is None or _expression_event_types(predicate.expression):
            continue
        for fact_type in requirement.acceptable_fact_types:
            invoice_caps.append(
                EvidenceCapability(
                    fact_type=fact_type,
                    entity_type=requirement.required_entity_type or "outcome",
                    fields=sorted(claim_fields),
                    authority=EvidenceAuthority.VENDOR_ASSERTION,
                    identity_keys=["invoice_id", "outcome_id", "customer_id", "account_id"],
                    parser_version="upload-v2",
                    historical_snapshots=True,
                    absence_provable=False,
                    completeness_guarantee="invoice_rows_only",
                )
            )
    if invoice_caps:
        descriptors.append(
            EvidenceSourceDescriptor(
                source_id=f"invoice:{invoice_id}",
                source_type="vendor_invoice",
                system="uploaded_invoice",
                capabilities=invoice_caps,
            )
        )

    uploads = session.scalars(
        select(PilotUploadRow).where(
            PilotUploadRow.invoice_id == invoice_id,
            PilotUploadRow.upload_type == "evidence",
            PilotUploadRow.status.in_(["complete", "partial"]),
        )
    ).all()
    for upload in uploads:
        events = session.scalars(
            select(PilotEventRow).where(PilotEventRow.upload_id == upload.id)
        ).all()
        by_system: dict[str, list[PilotEventRow]] = {}
        for event in events:
            by_system.setdefault(event.source_system, []).append(event)
        for system, source_events in sorted(by_system.items()):
            observed_types = {event.event_type for event in source_events}
            fields = {"id", "event_type", "timestamp", "customer_id", "outcome_id", "source_system"}
            for event in source_events:
                fields.update(str(key) for key in (event.values or {}))
            identity_keys = [
                key
                for key in ["outcome_id", "customer_id", "account_id", "conversation_id"]
                if key in fields
            ]
            caps: list[EvidenceCapability] = []
            for requirement in agreement.proof_requirements:
                predicate = predicate_by_id.get(requirement.predicate_id)
                if predicate is None:
                    continue
                required_event_types = _expression_event_types(predicate.expression)
                if not required_event_types:
                    continue
                # Strong evidence of capability: the normalized export contains
                # at least one event type used by this predicate. A complete
                # export can then prove per-claim absence of that same type.
                if not (required_event_types & observed_types):
                    continue
                for fact_type in requirement.acceptable_fact_types:
                    caps.append(
                        EvidenceCapability(
                            fact_type=fact_type,
                            entity_type=requirement.required_entity_type or "outcome",
                            fields=sorted(fields),
                            event_types=sorted(observed_types),
                            authority=EvidenceAuthority.CUSTOMER_SYSTEM_OF_RECORD,
                            identity_keys=identity_keys,
                            timestamp_semantics="event_time",
                            source_timezone="UTC",
                            historical_snapshots=True,
                            absence_provable=bool(upload.coverage_complete),
                            completeness_guarantee=(
                                "operator_declared_complete_export"
                                if upload.coverage_complete
                                else "observed_rows_only"
                            ),
                            parser_version="upload-v2",
                        )
                    )
            if caps:
                descriptors.append(
                    EvidenceSourceDescriptor(
                        source_id=f"upload:{upload.id}:{system}",
                        source_type=upload.source_type or "evidence",
                        system=system,
                        capabilities=caps,
                    )
                )
    return descriptors


def persist_auto_verification_plan(
    session: Session,
    *,
    air_version_id: str,
    invoice_id: str,
) -> PilotVerificationPlanRow:
    sources = infer_evidence_sources(
        session,
        air_version_id=air_version_id,
        invoice_id=invoice_id,
    )
    return persist_verification_plan(session, air_version_id=air_version_id, sources=sources)


def derive_and_persist_facts(
    session: Session,
    *,
    invoice_id: str,
    air_version_id: str,
) -> list[PilotFactRow]:
    air_row = session.get(PilotAIRVersionRow, air_version_id)
    if air_row is None or air_row.approved_at is None:
        raise ValueError("Derived facts require an approved AIR version")
    agreement = AgreementIR.model_validate(air_row.air_json)
    claims = session.scalars(
        select(PilotClaimRow).where(PilotClaimRow.invoice_id == invoice_id)
    ).all()
    events = session.scalars(
        select(PilotEventRow).where(
            PilotEventRow.invoice_id == invoice_id,
            PilotEventRow.match_status == "accepted",
        )
    ).all()
    events_by_claim: dict[str, list[PilotEventRow]] = {}
    for event in events:
        if event.matched_claim_id:
            events_by_claim.setdefault(event.matched_claim_id, []).append(event)

    created: list[PilotFactRow] = []
    for claim in claims:
        commercial_claim = CommercialClaim(
            id=claim.external_outcome_id,
            claim_type="outcome",
            submitted_amount=f"{claim.billed_amount:.2f}",
            fields={
                "outcome_id": claim.external_outcome_id,
                "invoice_id": claim.invoice_id,
                "customer_id": claim.customer_id,
                "intent": claim.intent,
                "vendor_claim": claim.vendor_claim,
                "closed_at": claim.closed_at,
                "expected_action": claim.expected_action,
                "account_id": claim.account_id,
                "billed_amount": claim.billed_amount,
            },
        )
        event_payloads = [
            {
                "id": event.id,
                "event_type": event.event_type,
                "timestamp": event.timestamp,
                "customer_id": event.customer_id,
                "outcome_id": claim.external_outcome_id,
                **event.values,
            }
            for event in events_by_claim.get(claim.id, [])
        ]
        for fact in derive_facts(agreement, commercial_claim, event_payloads):
            existing = session.scalar(
                select(PilotFactRow).where(
                    PilotFactRow.claim_id == claim.id,
                    PilotFactRow.air_version_id == air_version_id,
                    PilotFactRow.fact_type == fact.fact_type,
                    PilotFactRow.predicate_id == fact.predicate_id,
                    PilotFactRow.input_hash == fact.input_hash,
                )
            )
            if existing is not None:
                created.append(existing)
                continue
            row = PilotFactRow(
                id=_id("PFACT"),
                invoice_id=invoice_id,
                claim_id=claim.id,
                air_version_id=air_version_id,
                fact_type=fact.fact_type,
                predicate_id=fact.predicate_id,
                truth=fact.truth.value,
                value={"value": fact.value} if fact.value is not None else None,
                evidence_ids=fact.evidence_ids,
                authority=fact.authority.value,
                derivation_method="deterministic_air_expression",
                evaluator_version=fact.evaluator_version or FACT_DERIVER_VERSION,
                input_hash=fact.input_hash or _hash_payload(fact.model_dump(mode="json")),
                created_at=_now(),
                review_status="not_required"
                if fact.truth.value in {"true", "false"}
                else "pending",
            )
            session.add(row)
            session.flush()
            created.append(row)
            for evidence_id in fact.evidence_ids:
                session.add(
                    PilotProvenanceEdgeRow(
                        id=_id("PPROV"),
                        invoice_id=invoice_id,
                        source_id=evidence_id,
                        target_id=row.id,
                        relation="supports",
                        created_at=_now(),
                    )
                )
    session.flush()
    return created


def facts_view(rows: list[PilotFactRow]) -> list[dict[str, object]]:
    return [
        {
            "id": row.id,
            "invoice_id": row.invoice_id,
            "claim_id": row.claim_id,
            "air_version_id": row.air_version_id,
            "fact_type": row.fact_type,
            "predicate_id": row.predicate_id,
            "truth": row.truth,
            "value": row.value,
            "evidence_ids": row.evidence_ids,
            "authority": row.authority,
            "derivation_method": row.derivation_method,
            "evaluator_version": row.evaluator_version,
            "model_name": row.model_name,
            "prompt_version": row.prompt_version,
            "confidence": row.confidence,
            "explanation": row.explanation,
            "input_hash": row.input_hash,
            "created_at": row.created_at.isoformat(),
            "review_status": row.review_status,
            "reviewed_truth": row.reviewed_truth,
            "review_rationale": row.review_rationale,
            "reviewed_by": row.reviewed_by,
            "reviewed_at": row.reviewed_at.isoformat() if row.reviewed_at else None,
        }
        for row in rows
    ]
