from decimal import Decimal

from app.domain.engine import summarize
from app.fixtures import demo_records, review_record
from app.fixtures.demo import events_for


def test_exact_demo_totals_and_mutual_categories():
    summary = summarize(demo_records())
    assert summary["claimed_outcomes"] == 10_000
    assert summary["payable_outcomes"] == 8_320
    assert summary["disputed_outcomes"] == 1_680
    assert summary["submitted_amount"] == "15000.00"
    assert summary["payable_amount"] == "12480.00"
    assert summary["recommended_deduction"] == "2520.00"
    assert summary["categories"] == {"R1": 720, "R2": 360, "R3": 300, "R4": 180, "R5": 120}


def test_failed_refund_and_needs_review_are_deterministic():
    record = next(item for item in demo_records() if item.claim.outcome_id == "OUT-004821")
    assert record.status == "disputed"
    assert record.rule_id == "R3"
    assert record.payable_amount == Decimal("0.00")
    assert review_record().status == "needs_review"


def test_each_dispute_is_driven_by_actual_evidence():
    categories = {"R1": ("recontact", "customer_recontact"), "R2": ("human", "human_completion"), "R3": ("downstream", "downstream_failed"), "R4": ("duplicate", "duplicate_attribution"), "R5": ("mismatch", "account_verified")}
    records = demo_records()
    for rule_id, (category, event_type) in categories.items():
        record = next(item for item in records if item.rule_id == rule_id)
        assert any(event.event_type == event_type for event in events_for(record.claim, category))
