from datetime import datetime, timedelta

from app.domain.engine import evaluate
from app.domain.models import OperationalEvent, OutcomeClaim

BASE = datetime(2026, 6, 1, 9)
COUNTS = [("recontact", 720), ("human", 360), ("downstream", 300), ("duplicate", 180), ("mismatch", 120)]


def events_for(claim: OutcomeClaim, category: str | None) -> list[OperationalEvent]:
    at = claim.closed_at
    def event(suffix: str, typ: str, when: datetime, values: dict[str, str]) -> OperationalEvent:
        return OperationalEvent(f"EV-{claim.outcome_id}-{suffix}", "acme_operations", f"src-{claim.outcome_id}-{suffix}", typ, when, claim.customer_id, claim.outcome_id, values, when)
    events = [event("AI", "ai_closed", at, {"account_id": claim.account_id, "action": claim.expected_action})]
    if category == "recontact": events.append(event("RECONTACT", "customer_recontact", at + timedelta(days=1), {"intent": claim.intent}))
    elif category == "human": events.append(event("HUMAN", "human_completion", at + timedelta(minutes=45), {"action": claim.expected_action}))
    elif category == "downstream": events.append(event("FAILED", "downstream_failed", at + timedelta(minutes=20), {"action": claim.expected_action}))
    elif category == "duplicate":
        events += [event("DUP", "duplicate_attribution", at + timedelta(minutes=5), {"action": claim.expected_action}), event("SUCCESS", "downstream_succeeded", at + timedelta(minutes=30), {"account_id": claim.account_id, "action": claim.expected_action})]
    elif category == "mismatch":
        events += [event("MISMATCH", "account_verified", at + timedelta(minutes=5), {"account_id": "ACC-WRONG", "action": claim.expected_action}), event("SUCCESS", "downstream_succeeded", at + timedelta(minutes=30), {"account_id": claim.account_id, "action": claim.expected_action})]
    else: events.append(event("SUCCESS", "downstream_succeeded", at + timedelta(minutes=30), {"account_id": claim.account_id, "action": claim.expected_action}))
    if claim.outcome_id == "OUT-004821": events += [event("EXPIRE", "completion_window_expired", at+timedelta(hours=2), {"action":"refund"}), event("HUMAN_LATE", "human_refund_completed", at+timedelta(hours=4), {"action":"refund"})]
    return events


def demo_records():
    categories = [kind for kind, count in COUNTS for _ in range(count)] + [None] * 8320
    categories[4820] = "downstream"  # stable failed-refund; replace the displaced R3 line below
    categories[1080] = None
    records = []
    for index, category in enumerate(categories, 1):
        outcome_id = f"OUT-{index:06d}"
        claim = OutcomeClaim(outcome_id, f"CUST-{index:06d}", "refund" if outcome_id == "OUT-004821" else "order_support", True, BASE + timedelta(minutes=index), "refund" if outcome_id == "OUT-004821" else "order_update", f"ACC-{index:06d}")
        records.append(evaluate(claim, events_for(claim, category)))
    return records


def review_record():
    return evaluate(OutcomeClaim("OUT-REVIEW-001", "CUST-REVIEW", "refund", True, BASE, "refund", "ACC-REVIEW"), [])
