from datetime import datetime, timedelta
from decimal import Decimal

from .models import EvidenceReference, OperationalEvent, OutcomeClaim, OutcomeDetermination

START = datetime(2026, 6, 1)
END = datetime(2026, 7, 1)


def evaluate(claim: OutcomeClaim, events: list[OperationalEvent], now: datetime = END) -> OutcomeDetermination:
    """Pure, ordered contract evaluation. First failed rule owns the dispute."""
    refs = tuple(EvidenceReference(event.id, event.event_type) for event in events)
    if not claim.outcome_id or not claim.customer_id or not events:
        return OutcomeDetermination(claim, "needs_review", "Missing claim identifiers or operational evidence", "R7", refs, Decimal("0.00"), now)
    if not START <= claim.closed_at < END:
        return OutcomeDetermination(claim, "disputed", "Outcome falls outside the invoice billing period", "R6", refs, Decimal("0.00"), now)
    if any(event.values.get("contradictory") == "true" for event in events):
        return OutcomeDetermination(claim, "needs_review", "Contradictory operational evidence", "R7", refs, Decimal("0.00"), now)
    if any(event.event_type == "customer_recontact" and event.values.get("intent") == claim.intent and claim.closed_at.date() <= event.timestamp.date() <= (claim.closed_at + timedelta(days=7)).date() for event in events):
        return OutcomeDetermination(claim, "disputed", "Same-intent recontact within seven calendar days", "R1", refs, Decimal("0.00"), now)
    if any(event.event_type == "human_completion" and event.timestamp <= claim.closed_at + timedelta(hours=24) for event in events):
        return OutcomeDetermination(claim, "disputed", "Human completed or materially corrected the work within 24 hours", "R2", refs, Decimal("0.00"), now)
    action_events = [event for event in events if event.values.get("action") == claim.expected_action]
    if not action_events:
        return OutcomeDetermination(claim, "needs_review", "Missing downstream action evidence", "R7", refs, Decimal("0.00"), now)
    if any(event.event_type == "downstream_failed" for event in action_events) or not any(event.event_type == "downstream_succeeded" and event.timestamp <= claim.closed_at + timedelta(hours=2) for event in action_events):
        return OutcomeDetermination(claim, "disputed", "Promised downstream action failed within the required two-hour window", "R3", refs, Decimal("0.00"), now)
    if any(event.event_type == "duplicate_attribution" for event in events):
        return OutcomeDetermination(claim, "disputed", "Duplicate billed outcome in the 24-hour attribution window", "R4", refs, Decimal("0.00"), now)
    if any(event.values.get("account_id") not in (None, claim.account_id) or event.values.get("action") not in (None, claim.expected_action) for event in events):
        return OutcomeDetermination(claim, "disputed", "Customer account or expected action did not match operational evidence", "R5", refs, Decimal("0.00"), now)
    return OutcomeDetermination(claim, "payable", "All applicable contractual rules passed", None, refs, claim.billed_amount, now)


def summarize(items: list[OutcomeDetermination]) -> dict:
    billed = sum((item.claim.billed_amount for item in items), Decimal())
    payable = sum((item.payable_amount for item in items), Decimal())
    categories: dict[str, int] = {}
    for item in items:
        if item.status == "disputed":
            categories[item.rule_id or "unknown"] = categories.get(item.rule_id or "unknown", 0) + 1
    return {"claimed_outcomes": len(items), "payable_outcomes": sum(item.status == "payable" for item in items), "disputed_outcomes": sum(item.status == "disputed" for item in items), "needs_review_outcomes": sum(item.status == "needs_review" for item in items), "submitted_amount": f"{billed:.2f}", "payable_amount": f"{payable:.2f}", "recommended_deduction": f"{billed-payable:.2f}", "categories": categories}
