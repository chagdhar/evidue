from datetime import datetime, timedelta
from decimal import Decimal

from .models import EvidenceReference, OperationalEvent, OutcomeClaim, OutcomeDetermination

START = datetime(2026, 6, 1)
END = datetime(2026, 7, 1)
EVALUATED_AT = datetime(2026, 7, 1, 12)


def _result(
    claim: OutcomeClaim,
    events: list[OperationalEvent],
    status: str,
    reason: str,
    rule_id: str | None,
) -> OutcomeDetermination:
    evidence = tuple(EvidenceReference(event.id, event.event_type) for event in events)
    payable = claim.billed_amount if status == "payable" else Decimal("0.00")
    return OutcomeDetermination(
        claim=claim,
        status=status,  # type: ignore[arg-type]
        reason=reason,
        rule_id=rule_id,
        evidence=evidence,
        payable_amount=payable,
        evaluated_at=EVALUATED_AT,
    )


def evaluate(claim: OutcomeClaim, events: list[OperationalEvent]) -> OutcomeDetermination:
    """Evaluate one claim with deterministic, ordered contract rules."""
    if not claim.outcome_id or not claim.customer_id or not claim.account_id:
        return _result(claim, events, "needs_review", "Missing required claim identifiers", "R7")
    if not events or not any(event.event_type == "ai_closed" for event in events):
        return _result(claim, events, "needs_review", "Missing AI closure evidence", "R7")
    if any(event.values.get("contradictory") == "true" for event in events):
        return _result(claim, events, "needs_review", "Contradictory operational evidence", "R7")
    if not START <= claim.closed_at < END:
        return _result(
            claim, events, "disputed", "Outcome falls outside the invoice billing period", "R6"
        )

    recontact_limit = claim.closed_at + timedelta(days=7)
    if any(
        event.event_type == "customer_recontact"
        and event.values.get("intent") == claim.intent
        and claim.closed_at < event.timestamp <= recontact_limit
        for event in events
    ):
        return _result(
            claim,
            events,
            "disputed",
            "Same-intent recontact within seven calendar days",
            "R1",
        )

    human_limit = claim.closed_at + timedelta(hours=24)
    if any(
        event.event_type in {"human_completion", "human_material_correction"}
        and claim.closed_at < event.timestamp <= human_limit
        for event in events
    ):
        return _result(
            claim,
            events,
            "disputed",
            "Human completed or materially corrected the work within 24 hours",
            "R2",
        )

    action_events = [
        event for event in events if event.values.get("action") == claim.expected_action
    ]
    if not action_events:
        return _result(
            claim,
            events,
            "needs_review",
            "Missing evidence for the promised downstream action",
            "R7",
        )
    action_limit = claim.closed_at + timedelta(hours=2)
    if any(event.event_type == "downstream_failed" for event in action_events) or not any(
        event.event_type == "downstream_succeeded"
        and claim.closed_at <= event.timestamp <= action_limit
        for event in action_events
    ):
        return _result(
            claim,
            events,
            "disputed",
            "Promised downstream action failed within the required two-hour window",
            "R3",
        )

    if any(event.event_type == "duplicate_attribution" for event in events):
        return _result(
            claim,
            events,
            "disputed",
            "Duplicate billed outcome in the 24-hour attribution window",
            "R4",
        )

    if any(
        event.values.get("account_id") not in (None, claim.account_id)
        or event.values.get("action") not in (None, claim.expected_action)
        for event in events
    ):
        return _result(
            claim,
            events,
            "disputed",
            "Customer account or expected action did not match operational evidence",
            "R5",
        )

    return _result(
        claim,
        events,
        "payable",
        "All applicable contractual rules passed",
        None,
    )


def summarize(items: list[OutcomeDetermination]) -> dict[str, object]:
    billed = sum((item.claim.billed_amount for item in items), Decimal())
    payable = sum((item.payable_amount for item in items), Decimal())
    categories: dict[str, int] = {}
    for item in items:
        if item.status == "disputed":
            key = item.rule_id or "unknown"
            categories[key] = categories.get(key, 0) + 1
    return {
        "claimed_outcomes": len(items),
        "payable_outcomes": sum(item.status == "payable" for item in items),
        "disputed_outcomes": sum(item.status == "disputed" for item in items),
        "needs_review_outcomes": sum(item.status == "needs_review" for item in items),
        "submitted_amount": f"{billed:.2f}",
        "payable_amount": f"{payable:.2f}",
        "recommended_deduction": f"{billed - payable:.2f}",
        "categories": categories,
    }
