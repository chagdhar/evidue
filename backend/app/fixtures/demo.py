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
                    {"original_outcome_id": (f"OUT-{int(claim.outcome_id[-6:]) - 1380:06d}")},
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
    if index <= 1380:
        return "payable" if index == 1081 else "downstream"
    if index <= 1560:
        return "duplicate"
    if index <= 1680:
        return "mismatch"
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
        duplicate_winner_index = index - 1380 if 1381 <= index <= 1560 else index
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
