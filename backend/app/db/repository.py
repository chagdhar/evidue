import os
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from sqlalchemy import create_engine, delete, func, or_, select
from sqlalchemy.orm import joinedload, sessionmaker

from app.domain.engine import evaluate
from app.domain.models import RULES, OperationalEvent, OutcomeClaim
from app.fixtures.demo import INVOICE_ID, demo_fixture

from .models import (
    Base,
    ContractClauseRow,
    ContractRow,
    ContractRuleRow,
    ConversationRow,
    DemoStateRow,
    EvidenceReferenceRow,
    InvoiceRow,
    OperationalEventRow,
    OutcomeClaimRow,
    OutcomeDeterminationRow,
    ReconciliationRow,
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


def initialize() -> None:
    Base.metadata.create_all(engine)


def _money(value: Decimal) -> str:
    return f"{value:.2f}"


def reset() -> dict[str, object]:
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    records = demo_fixture()
    with SessionLocal.begin() as session:
        contract = ContractRow(
            id="CONTRACT-ACME-NOVA-2026",
            customer="Acme Commerce",
            vendor="Nova Support AI",
            period_start=datetime(2026, 6, 1),
            period_end=datetime(2026, 7, 1),
            price_per_outcome=Decimal("1.50"),
        )
        session.add(contract)
        for rule in RULES:
            session.add(
                ContractRuleRow(
                    id=rule.id,
                    title=rule.title,
                    description=rule.description,
                    parameters=rule.parameters,
                    evidence_required=list(rule.evidence_required),
                )
            )
        session.flush()
        clause_text = {
            "R1": "A resolution is not billable when the customer recontacts support for the same intent within seven calendar days.",
            "R2": "A resolution is not billable when a human completes or materially corrects the promised work within 24 hours.",
            "R3": "A promised downstream action must complete successfully within two hours.",
            "R4": "Only one outcome is billable for the same customer and intent in a 24-hour attribution window.",
            "R5": "Evidence must match the expected customer account and promised action.",
            "R6": "The outcome must occur during the invoice billing period.",
            "R7": "The claim must include sufficient identifiers to associate supporting evidence.",
        }
        for rule in RULES:
            session.add(
                ContractClauseRow(
                    id=f"CLAUSE-{rule.id}",
                    contract_id=contract.id,
                    rule_id=rule.id,
                    text=clause_text[rule.id],
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
                    outcome_id=record.claim.outcome_id,
                    invoice_id=record.claim.invoice_id,
                    customer_id=record.claim.customer_id,
                    intent=record.claim.intent,
                    vendor_claim=record.claim.vendor_claim,
                    closed_at=record.claim.closed_at,
                    expected_action=record.claim.expected_action,
                    account_id=record.claim.account_id,
                    billed_amount=record.claim.billed_amount,
                )
                for record in records
            ]
        )
        session.add_all(
            [
                ConversationRow(
                    id=record.conversation.id,
                    outcome_id=record.conversation.outcome_id,
                    customer_id=record.conversation.customer_id,
                    intent=record.conversation.intent,
                    closed_at=record.conversation.closed_at,
                )
                for record in records
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
                )
                for record in records
                for event in record.events
            ]
        )
        session.add(DemoStateRow(id=1, seeded=True, reconciled=False))
    return demo_status()


def demo_status() -> dict[str, object]:
    initialize()
    with SessionLocal() as session:
        state = session.get(DemoStateRow, 1)
        claim_count = session.scalar(select(func.count()).select_from(OutcomeClaimRow)) or 0
    return {
        "seeded": bool(state and state.seeded),
        "reconciled": bool(state and state.reconciled),
        "claimed_outcomes": claim_count,
        "billing_period": "2026-06-01 through 2026-06-30",
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
    if not demo_status()["seeded"]:
        reset()
    with SessionLocal.begin() as session:
        session.execute(delete(EvidenceReferenceRow))
        session.execute(delete(OutcomeDeterminationRow))
        session.execute(delete(ReconciliationRow))
        reconciliation = ReconciliationRow(
            id="REC-2026-06-001",
            invoice_id=INVOICE_ID,
            evaluated_at=datetime(2026, 7, 1, 12),
            engine_version="2026.06.1",
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
        for claim_row in claims:
            domain_events = [
                _domain_event(event) for event in by_outcome.get(claim_row.outcome_id, [])
            ]
            result = evaluate(_domain_claim(claim_row), domain_events)
            determination = OutcomeDeterminationRow(
                reconciliation_id=reconciliation.id,
                outcome_id=claim_row.outcome_id,
                rule_id=result.rule_id,
                status=result.status,
                reason=result.reason,
                billed_amount=result.claim.billed_amount,
                payable_amount=result.payable_amount,
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
        state = session.get(DemoStateRow, 1)
        if state:
            state.reconciled = True
    return summary()


def summary() -> dict[str, object]:
    with SessionLocal() as session:
        rows = session.execute(
            select(
                OutcomeDeterminationRow.status,
                OutcomeDeterminationRow.rule_id,
                OutcomeDeterminationRow.billed_amount,
                OutcomeDeterminationRow.payable_amount,
            )
        ).all()
        reconciliation = session.scalar(
            select(ReconciliationRow).order_by(ReconciliationRow.evaluated_at.desc())
        )
        price = session.scalar(select(ContractRow.price_per_outcome)) or Decimal()
    billed = sum((row.billed_amount for row in rows), Decimal())
    payable = sum((row.payable_amount for row in rows), Decimal())
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
                {"label": labels[row.rule_id], "count": 0, "amount_decimal": Decimal()},
            )
            category["count"] = int(category["count"]) + 1
            category["amount_decimal"] = (
                Decimal(str(category["amount_decimal"])) + row.billed_amount
            )
    for category in categories.values():
        category["amount"] = _money(Decimal(str(category.pop("amount_decimal"))))
    return {
        "reconciliation_id": reconciliation.id if reconciliation else "",
        "status": "completed" if rows else "not_run",
        "claimed_outcomes": len(rows),
        "payable_outcomes": sum(row.status == "payable" for row in rows),
        "disputed_outcomes": sum(row.status == "disputed" for row in rows),
        "needs_review_outcomes": sum(row.status == "needs_review" for row in rows),
        "submitted_amount": _money(billed),
        "payable_amount": _money(payable),
        "recommended_deduction": _money(billed - payable),
        "price_per_outcome": _money(price),
        "categories": categories,
        "synthetic_disclosure": DISCLOSURE,
    }


def contract() -> dict[str, object]:
    with SessionLocal() as session:
        row = session.scalar(
            select(ContractRow).options(
                joinedload(ContractRow.clauses).joinedload(ContractClauseRow.rule)
            )
        )
        if row is None:
            raise LookupError("Demo contract is not seeded")
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
                        "parameters": clause.rule.parameters,
                        "evidence_required": clause.rule.evidence_required,
                        "consequence": "Charge is not payable when this rule fails.",
                    },
                }
                for clause in sorted(row.clauses, key=lambda item: item.rule_id)
            ],
            "evidence_sources": [
                "Nova Support AI agent log",
                "Acme support desk",
                "Payment processor",
                "Billing export",
                "Product account system",
            ],
        }


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
        "payable_amount": _money(determination.payable_amount),
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
        events = session.scalars(
            select(OperationalEventRow)
            .where(OperationalEventRow.outcome_id == outcome_id)
            .order_by(OperationalEventRow.timestamp, OperationalEventRow.id)
        ).all()
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
            }
            if rule
            else None,
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
                }
                for event in events
            ],
            "evaluated_at": determination.evaluated_at.isoformat(),
            "engine_version": determination.engine_version,
        }
    )
    return result


def all_disputes() -> list[dict[str, object]]:
    _, rows = list_outcomes(0, 10_000, status="disputed")
    return rows


def evidence_package() -> dict[str, object]:
    disputes = all_disputes()
    return {
        "reconciliation": summary(),
        "outcomes": [outcome_detail(str(row["outcome_id"])) for row in disputes],
        "synthetic_disclosure": DISCLOSURE,
    }
