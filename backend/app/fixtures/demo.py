from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta

from app.domain.engine import evaluate, reconcile
from app.domain.models import (
    Conversation,
    OperationalEvent,
    OutcomeClaim,
    OutcomeDetermination,
)

BASE = datetime(2026, 6, 1, 9)
INGESTED_AT = datetime(2026, 7, 1, 8)
INVOICE_ID = "INV-NOVA-2026-06"
CATEGORY_COUNTS = {
    "recontact": 720,
    "human": 360,
    "downstream": 300,
    "duplicate": 180,
    "mismatch": 120,
    "payable": 8320,
}


@dataclass(frozen=True)
class DemoRecord:
    claim: OutcomeClaim
    conversation: Conversation
    events: tuple[OperationalEvent, ...]


@dataclass(frozen=True)
class DemoScenario:
    id: str
    name: str
    description: str
    demo_outcome_id: str
    fixture: Callable[[], list[DemoRecord]]


def _event(
    claim: OutcomeClaim,
    suffix: str,
    source_system: str,
    event_type: str,
    timestamp: datetime,
    values: dict[str, str],
) -> OperationalEvent:
    return OperationalEvent(
        id=f"EV-{claim.outcome_id}-{suffix}",
        source_system=source_system,
        source_record_id=f"{source_system}-{claim.outcome_id}-{suffix}",
        event_type=event_type,
        timestamp=timestamp,
        customer_id=claim.customer_id,
        outcome_id=claim.outcome_id,
        values=values,
        ingested_at=INGESTED_AT,
    )


def events_for(claim: OutcomeClaim, category: str) -> tuple[OperationalEvent, ...]:
    at = claim.closed_at
    events = [
        _event(
            claim,
            "CLOSED",
            "nova_agent",
            "ai_closed",
            at,
            {"account_id": claim.account_id, "action": claim.expected_action},
        )
    ]
    if category == "recontact":
        events.append(
            _event(
                claim,
                "RECONTACT",
                "acme_support",
                "customer_recontact",
                at + timedelta(days=1),
                {"intent": claim.intent},
            )
        )
    elif category == "human":
        events.append(
            _event(
                claim,
                "HUMAN",
                "acme_support",
                "human_completion",
                at + timedelta(minutes=45),
                {"action": claim.expected_action},
            )
        )
    elif category == "downstream":
        events.append(
            _event(
                claim,
                "FAILED",
                "payment_processor",
                "downstream_failed",
                at + timedelta(minutes=20),
                {
                    "account_id": claim.account_id,
                    "action": claim.expected_action,
                    "result": "rejected",
                },
            )
        )
    elif category == "duplicate":
        events.extend(
            [
                _event(
                    claim,
                    "SUCCESS",
                    "order_operations",
                    "downstream_succeeded",
                    at + timedelta(minutes=30),
                    {"account_id": claim.account_id, "action": claim.expected_action},
                ),
                _event(
                    claim,
                    "DUPLICATE",
                    "billing_export",
                    "duplicate_attribution",
                    at + timedelta(minutes=35),
                    {"original_outcome_id": (f"OUT-{int(claim.outcome_id[-6:]) - 300:06d}")},
                ),
            ]
        )
    elif category == "mismatch":
        events.extend(
            [
                _event(
                    claim,
                    "SUCCESS",
                    "order_operations",
                    "downstream_succeeded",
                    at + timedelta(minutes=30),
                    {"account_id": claim.account_id, "action": claim.expected_action},
                ),
                _event(
                    claim,
                    "MISMATCH",
                    "product_accounts",
                    "account_action_mismatch",
                    at + timedelta(minutes=35),
                    {
                        "account_id": claim.account_id,
                        "action": claim.expected_action,
                        "observed_account_id": "ACC-WRONG",
                        "observed_action": claim.expected_action,
                    },
                ),
            ]
        )
    else:
        events.append(
            _event(
                claim,
                "SUCCESS",
                "order_operations",
                "downstream_succeeded",
                at + timedelta(minutes=30),
                {"account_id": claim.account_id, "action": claim.expected_action},
            )
        )
    if claim.outcome_id == "OUT-004821":
        events.extend(
            [
                _event(
                    claim,
                    "HUMAN-LATE",
                    "acme_support",
                    "human_refund_completed",
                    at + timedelta(hours=4),
                    {"action": "refund"},
                ),
            ]
        )
    return tuple(events)


def category_for(index: int) -> str:
    if index == 4821:
        return "downstream"
    if index <= 720:
        return "recontact"
    if index <= 1080:
        return "human"
    if index <= 1260:
        return "payable"
    if index <= 1380:
        return "downstream"
    if index <= 1560:
        return "duplicate"
    if index <= 1680:
        return "mismatch"
    if index <= 1859:
        return "downstream"
    return "payable"


def demo_fixture() -> list[DemoRecord]:
    records: list[DemoRecord] = []
    for index in range(1, 10_001):
        outcome_id = f"OUT-{index:06d}"
        closed_at = BASE + timedelta(minutes=index)
        intent = (
            "refund"
            if outcome_id == "OUT-004821"
            else ("cancel_subscription" if index % 3 == 0 else "order_support")
        )
        action = (
            "refund"
            if outcome_id == "OUT-004821"
            else ("cancel_subscription" if intent == "cancel_subscription" else "order_update")
        )
        duplicate_winner_index = index - 300 if 1381 <= index <= 1560 else index
        claim = OutcomeClaim(
            outcome_id=outcome_id,
            invoice_id=INVOICE_ID,
            customer_id=f"CUST-{duplicate_winner_index:06d}",
            intent=intent,
            vendor_claim="resolved",
            closed_at=closed_at,
            expected_action=action,
            account_id=f"ACC-{index:06d}",
        )
        conversation = Conversation(
            id=f"CONV-{index:06d}",
            customer_id=claim.customer_id,
            intent=claim.intent,
            closed_at=closed_at,
            outcome_id=outcome_id,
        )
        category = category_for(index)
        records.append(DemoRecord(claim, conversation, events_for(claim, category)))
    return records


def _focused_record(
    outcome_id: str,
    customer_id: str,
    closed_at: datetime,
    category: str,
    intent: str = "refund",
) -> DemoRecord:
    expected_action = "refund" if intent == "refund" else "order_update"
    claim = OutcomeClaim(
        outcome_id=outcome_id,
        invoice_id=INVOICE_ID,
        customer_id=customer_id,
        intent=intent,
        vendor_claim="resolved",
        closed_at=closed_at,
        expected_action=expected_action,
        account_id=f"ACC-{outcome_id}",
    )
    return DemoRecord(
        claim=claim,
        conversation=Conversation(
            id=f"CONV-{outcome_id}",
            customer_id=customer_id,
            intent=intent,
            closed_at=closed_at,
            outcome_id=outcome_id,
        ),
        events=events_for(claim, category),
    )


def evidence_review_fixture() -> list[DemoRecord]:
    ambiguous = _focused_record(
        "CASE-REVIEW-001",
        "CUST-REVIEW-001",
        datetime(2026, 6, 10, 10),
        "payable",
    )
    failure = _event(
        ambiguous.claim,
        "CONTRADICTORY-FAILURE",
        "payment_processor",
        "downstream_failed",
        ambiguous.claim.closed_at + timedelta(minutes=35),
        {
            "account_id": ambiguous.claim.account_id,
            "action": ambiguous.claim.expected_action,
            "result": "rejected",
        },
    )
    payable = _focused_record(
        "CASE-REVIEW-002",
        "CUST-REVIEW-002",
        datetime(2026, 6, 10, 11),
        "payable",
    )
    return [
        DemoRecord(
            ambiguous.claim,
            ambiguous.conversation,
            (*ambiguous.events, failure),
        ),
        payable,
    ]


def recovery_fixture() -> list[DemoRecord]:
    customer_id = "CUST-RECOVERY"
    first_at = datetime(2026, 6, 12, 9)
    return [
        _focused_record(
            "CASE-RECOVERY-001",
            customer_id,
            first_at,
            "downstream",
            "order_support",
        ),
        _focused_record(
            "CASE-RECOVERY-002",
            customer_id,
            first_at + timedelta(hours=1),
            "payable",
            "order_support",
        ),
    ]


def duplicate_window_fixture() -> list[DemoRecord]:
    customer_id = "CUST-DUPLICATE-WINDOW"
    first_at = datetime(2026, 6, 15, 9)
    return [
        _focused_record(
            "CASE-DUP-001",
            customer_id,
            first_at,
            "payable",
            "cancel_subscription",
        ),
        _focused_record(
            "CASE-DUP-002",
            customer_id,
            first_at + timedelta(hours=8),
            "payable",
            "cancel_subscription",
        ),
        _focused_record(
            "CASE-DUP-003",
            customer_id,
            first_at + timedelta(hours=23),
            "payable",
            "cancel_subscription",
        ),
    ]


SCENARIOS = (
    DemoScenario(
        "headline",
        "Full invoice reconciliation",
        "10,000 claimed outcomes across all five confirmed dispute categories.",
        "OUT-004821",
        demo_fixture,
    ),
    DemoScenario(
        "evidence_review",
        "Contradictory evidence",
        "Conflicting directly matched records isolate an amount for review without deducting it.",
        "CASE-REVIEW-001",
        evidence_review_fixture,
    ),
    DemoScenario(
        "recovery",
        "Failed action, valid follow-up",
        "A failed first outcome is disputed while a valid follow-up remains payable.",
        "CASE-RECOVERY-001",
        recovery_fixture,
    ),
    DemoScenario(
        "duplicate_window",
        "Duplicate attribution window",
        "Three otherwise-payable claims demonstrate the deterministic 24-hour winner rule.",
        "CASE-DUP-002",
        duplicate_window_fixture,
    ),
)
SCENARIOS_BY_ID = {scenario.id: scenario for scenario in SCENARIOS}


def scenario_fixture(scenario_id: str) -> list[DemoRecord]:
    try:
        return SCENARIOS_BY_ID[scenario_id].fixture()
    except KeyError as exc:
        raise ValueError(f"Unknown demo scenario: {scenario_id}") from exc


def demo_records() -> list[OutcomeDetermination]:
    return reconcile([(record.claim, list(record.events)) for record in demo_fixture()])


def review_record() -> OutcomeDetermination:
    claim = OutcomeClaim(
        "OUT-REVIEW-001",
        INVOICE_ID,
        "CUST-REVIEW",
        "refund",
        "resolved",
        BASE,
        "refund",
        "ACC-REVIEW",
    )
    return evaluate(claim, [])
