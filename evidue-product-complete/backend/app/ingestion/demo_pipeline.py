from __future__ import annotations

import hashlib
import json
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any

from app.fixtures.demo import DemoRecord

RECEIVED_AT = datetime(2026, 7, 1, 8)
MATCHED_AT = datetime(2026, 7, 1, 8, 5)
SCHEMA_VERSION = "2026-06-01"


@dataclass(frozen=True)
class ConnectorSpec:
    id: str
    name: str
    category: str
    owner: str
    authority: str
    collection_method: str
    production_method: str
    source_format: str
    schedule: str
    description: str
    fields: tuple[str, ...]
    trust_boundary: str


@dataclass(frozen=True)
class RawRecord:
    id: str
    connector_id: str
    source_record_id: str
    record_type: str
    occurred_at: datetime | None
    received_at: datetime
    payload: dict[str, Any]
    normalized_payload: dict[str, Any]
    payload_hash: str
    match_status: str
    matched_outcome_id: str | None
    match_method: str
    match_confidence: Decimal
    match_reason: str
    schema_version: str = SCHEMA_VERSION


@dataclass(frozen=True)
class NormalizedClaim:
    outcome_id: str
    invoice_id: str
    customer_id: str
    intent: str
    vendor_claim: str
    closed_at: datetime
    expected_action: str
    account_id: str
    billed_amount: Decimal
    vendor_claim_id: str
    external_conversation_id: str
    agent_version: str
    raw_record_id: str | None


@dataclass(frozen=True)
class NormalizedConversation:
    id: str
    outcome_id: str
    customer_id: str
    intent: str
    closed_at: datetime


@dataclass(frozen=True)
class NormalizedEvent:
    id: str
    source_system: str
    source_record_id: str
    event_type: str
    timestamp: datetime
    customer_id: str
    outcome_id: str | None
    values: dict[str, str]
    ingested_at: datetime
    connector_id: str
    raw_record_id: str | None
    match_method: str
    match_confidence: Decimal
    payload_hash: str
    schema_version: str
    source_locator: str
    external_keys: dict[str, str]


@dataclass(frozen=True)
class ConnectorSnapshot:
    connector: ConnectorSpec
    records_received: int
    records_normalized: int
    records_rejected: int


@dataclass(frozen=True)
class IngestionStats:
    claims_received: int
    direct_matches: int
    secondary_matches: int
    unresolved_matches: int
    source_records_received: int
    source_records_normalized: int
    source_records_rejected: int


@dataclass(frozen=True)
class IngestionBundle:
    connectors: tuple[ConnectorSnapshot, ...]
    raw_samples: tuple[RawRecord, ...]
    claims: tuple[NormalizedClaim, ...]
    conversations: tuple[NormalizedConversation, ...]
    events: tuple[NormalizedEvent, ...]
    stats: IngestionStats


CONNECTORS = (
    ConnectorSpec(
        "vendor_claim_manifest",
        "Vendor claim manifest",
        "Invoice claims",
        "Nova Support AI",
        "Vendor assertion",
        "CSV upload",
        "SFTP, object storage, or invoice API",
        "CSV",
        "Per invoice",
        "The outcome-level claim manifest behind the vendor invoice.",
        (
            "vendor_claim_id",
            "outcome_id",
            "conversation_id",
            "customer_reference",
            "claimed_outcome_type",
            "claimed_completion_time",
            "billed_amount",
            "agent_version",
        ),
        "Declares what the vendor wants to bill; it does not determine payability.",
    ),
    ConnectorSpec(
        "vendor_agent_log",
        "Vendor agent execution log",
        "Vendor evidence",
        "Nova Support AI",
        "Vendor evidence",
        "JSONL fixture",
        "Vendor API, webhook, or signed object-store delivery",
        "JSONL",
        "Hourly or per invoice",
        "Execution receipts emitted by the vendor's agent runtime.",
        (
            "event_id",
            "outcome_id",
            "event_type",
            "occurred_at",
            "account_reference",
            "action",
            "agent_version",
        ),
        "Useful supporting evidence, but never a customer system of record.",
    ),
    ConnectorSpec(
        "support_desk",
        "Customer support desk",
        "Conversation evidence",
        "Acme Commerce",
        "Customer system of record",
        "Zendesk-style API fixture",
        "Read-only OAuth API, warehouse view, or scheduled export",
        "JSON",
        "Every 15 minutes",
        "Ticket state, customer recontacts, assignments, and human intervention.",
        (
            "ticket_id",
            "conversation_id",
            "customer_id",
            "intent",
            "status",
            "assignee_type",
            "occurred_at",
        ),
        "Customer-owned evidence is not visible or editable by the vendor.",
    ),
    ConnectorSpec(
        "payment_processor",
        "Payment processor",
        "Financial evidence",
        "Acme Commerce",
        "Customer financial record",
        "Stripe-style webhook fixture",
        "Read-only payment API plus webhooks",
        "JSON",
        "Near real time",
        "Refund, credit, and transaction results proving whether money moved.",
        (
            "transaction_id",
            "account_id",
            "action",
            "result",
            "amount",
            "occurred_at",
            "metadata",
        ),
        "Authoritative for payment state; Evidue receives read-only access.",
    ),
    ConnectorSpec(
        "product_operations",
        "Product operations ledger",
        "Operational evidence",
        "Acme Commerce",
        "Customer operational record",
        "Warehouse-table fixture",
        "Read-only Snowflake, BigQuery, or Redshift view",
        "Table rows",
        "Hourly batch",
        "Account changes and downstream actions proving customer state changed.",
        (
            "operation_id",
            "account_id",
            "action",
            "result",
            "observed_account_id",
            "occurred_at",
        ),
        "Read-only customer data; only approved columns are exposed.",
    ),
    ConnectorSpec(
        "billing_ledger",
        "Billing and attribution ledger",
        "Billing history",
        "Acme Commerce",
        "Customer billing record",
        "CSV ledger fixture",
        "Warehouse view, SFTP, or billing API",
        "CSV",
        "Daily",
        "Prior billed outcomes and attribution records used to identify duplicates.",
        (
            "ledger_record_id",
            "outcome_id",
            "customer_id",
            "normalized_intent",
            "original_outcome_id",
            "occurred_at",
        ),
        "Customer-owned billing history is independent of the current vendor invoice.",
    ),
    ConnectorSpec(
        "identity_map",
        "Customer identity map",
        "Identity resolution",
        "Acme Commerce",
        "Customer master data",
        "Warehouse mapping fixture",
        "Read-only customer-data view",
        "Table rows",
        "Daily",
        "Maps support, product, and payment identifiers across systems.",
        (
            "customer_id",
            "conversation_id",
            "account_id",
            "payment_customer_id",
        ),
        "Used only to join approved identifiers; raw PII is not required for the demo.",
    ),
    ConnectorSpec(
        "contract_documents",
        "Contract documents",
        "Commercial rules",
        "Acme Commerce",
        "Customer-approved commercial terms",
        "Document upload",
        "Secure upload plus approved rule versioning",
        "PDF and structured rules",
        "On signature or amendment",
        "The signed outcome definition, exclusions, and approved executable rules.",
        (
            "contract_id",
            "document_name",
            "effective_period",
            "pricing_model",
            "approved_rule_ids",
            "document_hash",
        ),
        "AI may extract candidate rules, but a customer approver activates each version.",
    ),
)

CONNECTOR_BY_SOURCE_SYSTEM = {
    "nova_agent": "vendor_agent_log",
    "acme_support": "support_desk",
    "payment_processor": "payment_processor",
    "order_operations": "product_operations",
    "product_accounts": "product_operations",
    "billing_export": "billing_ledger",
}


def _hash(payload: dict[str, Any]) -> str:
    material = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(material.encode()).hexdigest()


def _raw_id(connector_id: str, source_record_id: str) -> str:
    return f"RAW-{connector_id}-{source_record_id}"


def _suffix(outcome_id: str) -> str:
    return outcome_id.replace("OUT-", "").replace("CASE-", "CASE-")


def _secondary_match_outcomes(records: list[DemoRecord], scenario_id: str) -> set[str]:
    if scenario_id != "headline":
        return set()
    # Exactly 25 headline claims demonstrate production-style joins without
    # changing the deterministic payable result.
    return {record.claim.outcome_id for record in records[-25:]}


def _should_sample(outcome_id: str, secondary: bool, event_type: str | None = None) -> bool:
    return (
        outcome_id in {"OUT-004821", "OUT-001381", "OUT-001900", "CASE-REVIEW-001"}
        or secondary
        or event_type == "account_action_mismatch"
    )


def build_ingestion_bundle(records: list[DemoRecord], scenario_id: str) -> IngestionBundle:
    raw_samples: list[RawRecord] = []
    claims: list[NormalizedClaim] = []
    conversations: list[NormalizedConversation] = []
    events: list[NormalizedEvent] = []
    connector_counts: Counter[str] = Counter()
    secondary_outcomes = _secondary_match_outcomes(records, scenario_id)

    contract_payload = {
        "contract_id": "CONTRACT-ACME-NOVA-2026",
        "document_name": "Acme-Nova-Outcome-Pricing-Order-Form.pdf",
        "effective_period": "2026-06-01/2026-07-01",
        "pricing_model": "$1.50 per supported outcome",
        "approved_rule_ids": ["R1", "R2", "R3", "R4", "R5", "R6", "R7"],
        "document_hash": "sha256:demo-contract-2026-06",
    }
    raw_samples.append(
        RawRecord(
            id=_raw_id("contract_documents", "CONTRACT-ACME-NOVA-2026"),
            connector_id="contract_documents",
            source_record_id="CONTRACT-ACME-NOVA-2026",
            record_type="contract_document",
            occurred_at=datetime(2026, 5, 20, 16),
            received_at=RECEIVED_AT,
            payload=contract_payload,
            normalized_payload={
                "contract_id": contract_payload["contract_id"],
                "approved_rule_ids": contract_payload["approved_rule_ids"],
                "effective_period": contract_payload["effective_period"],
            },
            payload_hash=_hash(contract_payload),
            match_status="context",
            matched_outcome_id=None,
            match_method="contract_id",
            match_confidence=Decimal("1.0000"),
            match_reason="Commercial context applies to the invoice rather than one outcome.",
        )
    )
    connector_counts["contract_documents"] += 1

    for record in records:
        claim = record.claim
        conversation = record.conversation
        is_secondary = claim.outcome_id in secondary_outcomes
        agent_version = (
            "refund-v2.3"
            if claim.intent == "refund"
            else "cancel-v3.1"
            if claim.intent == "cancel_subscription"
            else "support-v4.2"
        )
        vendor_claim_id = f"CLM-{_suffix(claim.outcome_id)}"
        claim_payload = {
            "vendor_claim_id": vendor_claim_id,
            "invoice_id": claim.invoice_id,
            "outcome_id": claim.outcome_id,
            "conversation_id": conversation.id,
            "customer_reference": claim.customer_id,
            "account_reference": claim.account_id,
            "claimed_outcome_type": claim.expected_action,
            "vendor_disposition": claim.vendor_claim,
            "claimed_completion_time": claim.closed_at.isoformat(),
            "billed_amount": f"{claim.billed_amount:.2f}",
            "currency": "USD",
            "agent_version": agent_version,
        }
        claim_raw_id = _raw_id("vendor_claim_manifest", vendor_claim_id)
        connector_counts["vendor_claim_manifest"] += 1
        sample_claim = _should_sample(claim.outcome_id, is_secondary)
        if sample_claim:
            raw_samples.append(
                RawRecord(
                    id=claim_raw_id,
                    connector_id="vendor_claim_manifest",
                    source_record_id=vendor_claim_id,
                    record_type="vendor_claim",
                    occurred_at=claim.closed_at,
                    received_at=RECEIVED_AT,
                    payload=claim_payload,
                    normalized_payload={
                        "outcome_id": claim.outcome_id,
                        "customer_id": claim.customer_id,
                        "intent": claim.intent,
                        "expected_action": claim.expected_action,
                        "billed_amount": f"{claim.billed_amount:.2f}",
                    },
                    payload_hash=_hash(claim_payload),
                    match_status="matched",
                    matched_outcome_id=claim.outcome_id,
                    match_method="vendor_outcome_id",
                    match_confidence=Decimal("1.0000"),
                    match_reason="The line-level manifest supplied a stable outcome identifier.",
                )
            )
        claims.append(
            NormalizedClaim(
                outcome_id=claim.outcome_id,
                invoice_id=claim.invoice_id,
                customer_id=claim.customer_id,
                intent=claim.intent,
                vendor_claim=claim.vendor_claim,
                closed_at=claim.closed_at,
                expected_action=claim.expected_action,
                account_id=claim.account_id,
                billed_amount=claim.billed_amount,
                vendor_claim_id=vendor_claim_id,
                external_conversation_id=conversation.id,
                agent_version=agent_version,
                raw_record_id=claim_raw_id if sample_claim else None,
            )
        )

        conversation_payload = {
            "ticket_id": conversation.id,
            "conversation_id": conversation.id,
            "outcome_id": claim.outcome_id,
            "customer_id": conversation.customer_id,
            "intent": conversation.intent,
            "status": "solved",
            "assignee_type": "ai_agent",
            "closed_at": conversation.closed_at.isoformat(),
        }
        conversation_raw_id = _raw_id("support_desk", conversation.id)
        connector_counts["support_desk"] += 1
        if sample_claim:
            raw_samples.append(
                RawRecord(
                    id=conversation_raw_id,
                    connector_id="support_desk",
                    source_record_id=conversation.id,
                    record_type="support_conversation",
                    occurred_at=conversation.closed_at,
                    received_at=RECEIVED_AT,
                    payload=conversation_payload,
                    normalized_payload={
                        "conversation_id": conversation.id,
                        "outcome_id": claim.outcome_id,
                        "customer_id": conversation.customer_id,
                        "intent": conversation.intent,
                    },
                    payload_hash=_hash(conversation_payload),
                    match_status="matched",
                    matched_outcome_id=claim.outcome_id,
                    match_method="conversation_outcome_id",
                    match_confidence=Decimal("1.0000"),
                    match_reason="The support conversation carried the stable outcome identifier.",
                )
            )
        conversations.append(
            NormalizedConversation(
                id=conversation.id,
                outcome_id=claim.outcome_id,
                customer_id=conversation.customer_id,
                intent=conversation.intent,
                closed_at=conversation.closed_at,
            )
        )

        identity_payload = {
            "customer_id": claim.customer_id,
            "conversation_id": conversation.id,
            "account_id": claim.account_id,
            "payment_customer_id": f"PAY-{claim.customer_id}",
        }
        connector_counts["identity_map"] += 1
        if sample_claim:
            raw_samples.append(
                RawRecord(
                    id=_raw_id("identity_map", f"IDENTITY-{_suffix(claim.outcome_id)}"),
                    connector_id="identity_map",
                    source_record_id=f"IDENTITY-{_suffix(claim.outcome_id)}",
                    record_type="identity_mapping",
                    occurred_at=None,
                    received_at=RECEIVED_AT,
                    payload=identity_payload,
                    normalized_payload=identity_payload,
                    payload_hash=_hash(identity_payload),
                    match_status="matched",
                    matched_outcome_id=claim.outcome_id,
                    match_method="customer_conversation_account_map",
                    match_confidence=Decimal("1.0000"),
                    match_reason="Customer master data links support and operational identifiers.",
                )
            )

        for event in record.events:
            connector_id = CONNECTOR_BY_SOURCE_SYSTEM[event.source_system]
            use_secondary = is_secondary and event.source_system not in {
                "nova_agent",
                "billing_export",
            }
            raw_payload: dict[str, Any] = {
                "event_id": event.source_record_id,
                "event_type": event.event_type,
                "occurred_at": event.timestamp.isoformat(),
                "customer_id": event.customer_id,
                "values": event.values,
            }
            external_keys = {
                "customer_id": claim.customer_id,
                "conversation_id": conversation.id,
                "account_id": claim.account_id,
            }
            if connector_id == "support_desk":
                raw_payload.update(
                    {
                        "ticket_id": conversation.id,
                        "conversation_id": conversation.id,
                        "intent": event.values.get("intent", claim.intent),
                        "assignee_type": (
                            "human" if event.event_type.startswith("human_") else "customer"
                        ),
                    }
                )
            elif connector_id == "payment_processor":
                raw_payload.update(
                    {
                        "transaction_id": event.source_record_id,
                        "account_id": event.values.get("account_id", claim.account_id),
                        "action": event.values.get("action", claim.expected_action),
                        "result": event.values.get("result", "unknown"),
                        "amount": "49.00" if claim.outcome_id == "OUT-004821" else "0.00",
                        "metadata": {"conversation_id": conversation.id},
                    }
                )
                external_keys["transaction_id"] = event.source_record_id
            elif connector_id == "product_operations":
                raw_payload.update(
                    {
                        "operation_id": event.source_record_id,
                        "account_id": event.values.get("account_id", claim.account_id),
                        "action": event.values.get("action", claim.expected_action),
                        "result": (
                            "succeeded"
                            if event.event_type == "downstream_succeeded"
                            else "mismatch"
                        ),
                        "observed_account_id": event.values.get("observed_account_id"),
                        "conversation_id": conversation.id,
                    }
                )
                external_keys["operation_id"] = event.source_record_id
            elif connector_id == "billing_ledger":
                raw_payload.update(
                    {
                        "ledger_record_id": event.source_record_id,
                        "normalized_intent": claim.intent,
                        "original_outcome_id": event.values.get("original_outcome_id"),
                    }
                )
            elif connector_id == "vendor_agent_log":
                raw_payload.update(
                    {
                        "account_reference": claim.account_id,
                        "action": claim.expected_action,
                        "agent_version": agent_version,
                    }
                )

            if not use_secondary:
                raw_payload["outcome_id"] = claim.outcome_id

            event_raw_id = _raw_id(connector_id, event.source_record_id)
            payload_hash = _hash(raw_payload)
            connector_counts[connector_id] += 1
            if use_secondary:
                match_method = "conversation_id + customer_account_map"
                confidence = Decimal("0.9700")
                match_reason = (
                    "The source omitted outcome_id; Evidue joined conversation_id through the "
                    "customer identity map and verified account and time-window consistency."
                )
                match_status = "secondary"
            else:
                match_method = "direct_outcome_id"
                confidence = Decimal("1.0000")
                match_reason = "The source record supplied the stable outcome identifier."
                match_status = "matched"

            sample_event = _should_sample(claim.outcome_id, use_secondary, event.event_type)
            if sample_event:
                raw_samples.append(
                    RawRecord(
                        id=event_raw_id,
                        connector_id=connector_id,
                        source_record_id=event.source_record_id,
                        record_type="operational_event",
                        occurred_at=event.timestamp,
                        received_at=RECEIVED_AT,
                        payload=raw_payload,
                        normalized_payload={
                            "event_id": event.id,
                            "source_system": event.source_system,
                            "event_type": event.event_type,
                            "timestamp": event.timestamp.isoformat(),
                            "customer_id": event.customer_id,
                            "outcome_id": claim.outcome_id,
                            "values": event.values,
                        },
                        payload_hash=payload_hash,
                        match_status=match_status,
                        matched_outcome_id=claim.outcome_id,
                        match_method=match_method,
                        match_confidence=confidence,
                        match_reason=match_reason,
                    )
                )
            events.append(
                NormalizedEvent(
                    id=event.id,
                    source_system=event.source_system,
                    source_record_id=event.source_record_id,
                    event_type=event.event_type,
                    timestamp=event.timestamp,
                    customer_id=event.customer_id,
                    outcome_id=claim.outcome_id,
                    values=event.values,
                    ingested_at=event.ingested_at,
                    connector_id=connector_id,
                    raw_record_id=event_raw_id if sample_event else None,
                    match_method=match_method,
                    match_confidence=confidence,
                    payload_hash=payload_hash,
                    schema_version=SCHEMA_VERSION,
                    source_locator=f"{connector_id}://{event.source_record_id}",
                    external_keys=external_keys,
                )
            )

    snapshots = tuple(
        ConnectorSnapshot(
            connector=connector,
            records_received=connector_counts[connector.id],
            records_normalized=connector_counts[connector.id],
            records_rejected=0,
        )
        for connector in CONNECTORS
    )
    secondary_matches = len(secondary_outcomes)
    stats = IngestionStats(
        claims_received=len(records),
        direct_matches=len(records) - secondary_matches,
        secondary_matches=secondary_matches,
        unresolved_matches=0,
        source_records_received=sum(connector_counts.values()),
        source_records_normalized=sum(connector_counts.values()),
        source_records_rejected=0,
    )
    return IngestionBundle(
        connectors=snapshots,
        raw_samples=tuple(raw_samples),
        claims=tuple(claims),
        conversations=tuple(conversations),
        events=tuple(events),
        stats=stats,
    )
