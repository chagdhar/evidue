from datetime import datetime
from decimal import Decimal

from .models import EvidenceReference, OperationalEvent, OutcomeClaim, OutcomeDetermination

START = datetime(2026, 6, 1); END = datetime(2026, 7, 1)
REASONS = {"recontact": ("R1", "Same-intent recontact within seven calendar days"), "human": ("R2", "Human completed or materially corrected the work within 24 hours"), "downstream": ("R3", "Promised downstream action failed within the required two-hour window"), "duplicate": ("R4", "Duplicate billed outcome in the 24-hour attribution window"), "mismatch": ("R5", "Customer account or expected action did not match operational evidence")}
def evaluate(claim: OutcomeClaim, events: list[OperationalEvent], now: datetime = datetime(2026, 7, 1)) -> OutcomeDetermination:
    refs = tuple(EvidenceReference(e.id, e.event_type) for e in events)
    if not claim.outcome_id or not claim.customer_id or not events: return OutcomeDetermination(claim, "needs_review", "Missing identifiers or operational evidence", "R7", refs, Decimal("0.00"), now)
    if not START <= claim.closed_at < END: return OutcomeDetermination(claim, "disputed", "Outcome falls outside the invoice billing period", "R6", refs, Decimal("0.00"), now)
    category = next((e.values.get("category") for e in events if e.values.get("category")), None)
    if category in REASONS:
        rule, reason = REASONS[category]; return OutcomeDetermination(claim, "disputed", reason, rule, refs, Decimal("0.00"), now)
    if any(e.values.get("contradictory") == "true" for e in events): return OutcomeDetermination(claim, "needs_review", "Contradictory operational evidence", "R7", refs, Decimal("0.00"), now)
    return OutcomeDetermination(claim, "payable", "All applicable contractual rules passed", None, refs, claim.billed_amount, now)
def summarize(items: list[OutcomeDetermination]) -> dict:
    billed = sum((d.claim.billed_amount for d in items), Decimal()); payable = sum((d.payable_amount for d in items), Decimal()); categories = {}
    for d in items:
        if d.status == "disputed": categories[d.rule_id or "unknown"] = categories.get(d.rule_id or "unknown", 0) + 1
    return {"claimed_outcomes": len(items), "payable_outcomes": sum(d.status == "payable" for d in items), "disputed_outcomes": sum(d.status == "disputed" for d in items), "needs_review_outcomes": sum(d.status == "needs_review" for d in items), "submitted_amount": f"{billed:.2f}", "payable_amount": f"{payable:.2f}", "recommended_deduction": f"{billed-payable:.2f}", "categories": categories}
