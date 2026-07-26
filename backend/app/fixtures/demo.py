from collections import Counter
from datetime import datetime, timedelta

from app.domain.engine import evaluate
from app.domain.models import OperationalEvent, OutcomeClaim

BASE = datetime(2026, 6, 1, 9)
COUNTS = [("recontact", 720), ("human", 360), ("downstream", 300), ("duplicate", 180), ("mismatch", 120)]
def _events(claim, category):
    at = claim.closed_at; events = [OperationalEvent(f"EV-{claim.outcome_id}-AI", "nova_agent", f"agent-{claim.outcome_id}", "ai_closed", at, claim.customer_id, claim.outcome_id, {"account_id": claim.account_id, "action": claim.expected_action}, at)]
    if category:
        types = {"recontact": "customer_recontact", "human": "human_completion", "downstream": "payment_refund_rejected", "duplicate": "duplicate_attribution", "mismatch": "account_action_mismatch"}
        extra = at + timedelta(minutes=30 if category != "recontact" else 1440); events.append(OperationalEvent(f"EV-{claim.outcome_id}-{category}", "operations", f"ops-{claim.outcome_id}", types[category], extra, claim.customer_id, claim.outcome_id, {"category": category}, extra))
    if claim.outcome_id == "OUT-004821":
        events += [OperationalEvent("EV-4821-EXPIRE", "evidue", "window-4821", "two_hour_window_expired", at+timedelta(hours=2), claim.customer_id, claim.outcome_id, {"category": "downstream"}, at+timedelta(hours=2)), OperationalEvent("EV-4821-HUMAN", "support", "human-4821", "human_refund_completed", at+timedelta(hours=4), claim.customer_id, claim.outcome_id, {"category": "downstream"}, at+timedelta(hours=4))]
    return events
def demo_records():
    categories = [c for c, n in COUNTS for _ in range(n)] + [None] * 8320; result = []
    for index, category in enumerate(categories, 1):
        oid = f"OUT-{index:06d}"; category = "downstream" if oid == "OUT-004821" else category
        claim = OutcomeClaim(oid, f"CUST-{index:06d}", "refund" if oid == "OUT-004821" else "order_support", True, BASE + timedelta(minutes=index % 40000), "refund" if oid == "OUT-004821" else "order_update", f"ACC-{index:06d}")
        result.append(evaluate(claim, _events(claim, category)))
    if Counter(d.rule_id for d in result if d.status == "disputed")["R3"] > 300:
        for pos, d in enumerate(result):
            if d.rule_id == "R3" and d.claim.outcome_id != "OUT-004821": result[pos] = evaluate(d.claim, _events(d.claim, None)); break
    return result
def review_record():
    return evaluate(OutcomeClaim("OUT-REVIEW-001", "CUST-REVIEW", "refund", True, BASE, "refund", "ACC-REVIEW"), [])
