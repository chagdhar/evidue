import os
import threading
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from sqlalchemy import create_engine, delete, func, inspect, or_, select
from sqlalchemy.orm import joinedload, sessionmaker

from app.contracts.compiler import (
    DEFAULT_CONTRACT_PATH,
    compile_with_gemini,
    load_recorded_proposal,
    recorded_rule_program,
)
from app.domain.engine import evaluate, reconcile
from app.domain.models import ExecutableRule, OperationalEvent, OutcomeClaim, RuleProgram
from app.fixtures.demo import (
    INVOICE_ID,
    SCENARIOS,
    SCENARIOS_BY_ID,
    DemoScenario,
    scenario_fixture,
)
from app.ingestion.demo_pipeline import CONNECTORS, build_ingestion_bundle

from .models import (
    Base,
    ConnectorRow,
    ContractClauseRow,
    ContractRow,
    ContractRuleRow,
    ConversationRow,
    DemoStateRow,
    EvidenceMatchRow,
    EvidenceReferenceRow,
    IngestionBatchRow,
    InvoiceRow,
    OperationalEventRow,
    OutcomeClaimRow,
    OutcomeDeterminationRow,
    RawRecordRow,
    ReconciliationRow,
    RuleCompilationRow,
)

ROOT = Path(__file__).parents[3]
DB_PATH = Path(os.getenv("EVIDUE_DB_PATH", str(ROOT / "data" / "evidue.db")))
DB_PATH.parent.mkdir(parents=True, exist_ok=True)
engine = create_engine(f"sqlite:///{DB_PATH}", future=True)
SessionLocal = sessionmaker(engine, expire_on_commit=False)
DISCLOSURE = (
    "Operationally realistic data generated deterministically. "
    "No real customer or vendor data is shown."
)
_public_evidence_package_cache: dict[str, object] | None = None
_public_evidence_package_lock = threading.Lock()


def initialize() -> None:
    Base.metadata.create_all(engine)
    required_columns = {
        "outcome_claims": {"vendor_claim_id", "external_conversation_id", "agent_version"},
        "operational_events": {"connector_id", "match_method", "payload_hash"},
        "connectors": {"category", "records_received", "trust_boundary"},
        "raw_records": {"normalized_payload", "payload_hash", "schema_version"},
        "demo_state": {"scenario_id", "active_compilation_id"},
        "outcome_determinations": {"confirmed_disputed_amount"},
        "contract_rules": {"operation", "priority", "consequence", "compilation_id"},
    }
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    missing_table = (
        not {"connectors", "raw_records", "evidence_matches", "ingestion_batches"} <= tables
    )
    missing_column = any(
        table in tables
        and not columns <= {column["name"] for column in inspector.get_columns(table)}
        for table, columns in required_columns.items()
    )
    if missing_table or missing_column:
        Base.metadata.drop_all(engine)
        Base.metadata.create_all(engine)


def _money(value: Decimal) -> str:
    return f"{value:.2f}"


def _scenario_metadata(scenario: DemoScenario) -> dict[str, str]:
    return {
        "id": scenario.id,
        "name": scenario.name,
        "description": scenario.description,
        "demo_outcome_id": scenario.demo_outcome_id,
    }


def scenario_catalog() -> list[dict[str, str]]:
    return [_scenario_metadata(scenario) for scenario in SCENARIOS]


def _proposal_payload(result) -> list[dict[str, object]]:
    return [rule.model_dump(mode="json") for rule in result.proposal.rules]


def _seed_compilation(session, *, approved: bool = True) -> RuleCompilationRow:
    result = load_recorded_proposal(DEFAULT_CONTRACT_PATH.read_text())
    compilation = RuleCompilationRow(
        id="COMP-RECORDED-GEMINI-V1",
        contract_id=result.proposal.contract_id,
        source_document=result.proposal.source_document,
        source_hash=result.source_hash,
        prompt_hash=result.prompt_hash,
        provider=result.proposal.provider,
        model=result.proposal.model,
        compiler_version=result.proposal.compiler_version,
        status="approved" if approved else "pending_approval",
        version=1,
        live_model_call=result.live_model_call,
        created_at=datetime(2026, 7, 1, 8, 10),
        approved_at=datetime(2026, 7, 1, 8, 15) if approved else None,
        rules=_proposal_payload(result),
        raw_response={**result.raw_response, "source_text": DEFAULT_CONTRACT_PATH.read_text()},
    )
    session.add(compilation)
    for rule in result.proposal.rules:
        session.add(
            ContractRuleRow(
                id=rule.id,
                title=rule.title,
                description=rule.description,
                clause_text=rule.clause_text,
                operation=rule.operation,
                parameters=rule.parameters,
                evidence_required=list(rule.evidence_required),
                priority=rule.priority,
                consequence=rule.consequence,
                compilation_id=compilation.id,
                version=compilation.version,
            )
        )
    return compilation


def _active_rule_program(session) -> RuleProgram:
    state = session.get(DemoStateRow, 1)
    if not state or not state.active_compilation_id:
        raise LookupError("No approved rule compilation is active")
    compilation = session.get(RuleCompilationRow, state.active_compilation_id)
    if compilation is None or compilation.status != "approved":
        raise LookupError("The active contract rules are not approved")
    rules = tuple(
        ExecutableRule(
            id=row.id,
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
        for row in session.scalars(
            select(ContractRuleRow)
            .where(ContractRuleRow.compilation_id == compilation.id)
            .order_by(ContractRuleRow.priority)
        ).all()
    )
    return RuleProgram(
        compilation_id=compilation.id,
        version=compilation.version,
        source_hash=compilation.source_hash,
        rules=rules,
    )


def load_active_rule_program() -> RuleProgram:
    """Load the exact approved, persisted program used by reconciliation."""
    with SessionLocal() as session:
        return _active_rule_program(session)


def _compilation_view(row: RuleCompilationRow | None) -> dict[str, object]:
    if row is None:
        raise LookupError("No contract rule compilation exists")
    raw_response = row.raw_response or {}
    return {
        "id": row.id,
        "contract_id": row.contract_id,
        "source_document": row.source_document,
        "source_text": raw_response.get("source_text", DEFAULT_CONTRACT_PATH.read_text()),
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
        "fallback_reason": raw_response.get("fallback_reason"),
        "validation": {
            "schema_valid": True,
            "allowlisted_operations": True,
            "unique_rule_ids": True,
            "unique_priorities": True,
            "rule_count": len(row.rules),
        },
        "safety_boundary": (
            "The LLM proposes only schema-validated rules. Approval creates an immutable version; "
            "the deterministic interpreter alone evaluates invoice claims."
        ),
    }


def reset(scenario_id: str = "headline") -> dict[str, object]:
    global _public_evidence_package_cache
    _public_evidence_package_cache = None
    records = scenario_fixture(scenario_id)
    scenario = SCENARIOS_BY_ID[scenario_id]
    ingestion = build_ingestion_bundle(records, scenario_id)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with SessionLocal.begin() as session:
        for snapshot in ingestion.connectors:
            connector = snapshot.connector
            session.add(
                ConnectorRow(
                    id=connector.id,
                    name=connector.name,
                    category=connector.category,
                    owner=connector.owner,
                    authority=connector.authority,
                    collection_method=connector.collection_method,
                    production_method=connector.production_method,
                    source_format=connector.source_format,
                    schedule=connector.schedule,
                    status="fixture_loaded",
                    description=connector.description,
                    fields=list(connector.fields),
                    records_received=snapshot.records_received,
                    records_normalized=snapshot.records_normalized,
                    records_rejected=snapshot.records_rejected,
                    last_synced_at=datetime(2026, 7, 1, 8),
                    trust_boundary=connector.trust_boundary,
                )
            )
        for raw in ingestion.raw_samples:
            session.add(
                RawRecordRow(
                    id=raw.id,
                    connector_id=raw.connector_id,
                    source_record_id=raw.source_record_id,
                    record_type=raw.record_type,
                    occurred_at=raw.occurred_at,
                    received_at=raw.received_at,
                    payload=raw.payload,
                    normalized_payload=raw.normalized_payload,
                    payload_hash=raw.payload_hash,
                    schema_version=raw.schema_version,
                    sampled=True,
                )
            )
            session.add(
                EvidenceMatchRow(
                    raw_record_id=raw.id,
                    outcome_id=raw.matched_outcome_id,
                    status=raw.match_status,
                    match_method=raw.match_method,
                    confidence=raw.match_confidence,
                    reason=raw.match_reason,
                    matched_at=datetime(2026, 7, 1, 8, 5),
                )
            )
        session.add(
            IngestionBatchRow(
                id=f"INGEST-2026-06-{scenario.id.upper().replace('_', '-')}",
                scenario_id=scenario.id,
                started_at=datetime(2026, 7, 1, 8),
                completed_at=datetime(2026, 7, 1, 8, 7),
                claims_received=ingestion.stats.claims_received,
                direct_matches=ingestion.stats.direct_matches,
                secondary_matches=ingestion.stats.secondary_matches,
                unresolved_matches=ingestion.stats.unresolved_matches,
                source_records_received=ingestion.stats.source_records_received,
                source_records_normalized=ingestion.stats.source_records_normalized,
                source_records_rejected=ingestion.stats.source_records_rejected,
                contract_rules_approved=7,
            )
        )
        contract = ContractRow(
            id="CONTRACT-ACME-NOVA-2026",
            customer="Acme Commerce",
            vendor="Nova Support AI",
            period_start=datetime(2026, 6, 1),
            period_end=datetime(2026, 7, 1),
            price_per_outcome=Decimal("1.50"),
        )
        session.add(contract)
        compilation = _seed_compilation(session, approved=True)
        session.flush()
        for rule in session.scalars(
            select(ContractRuleRow).where(ContractRuleRow.compilation_id == compilation.id)
        ).all():
            session.add(
                ContractClauseRow(
                    id=f"CLAUSE-{rule.id}",
                    contract_id=contract.id,
                    rule_id=rule.id,
                    text=rule.clause_text,
                )
            )
        session.add(
            InvoiceRow(
                id=INVOICE_ID,
                contract_id=contract.id,
                billing_period_start=contract.period_start,
                billing_period_end=contract.period_end,
                submitted_at=datetime(2026, 7, 1, 9),
            )
        )
        session.add_all(
            [
                OutcomeClaimRow(
                    outcome_id=claim.outcome_id,
                    vendor_claim_id=claim.vendor_claim_id,
                    external_conversation_id=claim.external_conversation_id,
                    agent_version=claim.agent_version,
                    raw_record_id=claim.raw_record_id,
                    invoice_id=claim.invoice_id,
                    customer_id=claim.customer_id,
                    intent=claim.intent,
                    vendor_claim=claim.vendor_claim,
                    closed_at=claim.closed_at,
                    expected_action=claim.expected_action,
                    account_id=claim.account_id,
                    billed_amount=claim.billed_amount,
                )
                for claim in ingestion.claims
            ]
        )
        session.add_all(
            [
                ConversationRow(
                    id=conversation.id,
                    outcome_id=conversation.outcome_id,
                    customer_id=conversation.customer_id,
                    intent=conversation.intent,
                    closed_at=conversation.closed_at,
                )
                for conversation in ingestion.conversations
            ]
        )
        session.add_all(
            [
                OperationalEventRow(
                    id=event.id,
                    source_system=event.source_system,
                    source_record_id=event.source_record_id,
                    event_type=event.event_type,
                    timestamp=event.timestamp,
                    customer_id=event.customer_id,
                    outcome_id=event.outcome_id,
                    values=event.values,
                    ingested_at=event.ingested_at,
                    connector_id=event.connector_id,
                    raw_record_id=event.raw_record_id,
                    match_method=event.match_method,
                    match_confidence=event.match_confidence,
                    payload_hash=event.payload_hash,
                    schema_version=event.schema_version,
                    source_locator=event.source_locator,
                    external_keys=event.external_keys,
                )
                for event in ingestion.events
            ]
        )
        session.add(
            DemoStateRow(
                id=1,
                seeded=True,
                reconciled=False,
                scenario_id=scenario.id,
                active_compilation_id=compilation.id,
            )
        )
    return demo_status()


def demo_status() -> dict[str, object]:
    initialize()
    with SessionLocal() as session:
        state = session.get(DemoStateRow, 1)
        claim_count = session.scalar(select(func.count()).select_from(OutcomeClaimRow)) or 0
    scenario = SCENARIOS_BY_ID.get(state.scenario_id if state else "headline")
    if scenario is None:
        scenario = SCENARIOS_BY_ID["headline"]
    return {
        "seeded": bool(state and state.seeded),
        "reconciled": bool(state and state.reconciled),
        "claimed_outcomes": claim_count,
        "billing_period": "2026-06-01 through 2026-06-30",
        "scenario_id": scenario.id,
        "scenario_name": scenario.name,
        "scenario_description": scenario.description,
        "demo_outcome_id": scenario.demo_outcome_id,
    }


def prepare_public_demo() -> None:
    """Leave the shared public workspace on the immutable headline result."""
    state = demo_status()
    if not state["seeded"] or state["scenario_id"] != "headline":
        reset("headline")
    with SessionLocal() as session:
        demo_state = session.get(DemoStateRow, 1)
        compilation = (
            session.get(RuleCompilationRow, demo_state.active_compilation_id)
            if demo_state and demo_state.active_compilation_id
            else None
        )
        valid_program = bool(
            compilation
            and compilation.id == "COMP-RECORDED-GEMINI-V1"
            and compilation.status == "approved"
        )
    if not valid_program:
        reset("headline")
    if not demo_status()["reconciled"]:
        run_reconciliation()


def _source_summary(session, connector: ConnectorRow) -> dict[str, object]:
    match_counts = dict(
        session.execute(
            select(EvidenceMatchRow.status, func.count())
            .join(RawRecordRow, RawRecordRow.id == EvidenceMatchRow.raw_record_id)
            .where(RawRecordRow.connector_id == connector.id)
            .group_by(EvidenceMatchRow.status)
        ).all()
    )
    return {
        "id": connector.id,
        "name": connector.name,
        "category": connector.category,
        "owner": connector.owner,
        "authority": connector.authority,
        "collection_method": connector.collection_method,
        "production_method": connector.production_method,
        "source_format": connector.source_format,
        "schedule": connector.schedule,
        "status": connector.status,
        "description": connector.description,
        "fields": connector.fields,
        "raw_records": connector.records_received,
        "normalized_records": connector.records_normalized,
        "rejected_records": connector.records_rejected,
        "matched_records": connector.records_normalized - connector.records_rejected,
        "secondary_matches": int(match_counts.get("secondary", 0)),
        "review_records": connector.records_rejected
        + int(match_counts.get("review", 0) + match_counts.get("unmatched", 0)),
        "last_synced_at": connector.last_synced_at.isoformat(),
        "trust_boundary": connector.trust_boundary,
    }


def data_readiness() -> dict[str, object]:
    with SessionLocal() as session:
        connector_rows = {
            connector.id: connector for connector in session.scalars(select(ConnectorRow)).all()
        }
        sources = [
            _source_summary(session, connector_rows[spec.id])
            for spec in CONNECTORS
            if spec.id in connector_rows
        ]
        batch = session.scalar(
            select(IngestionBatchRow).order_by(IngestionBatchRow.completed_at.desc())
        )
        normalized_events = (
            session.scalar(select(func.count()).select_from(OperationalEventRow)) or 0
        )
        sampled_records = session.scalar(select(func.count()).select_from(RawRecordRow)) or 0
    if batch is None:
        raise LookupError("Ingestion batch is not available")
    covered = batch.direct_matches + batch.secondary_matches
    coverage_percent = (
        round((covered / batch.claims_received * 100), 2) if batch.claims_received else 0.0
    )
    return {
        "status": "ready" if batch.unresolved_matches == 0 else "review_required",
        "synthetic_disclosure": DISCLOSURE,
        "collection_note": (
            "The demo begins with source-shaped vendor, support, payment, product, billing, "
            "identity, and contract records. Evidue preserves provenance, normalizes the fields, "
            "matches evidence to claims, and only then runs contract rules. Production uses the "
            "same stages through read-only APIs, warehouse views, SFTP, object storage, and uploads."
        ),
        "totals": {
            "claimed_outcomes": batch.claims_received,
            "raw_records": batch.source_records_received,
            "sampled_raw_records": int(sampled_records),
            "normalized_events": int(normalized_events),
            "direct_matches": batch.direct_matches,
            "secondary_matches": batch.secondary_matches,
            "review_records": batch.unresolved_matches,
            "claim_coverage_percent": coverage_percent,
            "contract_rules_approved": batch.contract_rules_approved,
        },
        "sources": sources,
        "pipeline": [
            {
                "id": "collect",
                "label": "Collect",
                "description": "Receive the vendor claim manifest, customer records, identity mappings, and contract documents through read-only channels.",
            },
            {
                "id": "raw",
                "label": "Preserve raw",
                "description": "Retain source record IDs, receipt times, schema versions, content hashes, and representative payloads.",
            },
            {
                "id": "normalize",
                "label": "Normalize",
                "description": "Map source-specific fields into claims, conversations, operational events, and approved rules.",
            },
            {
                "id": "match",
                "label": "Match",
                "description": "Join records using stable outcome IDs or verified secondary keys such as conversation, account, and transaction IDs.",
            },
            {
                "id": "evaluate",
                "label": "Evaluate",
                "description": "Apply deterministic contract rules only after evidence attribution is complete.",
            },
        ],
        "onboarding": [
            {
                "phase": "1",
                "label": "Start with exports",
                "description": "CSV, JSONL, contract documents, and secure object-storage drops prove value without a long integration project.",
            },
            {
                "phase": "2",
                "label": "Connect read-only systems",
                "description": "Support, payment, warehouse, SFTP, and vendor APIs replace manual exports while keeping the same normalized model.",
            },
            {
                "phase": "3",
                "label": "Incremental sync",
                "description": "Webhooks, scheduled polling, or change-data capture keep evidence current before each invoice cycle.",
            },
        ],
    }


def source_samples(
    source_id: str,
    limit: int = 5,
    outcome_id: str | None = None,
) -> dict[str, object]:
    with SessionLocal() as session:
        connector = session.get(ConnectorRow, source_id)
        if connector is None:
            raise LookupError("Data source not found")
        statement = (
            select(RawRecordRow, EvidenceMatchRow)
            .outerjoin(EvidenceMatchRow, EvidenceMatchRow.raw_record_id == RawRecordRow.id)
            .where(RawRecordRow.connector_id == source_id)
        )
        if outcome_id:
            statement = statement.where(EvidenceMatchRow.outcome_id == outcome_id)
        statement = statement.order_by(
            RawRecordRow.occurred_at.is_(None), RawRecordRow.occurred_at, RawRecordRow.id
        ).limit(limit)
        rows = session.execute(statement).all()
        source = _source_summary(session, connector)
    return {
        "source": source,
        "records": [
            {
                "id": raw.id,
                "connector_id": raw.connector_id,
                "source_record_id": raw.source_record_id,
                "record_type": raw.record_type,
                "occurred_at": raw.occurred_at.isoformat() if raw.occurred_at else None,
                "received_at": raw.received_at.isoformat(),
                "payload": raw.payload,
                "normalized_payload": raw.normalized_payload,
                "payload_hash": f"sha256:{raw.payload_hash}",
                "schema_version": raw.schema_version,
                "matched_outcome_id": match.outcome_id if match else None,
                "match_status": match.status if match else None,
                "match_method": match.match_method if match else None,
                "match_confidence": f"{match.confidence:.4f}" if match else None,
                "match_reason": match.reason if match else None,
            }
            for raw, match in rows
        ],
        "sample_note": (
            "The demo stores representative raw payloads for inspection and exact aggregate counts "
            "for the full batch. Production retains every permitted raw record according to the "
            "customer's retention policy."
        ),
    }


def _domain_claim(row: OutcomeClaimRow) -> OutcomeClaim:
    return OutcomeClaim(
        row.outcome_id,
        row.invoice_id,
        row.customer_id,
        row.intent,
        row.vendor_claim,
        row.closed_at,
        row.expected_action,
        row.account_id,
        row.billed_amount,
    )


def _domain_event(row: OperationalEventRow) -> OperationalEvent:
    return OperationalEvent(
        row.id,
        row.source_system,
        row.source_record_id,
        row.event_type,
        row.timestamp,
        row.customer_id,
        row.outcome_id,
        row.values,
        row.ingested_at,
    )


def run_reconciliation() -> dict[str, object]:
    global _public_evidence_package_cache
    _public_evidence_package_cache = None
    if not demo_status()["seeded"]:
        reset()
    with SessionLocal.begin() as session:
        session.execute(delete(EvidenceReferenceRow))
        session.execute(delete(OutcomeDeterminationRow))
        session.execute(delete(ReconciliationRow))
        state = session.get(DemoStateRow, 1)
        scenario_id = state.scenario_id if state else "headline"
        reconciliation_id = (
            "REC-2026-06-001"
            if scenario_id == "headline"
            else f"REC-2026-06-{scenario_id.upper().replace('_', '-')}"
        )
        program = _active_rule_program(session)
        reconciliation = ReconciliationRow(
            id=reconciliation_id,
            invoice_id=INVOICE_ID,
            evaluated_at=datetime(2026, 7, 1, 12),
            engine_version=program.engine_version,
        )
        session.add(reconciliation)
        claims = session.scalars(select(OutcomeClaimRow).order_by(OutcomeClaimRow.outcome_id)).all()
        event_rows = session.scalars(
            select(OperationalEventRow).order_by(
                OperationalEventRow.outcome_id, OperationalEventRow.timestamp
            )
        ).all()
        by_outcome: dict[str, list[OperationalEventRow]] = {}
        for event in event_rows:
            if event.outcome_id:
                by_outcome.setdefault(event.outcome_id, []).append(event)
        domain_inputs = [
            (
                _domain_claim(claim_row),
                [_domain_event(event) for event in by_outcome.get(claim_row.outcome_id, [])],
            )
            for claim_row in claims
        ]
        results = reconcile(domain_inputs, program=program)
        for claim_row, result in zip(claims, results, strict=True):
            determination = OutcomeDeterminationRow(
                reconciliation_id=reconciliation.id,
                outcome_id=claim_row.outcome_id,
                rule_id=result.rule_id,
                status=result.status,
                reason=result.reason,
                billed_amount=result.claim.billed_amount,
                confirmed_payable_amount=result.confirmed_payable_amount,
                confirmed_disputed_amount=result.confirmed_disputed_amount,
                needs_review_amount=result.needs_review_amount,
                duplicate_winner_outcome_id=(
                    result.duplicate_decision.winner_outcome_id
                    if result.duplicate_decision
                    else None
                ),
                evaluated_at=result.evaluated_at,
                engine_version=result.engine_version,
            )
            session.add(determination)
            session.flush()
            session.add_all(
                [
                    EvidenceReferenceRow(
                        determination_id=determination.id,
                        event_id=reference.event_id,
                        purpose=reference.purpose,
                    )
                    for reference in result.evidence
                ]
            )
        if state:
            state.reconciled = True
    return summary()


def validate_recorded_proposal() -> dict[str, object]:
    """Validate only the immutable bundled proposal; this never writes or calls a model."""
    result = load_recorded_proposal(DEFAULT_CONTRACT_PATH.read_text())
    program = recorded_rule_program()
    return {
        "valid": True,
        "contract_id": result.proposal.contract_id,
        "source_hash": result.source_hash,
        "prompt_hash": result.prompt_hash,
        "rule_count": len(program.rules),
        "rule_ids": [rule.id for rule in program.rules],
        "compiler_version": result.proposal.compiler_version,
        "live_model_call": False,
    }


def public_outcome_evaluation(outcome_id: str) -> dict[str, object]:
    """Rerun the approved program in memory for a supported demo outcome."""
    if outcome_id != "OUT-004821":
        raise LookupError("Only OUT-004821 is available for public deterministic evaluation")
    with SessionLocal() as session:
        claim = session.get(OutcomeClaimRow, outcome_id)
        if claim is None:
            raise LookupError("Outcome not found")
        events = session.scalars(
            select(OperationalEventRow)
            .where(OperationalEventRow.outcome_id == outcome_id)
            .order_by(OperationalEventRow.timestamp, OperationalEventRow.id)
        ).all()
        program = _active_rule_program(session)
    determination = evaluate(
        _domain_claim(claim),
        [_domain_event(event) for event in events],
        program=program,
    )
    return {
        "outcome_id": outcome_id,
        "status": determination.status,
        "rule_id": determination.rule_id,
        "reason": determination.reason,
        "confirmed_payable_amount": _money(determination.confirmed_payable_amount),
        "confirmed_disputed_amount": _money(determination.confirmed_disputed_amount),
        "needs_review_amount": _money(determination.needs_review_amount),
        "evidence_ids": [reference.event_id for reference in determination.evidence],
        "engine_version": determination.engine_version,
        "compilation_id": program.compilation_id,
        "program_version": program.version,
        "source_hash": program.source_hash,
        "canonical": outcome_detail(outcome_id),
    }


def public_reconciliation_sample(limit: int = 100) -> dict[str, object]:
    """Evaluate a stable subset against the approved program without persisting anything."""
    with SessionLocal() as session:
        program = _active_rule_program(session)
        determinations = session.execute(
            select(OutcomeClaimRow, OutcomeDeterminationRow)
            .join(
                OutcomeDeterminationRow,
                OutcomeDeterminationRow.outcome_id == OutcomeClaimRow.outcome_id,
            )
            .order_by(OutcomeClaimRow.outcome_id)
        ).all()
        payable = [
            claim for claim, determination in determinations if determination.status == "payable"
        ][:83]
        disputed_by_rule = {}
        for rule_id, count in (("R1", 7), ("R2", 4), ("R3", 3), ("R4", 2), ("R5", 1)):
            matching_claims = [
                claim for claim, determination in determinations if determination.rule_id == rule_id
            ]
            if rule_id == "R3":
                featured_claim = next(
                    claim for claim in matching_claims if claim.outcome_id == "OUT-004821"
                )
                matching_claims = [featured_claim] + [
                    claim
                    for claim in matching_claims
                    if claim.outcome_id != featured_claim.outcome_id
                ]
            disputed_by_rule[rule_id] = matching_claims[:count]
        claims = payable + [claim for rows in disputed_by_rule.values() for claim in rows]
        outcome_ids = [claim.outcome_id for claim in claims]
        event_rows = session.scalars(
            select(OperationalEventRow)
            .where(OperationalEventRow.outcome_id.in_(outcome_ids))
            .order_by(OperationalEventRow.outcome_id, OperationalEventRow.timestamp)
        ).all()
    by_outcome: dict[str, list[OperationalEventRow]] = {}
    for event in event_rows:
        if event.outcome_id:
            by_outcome.setdefault(event.outcome_id, []).append(event)
    results = reconcile(
        [
            (
                _domain_claim(row),
                [_domain_event(event) for event in by_outcome.get(row.outcome_id, [])],
            )
            for row in claims
        ],
        program=program,
    )
    disputed = [result for result in results if result.status == "disputed"]
    return {
        "sample_size": len(results),
        "payable_outcomes": sum(result.status == "payable" for result in results),
        "disputed_outcomes": len(disputed),
        "needs_review_outcomes": sum(result.status == "needs_review" for result in results),
        "submitted_amount": _money(
            sum((result.claim.billed_amount for result in results), Decimal())
        ),
        "confirmed_payable_amount": _money(
            sum((result.confirmed_payable_amount for result in results), Decimal())
        ),
        "recommended_deduction": _money(
            sum((result.confirmed_disputed_amount for result in results), Decimal())
        ),
        "representative_findings": [
            {
                "rule_id": rule_id,
                "outcome_id": next(
                    result.claim.outcome_id for result in disputed if result.rule_id == rule_id
                ),
            }
            for rule_id in ("R1", "R2", "R3", "R4", "R5")
        ],
        "sampling_method": "Deterministic stratified sample: 83 payable; 7 R1, 4 R2, 3 R3, 2 R4, and 1 R5 disputes.",
        "compilation_id": program.compilation_id,
        "program_version": program.version,
        "source_hash": program.source_hash,
        "engine_version": program.engine_version,
    }


def summary() -> dict[str, object]:
    with SessionLocal() as session:
        rows = session.execute(
            select(
                OutcomeDeterminationRow.status,
                OutcomeDeterminationRow.rule_id,
                OutcomeDeterminationRow.billed_amount,
                OutcomeDeterminationRow.confirmed_payable_amount,
                OutcomeDeterminationRow.confirmed_disputed_amount,
                OutcomeDeterminationRow.needs_review_amount,
            )
        ).all()
        reconciliation = session.scalar(
            select(ReconciliationRow).order_by(ReconciliationRow.evaluated_at.desc())
        )
        price = session.scalar(select(ContractRow.price_per_outcome)) or Decimal()
        state = session.get(DemoStateRow, 1)
    scenario = SCENARIOS_BY_ID.get(state.scenario_id if state else "headline")
    if scenario is None:
        scenario = SCENARIOS_BY_ID["headline"]
    billed = sum((row.billed_amount for row in rows), Decimal())
    payable = sum((row.confirmed_payable_amount for row in rows), Decimal())
    disputed = sum((row.confirmed_disputed_amount for row in rows), Decimal())
    review = sum((row.needs_review_amount for row in rows), Decimal())
    categories: dict[str, dict[str, object]] = {}
    labels = {
        "R1": "Same-intent recontacts",
        "R2": "Human completions or corrections",
        "R3": "Failed downstream actions",
        "R4": "Duplicate charges",
        "R5": "Account or action mismatches",
    }
    for row in rows:
        if row.status == "disputed" and row.rule_id:
            category = categories.setdefault(
                row.rule_id,
                {
                    "label": labels.get(row.rule_id, row.rule_id),
                    "count": 0,
                    "amount_decimal": Decimal(),
                },
            )
            category["count"] = int(category["count"]) + 1
            category["amount_decimal"] = (
                Decimal(str(category["amount_decimal"])) + row.confirmed_disputed_amount
            )
    for category in categories.values():
        category["amount"] = _money(Decimal(str(category.pop("amount_decimal"))))
    return {
        "reconciliation_id": reconciliation.id if reconciliation else "",
        "status": "completed" if rows else "not_run",
        "scenario_id": scenario.id,
        "scenario_name": scenario.name,
        "claimed_outcomes": len(rows),
        "payable_outcomes": sum(row.status == "payable" for row in rows),
        "disputed_outcomes": sum(row.status == "disputed" for row in rows),
        "needs_review_outcomes": sum(row.status == "needs_review" for row in rows),
        "submitted_amount": _money(billed),
        "confirmed_payable_amount": _money(payable),
        "recommended_deduction": _money(disputed),
        "needs_review_amount": _money(review),
        "price_per_outcome": _money(price),
        "categories": categories,
        "synthetic_disclosure": DISCLOSURE,
    }


def list_compilations() -> list[dict[str, object]]:
    with SessionLocal() as session:
        rows = session.scalars(
            select(RuleCompilationRow).order_by(RuleCompilationRow.version.desc())
        ).all()
        return [_compilation_view(row) for row in rows]


def contract() -> dict[str, object]:
    with SessionLocal() as session:
        row = session.scalar(
            select(ContractRow).options(
                joinedload(ContractRow.clauses).joinedload(ContractClauseRow.rule)
            )
        )
        if row is None:
            raise LookupError("Demo contract is not seeded")
        state = session.get(DemoStateRow, 1)
        if state is None or not state.active_compilation_id:
            raise LookupError("No approved contract rule program is active")
        active = session.get(RuleCompilationRow, state.active_compilation_id)
        latest = session.scalar(
            select(RuleCompilationRow).order_by(RuleCompilationRow.version.desc())
        )
        active_view = _compilation_view(active)
        latest_view = _compilation_view(latest)
        return {
            "id": row.id,
            "customer": row.customer,
            "vendor": row.vendor,
            "period_start": row.period_start.isoformat(),
            "period_end": row.period_end.isoformat(),
            "price_per_outcome": _money(row.price_per_outcome),
            "clauses": [
                {
                    "id": clause.id,
                    "text": clause.text,
                    "rule": {
                        "id": clause.rule.id,
                        "title": clause.rule.title,
                        "description": clause.rule.description,
                        "parameters": {
                            **clause.rule.parameters,
                            **(
                                {"applies_after": ",".join(clause.rule.parameters["applies_after"])}
                                if isinstance(clause.rule.parameters.get("applies_after"), list)
                                else {}
                            ),
                        },
                        "evidence_required": clause.rule.evidence_required,
                        "consequence": clause.rule.consequence,
                        "operation": clause.rule.operation,
                        "priority": clause.rule.priority,
                        "compilation_id": clause.rule.compilation_id,
                    },
                }
                for clause in sorted(row.clauses, key=lambda item: item.rule.priority)
            ],
            "compilation": active_view,
            "latest_compilation": latest_view,
            "contract_text": active_view["source_text"],
            "demo_contract_text": DEFAULT_CONTRACT_PATH.read_text(),
            "live_compilation_available": bool(os.getenv("GEMINI_API_KEY")),
            "evidence_sources": [
                "Nova Support AI agent log",
                "Acme support desk",
                "Payment processor",
                "Billing export",
                "Product account system",
            ],
        }


def compile_contract_rules(
    mode: str = "auto",
    *,
    contract_text: str | None = None,
    source_document: str | None = None,
) -> dict[str, object]:
    default_text = DEFAULT_CONTRACT_PATH.read_text()
    selected_text = contract_text if contract_text is not None else default_text
    selected_document = (source_document or "Acme-Nova-Outcome-Pricing-Order-Form.pdf").strip()
    if len(selected_text.strip()) < 50:
        raise ValueError("Contract text must contain at least 50 characters")
    if len(selected_document) < 3:
        raise ValueError("Source document must contain at least 3 characters")
    custom_source = selected_text.strip() != default_text.strip()
    use_live = mode == "live" or (mode == "auto" and bool(os.getenv("GEMINI_API_KEY")))
    if mode == "recorded" and custom_source:
        raise ValueError(
            "The recorded Gemini proposal is tied to the bundled demo contract. "
            "Restore the demo contract or configure GEMINI_API_KEY for custom text."
        )
    if mode == "auto" and custom_source and not os.getenv("GEMINI_API_KEY"):
        raise ValueError(
            "Custom contract text requires a live Gemini compilation. Configure GEMINI_API_KEY, "
            "or replay the recorded proposal using the bundled demo contract."
        )
    fallback_reason = None
    if use_live:
        try:
            result = compile_with_gemini(
                selected_text,
                "CONTRACT-ACME-NOVA-2026",
                selected_document,
            )
        except (RuntimeError, ValueError) as exc:
            if mode == "live" or custom_source:
                raise
            fallback_reason = (
                f"Live Gemini compilation failed; loaded the validated recorded proposal: {exc}"
            )
            result = load_recorded_proposal(selected_text)
    else:
        result = load_recorded_proposal(selected_text)
    with SessionLocal.begin() as session:
        latest_version = session.scalar(select(func.max(RuleCompilationRow.version))) or 0
        session.execute(
            RuleCompilationRow.__table__.update()
            .where(RuleCompilationRow.status == "pending_approval")
            .values(status="superseded")
        )
        compilation_id = f"COMP-{datetime.now(UTC).strftime('%Y%m%d%H%M%S%f')}"
        row = RuleCompilationRow(
            id=compilation_id,
            contract_id=result.proposal.contract_id,
            source_document=selected_document,
            source_hash=result.source_hash,
            prompt_hash=result.prompt_hash,
            provider=result.proposal.provider,
            model=result.proposal.model,
            compiler_version=result.proposal.compiler_version,
            status="pending_approval",
            version=int(latest_version) + 1,
            live_model_call=result.live_model_call,
            created_at=datetime.now(UTC),
            approved_at=None,
            rules=_proposal_payload(result),
            raw_response={
                **result.raw_response,
                "source_text": selected_text,
                **({"fallback_reason": fallback_reason} if fallback_reason else {}),
            },
        )
        session.add(row)
    return _compilation_view(row)


def approve_compilation(compilation_id: str) -> dict[str, object]:
    with SessionLocal.begin() as session:
        row = session.get(RuleCompilationRow, compilation_id)
        if row is None:
            raise LookupError("Compilation not found")
        if row.status == "superseded":
            raise ValueError(
                f"Version {row.version} is superseded. Review and approve the latest proposal instead."
            )
        if row.status != "pending_approval":
            raise ValueError("Only a pending compilation can be approved")
        latest_pending = session.scalar(
            select(RuleCompilationRow)
            .where(RuleCompilationRow.status == "pending_approval")
            .order_by(RuleCompilationRow.version.desc())
        )
        if latest_pending and latest_pending.id != row.id:
            raise ValueError(
                f"Version {row.version} is stale. Review the latest proposal, version {latest_pending.version}."
            )
        # An approved program invalidates prior determinations. The interpreter will
        # recompute them from the newly approved immutable rule program.
        session.execute(delete(EvidenceReferenceRow))
        session.execute(delete(OutcomeDeterminationRow))
        session.execute(delete(ReconciliationRow))
        session.execute(delete(ContractClauseRow))
        session.execute(delete(ContractRuleRow))
        for payload in sorted(row.rules, key=lambda item: item["priority"]):
            rule = ExecutableRule(
                id=payload["id"],
                title=payload["title"],
                description=payload["description"],
                clause_text=payload["clause_text"],
                operation=payload["operation"],
                parameters=payload["parameters"],
                evidence_required=tuple(payload["evidence_required"]),
                priority=payload["priority"],
                consequence=payload["consequence"],
                compilation_id=row.id,
            )
            session.add(
                ContractRuleRow(
                    id=rule.id,
                    title=rule.title,
                    description=rule.description,
                    clause_text=rule.clause_text,
                    operation=rule.operation,
                    parameters=rule.parameters,
                    evidence_required=list(rule.evidence_required),
                    priority=rule.priority,
                    consequence=rule.consequence,
                    compilation_id=row.id,
                    version=row.version,
                )
            )
            session.add(
                ContractClauseRow(
                    id=f"CLAUSE-{rule.id}",
                    contract_id=row.contract_id,
                    rule_id=rule.id,
                    text=rule.clause_text,
                )
            )
        row.status = "approved"
        row.approved_at = datetime.now(UTC)
        session.execute(
            RuleCompilationRow.__table__.update()
            .where(
                RuleCompilationRow.status.in_(["pending_approval", "approved"]),
                RuleCompilationRow.id != row.id,
            )
            .values(status="superseded")
        )
        state = session.get(DemoStateRow, 1)
        if state:
            state.active_compilation_id = row.id
            state.reconciled = False
    return _compilation_view(row)


def invoice() -> dict[str, object]:
    with SessionLocal() as session:
        row = session.get(InvoiceRow, INVOICE_ID)
        count = session.scalar(select(func.count()).select_from(OutcomeClaimRow)) or 0
        amount = session.scalar(select(func.sum(OutcomeClaimRow.billed_amount))) or Decimal()
    if row is None:
        raise LookupError("Demo invoice is not seeded")
    return {
        "invoice_id": row.id,
        "contract_id": row.contract_id,
        "billing_period_start": row.billing_period_start.isoformat(),
        "billing_period_end": row.billing_period_end.isoformat(),
        "submitted_at": row.submitted_at.isoformat(),
        "claimed_outcomes": count,
        "submitted_amount": _money(amount),
        "status": "submitted",
    }


def list_outcomes(
    offset: int,
    limit: int,
    status: str | None = None,
    reason: str | None = None,
    outcome_id: str | None = None,
    customer_id: str | None = None,
    intent: str | None = None,
    search: str | None = None,
) -> tuple[int, list[dict[str, object]]]:
    statement = select(OutcomeDeterminationRow, OutcomeClaimRow).join(
        OutcomeClaimRow, OutcomeClaimRow.outcome_id == OutcomeDeterminationRow.outcome_id
    )
    if status:
        statement = statement.where(OutcomeDeterminationRow.status == status)
    if reason:
        statement = statement.where(OutcomeDeterminationRow.rule_id == reason)
    if outcome_id:
        statement = statement.where(OutcomeClaimRow.outcome_id.contains(outcome_id))
    if customer_id:
        statement = statement.where(OutcomeClaimRow.customer_id.contains(customer_id))
    if intent:
        statement = statement.where(OutcomeClaimRow.intent == intent)
    if search:
        pattern = f"%{search}%"
        statement = statement.where(
            or_(
                OutcomeClaimRow.outcome_id.like(pattern),
                OutcomeClaimRow.customer_id.like(pattern),
                OutcomeClaimRow.intent.like(pattern),
            )
        )
    count_statement = select(func.count()).select_from(statement.subquery())
    statement = statement.order_by(OutcomeClaimRow.outcome_id).offset(offset).limit(limit)
    with SessionLocal() as session:
        total = session.scalar(count_statement) or 0
        rows = session.execute(statement).all()
    return total, [_outcome_view(determination, claim) for determination, claim in rows]


def _outcome_view(
    determination: OutcomeDeterminationRow, claim: OutcomeClaimRow
) -> dict[str, object]:
    return {
        "outcome_id": claim.outcome_id,
        "customer_id": claim.customer_id,
        "intent": claim.intent,
        "vendor_claim": claim.vendor_claim,
        "status": determination.status,
        "reason": determination.reason,
        "rule_id": determination.rule_id,
        "billed_amount": _money(determination.billed_amount),
        "confirmed_payable_amount": _money(determination.confirmed_payable_amount),
        "confirmed_disputed_amount": _money(determination.confirmed_disputed_amount),
        "needs_review_amount": _money(determination.needs_review_amount),
        "closed_at": claim.closed_at.isoformat(),
    }


def outcome_detail(outcome_id: str) -> dict[str, object] | None:
    with SessionLocal() as session:
        row = session.execute(
            select(OutcomeDeterminationRow, OutcomeClaimRow, ConversationRow)
            .join(OutcomeClaimRow, OutcomeClaimRow.outcome_id == OutcomeDeterminationRow.outcome_id)
            .join(ConversationRow, ConversationRow.outcome_id == OutcomeClaimRow.outcome_id)
            .where(OutcomeClaimRow.outcome_id == outcome_id)
        ).first()
        if row is None:
            return None
        determination, claim, conversation = row
        event_rows = session.execute(
            select(
                OperationalEventRow,
                RawRecordRow,
                EvidenceMatchRow,
                ConnectorRow,
            )
            .join(
                EvidenceReferenceRow,
                EvidenceReferenceRow.event_id == OperationalEventRow.id,
            )
            .outerjoin(RawRecordRow, RawRecordRow.id == OperationalEventRow.raw_record_id)
            .outerjoin(
                EvidenceMatchRow,
                EvidenceMatchRow.raw_record_id == RawRecordRow.id,
            )
            .outerjoin(ConnectorRow, ConnectorRow.id == OperationalEventRow.connector_id)
            .where(EvidenceReferenceRow.determination_id == determination.id)
            .order_by(OperationalEventRow.timestamp, OperationalEventRow.id)
        ).all()
        claim_provenance_row = session.execute(
            select(RawRecordRow, EvidenceMatchRow, ConnectorRow)
            .outerjoin(
                EvidenceMatchRow,
                EvidenceMatchRow.raw_record_id == RawRecordRow.id,
            )
            .outerjoin(ConnectorRow, ConnectorRow.id == RawRecordRow.connector_id)
            .where(RawRecordRow.id == claim.raw_record_id)
        ).first()
        rule = (
            session.get(ContractRuleRow, determination.rule_id) if determination.rule_id else None
        )
        clause = (
            session.scalar(
                select(ContractClauseRow).where(ContractClauseRow.rule_id == determination.rule_id)
            )
            if determination.rule_id
            else None
        )
    result = _outcome_view(determination, claim)
    result.update(
        {
            "account_id": claim.account_id,
            "expected_action": claim.expected_action,
            "conversation": {
                "id": conversation.id,
                "intent": conversation.intent,
                "closed_at": conversation.closed_at.isoformat(),
            },
            "contract_clause": clause.text if clause else None,
            "rule": {
                "id": rule.id,
                "title": rule.title,
                "description": rule.description,
                "parameters": rule.parameters,
                "operation": rule.operation,
                "priority": rule.priority,
                "consequence": rule.consequence,
                "evidence_required": rule.evidence_required,
                "compilation_id": rule.compilation_id,
            }
            if rule
            else None,
            "vendor_claim_id": claim.vendor_claim_id,
            "agent_version": claim.agent_version,
            "claim_provenance": (
                {
                    "connector_id": claim_provenance_row[2].id
                    if claim_provenance_row and claim_provenance_row[2]
                    else None,
                    "connector_name": claim_provenance_row[2].name
                    if claim_provenance_row and claim_provenance_row[2]
                    else None,
                    "collection_method": claim_provenance_row[2].collection_method
                    if claim_provenance_row and claim_provenance_row[2]
                    else None,
                    "production_method": claim_provenance_row[2].production_method
                    if claim_provenance_row and claim_provenance_row[2]
                    else None,
                    "raw_record_id": claim_provenance_row[0].id if claim_provenance_row else None,
                    "source_record_id": claim_provenance_row[0].source_record_id
                    if claim_provenance_row
                    else None,
                    "payload_hash": f"sha256:{claim_provenance_row[0].payload_hash}"
                    if claim_provenance_row
                    else None,
                    "schema_version": claim_provenance_row[0].schema_version
                    if claim_provenance_row
                    else None,
                    "match_method": claim_provenance_row[1].match_method
                    if claim_provenance_row and claim_provenance_row[1]
                    else None,
                    "match_confidence": f"{claim_provenance_row[1].confidence:.4f}"
                    if claim_provenance_row and claim_provenance_row[1]
                    else None,
                    "raw_payload": claim_provenance_row[0].payload
                    if claim_provenance_row
                    else None,
                }
                if claim_provenance_row
                else None
            ),
            "evidence": [
                {
                    "id": event.id,
                    "source_system": event.source_system,
                    "source_record_id": event.source_record_id,
                    "event_type": event.event_type,
                    "timestamp": event.timestamp.isoformat(),
                    "customer_id": event.customer_id,
                    "outcome_id": event.outcome_id,
                    "values": event.values,
                    "ingested_at": event.ingested_at.isoformat(),
                    "provenance": {
                        "connector_id": connector.id if connector else event.connector_id,
                        "connector_name": connector.name
                        if connector
                        else event.source_system.replace("_", " ").title(),
                        "authority": connector.authority if connector else None,
                        "collection_method": connector.collection_method if connector else None,
                        "production_method": connector.production_method if connector else None,
                        "raw_record_id": raw.id if raw else event.raw_record_id,
                        "raw_payload": raw.payload if raw else None,
                        "payload_hash": f"sha256:{raw.payload_hash}" if raw else None,
                        "schema_version": raw.schema_version if raw else event.schema_version,
                        "match_status": match.status if match else None,
                        "match_method": match.match_method if match else event.match_method,
                        "match_confidence": f"{match.confidence:.4f}"
                        if match
                        else f"{event.match_confidence:.4f}",
                        "match_reason": match.reason if match else None,
                        "received_at": raw.received_at.isoformat()
                        if raw
                        else event.ingested_at.isoformat(),
                    },
                }
                for event, raw, match, connector in event_rows
            ],
            "evaluated_at": determination.evaluated_at.isoformat(),
            "engine_version": determination.engine_version,
            "duplicate_winner_outcome_id": determination.duplicate_winner_outcome_id,
            "computed_timeline_markers": (
                [
                    {
                        "id": f"COMPUTED-{outcome_id}-R3-DEADLINE",
                        "marker_type": "completion_window_expired",
                        "timestamp": (claim.closed_at + timedelta(hours=2)).isoformat(),
                        "description": ("Computed contractual two-hour completion deadline"),
                    }
                ]
                if determination.rule_id == "R3"
                else []
            ),
        }
    )
    return result


def all_disputes() -> list[dict[str, object]]:
    _, rows = list_outcomes(0, 10_000, status="disputed")
    return rows


def evidence_package() -> dict[str, object]:
    global _public_evidence_package_cache
    if _public_evidence_package_cache is not None:
        return _public_evidence_package_cache
    with _public_evidence_package_lock:
        if _public_evidence_package_cache is None:
            disputes = all_disputes()
            _public_evidence_package_cache = {
                "reconciliation": summary(),
                "outcomes": [outcome_detail(str(row["outcome_id"])) for row in disputes],
                "synthetic_disclosure": DISCLOSURE,
            }
    return _public_evidence_package_cache
