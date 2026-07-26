from dataclasses import replace
from datetime import datetime, timedelta
from decimal import Decimal

from app.domain.engine import evaluate, summarize
from app.domain.models import OperationalEvent
from app.fixtures.demo import (
    CATEGORY_COUNTS,
    category_for,
    demo_fixture,
    demo_records,
    events_for,
    review_record,
)


def test_exact_demo_totals_and_mutually_exclusive_categories():
    records = demo_records()
    summary = summarize(records)
    assert summary == {
        "claimed_outcomes": 10_000,
        "payable_outcomes": 8_320,
        "disputed_outcomes": 1_680,
        "needs_review_outcomes": 0,
        "submitted_amount": "15000.00",
        "payable_amount": "12480.00",
        "recommended_deduction": "2520.00",
        "categories": {"R1": 720, "R2": 360, "R3": 300, "R4": 180, "R5": 120},
    }
    assert sum(CATEGORY_COUNTS.values()) == 10_000
    assert all(record.status in {"payable", "disputed"} for record in records)


def test_fixture_regeneration_is_deterministic():
    first = demo_fixture()
    second = demo_fixture()
    assert first == second
    assert [category_for(i) for i in range(1, 10_001)] == [
        category_for(i) for i in range(1, 10_001)
    ]


def test_money_uses_decimal_only():
    records = demo_records()
    assert all(isinstance(record.claim.billed_amount, Decimal) for record in records)
    assert all(isinstance(record.payable_amount, Decimal) for record in records)
    assert sum((record.payable_amount for record in records), Decimal()) == Decimal("12480.00")


def test_each_dispute_rule_is_driven_by_operational_evidence():
    categories = {
        "R1": ("recontact", "customer_recontact"),
        "R2": ("human", "human_completion"),
        "R3": ("downstream", "downstream_failed"),
        "R4": ("duplicate", "duplicate_attribution"),
        "R5": ("mismatch", "account_verified"),
    }
    record = demo_fixture()[0]
    for expected_rule, (category, event_type) in categories.items():
        determination = evaluate(record.claim, list(events_for(record.claim, category)))
        assert determination.rule_id == expected_rule
        assert determination.status == "disputed"
        assert any(reference.purpose == event_type for reference in determination.evidence)


def test_recontact_boundary_after_seven_days_is_payable():
    record = demo_fixture()[2000]
    events = list(events_for(record.claim, "payable"))
    events.append(
        OperationalEvent(
            "EV-BOUNDARY",
            "acme_support",
            "ticket-boundary",
            "customer_recontact",
            record.claim.closed_at + timedelta(days=7, seconds=1),
            record.claim.customer_id,
            record.claim.outcome_id,
            {"intent": record.claim.intent},
            datetime(2026, 7, 1, 8),
        )
    )
    assert evaluate(record.claim, events).status == "payable"


def test_human_completion_boundary_at_24_hours_is_disputed():
    record = demo_fixture()[2000]
    events = list(events_for(record.claim, "payable"))
    events.append(
        OperationalEvent(
            "EV-HUMAN-BOUNDARY",
            "acme_support",
            "human-boundary",
            "human_completion",
            record.claim.closed_at + timedelta(hours=24),
            record.claim.customer_id,
            record.claim.outcome_id,
            {"action": record.claim.expected_action},
            datetime(2026, 7, 1, 8),
        )
    )
    assert evaluate(record.claim, events).rule_id == "R2"


def test_billing_period_boundaries():
    record = demo_fixture()[2000]
    at_start = replace(record.claim, closed_at=datetime(2026, 6, 1))
    before_start = replace(record.claim, closed_at=datetime(2026, 5, 31, 23, 59, 59))
    at_end = replace(record.claim, closed_at=datetime(2026, 7, 1))
    assert evaluate(at_start, list(events_for(at_start, "payable"))).status == "payable"
    assert evaluate(before_start, list(events_for(before_start, "payable"))).rule_id == "R6"
    assert evaluate(at_end, list(events_for(at_end, "payable"))).rule_id == "R6"


def test_missing_and_contradictory_evidence_need_review_without_deduction():
    missing = review_record()
    assert missing.status == "needs_review"
    assert missing.payable_amount == Decimal("0.00")
    record = demo_fixture()[2000]
    contradictory = replace(
        events_for(record.claim, "payable")[0],
        values={"contradictory": "true"},
    )
    result = evaluate(record.claim, [contradictory])
    assert result.status == "needs_review"
    assert "Contradictory" in result.reason


def test_out_004821_failed_refund_timeline_and_amounts():
    record = demo_fixture()[4820]
    assert record.claim.outcome_id == "OUT-004821"
    assert record.claim.vendor_claim == "resolved"
    assert [event.event_type for event in record.events] == [
        "ai_closed",
        "downstream_failed",
        "completion_window_expired",
        "human_refund_completed",
    ]
    result = evaluate(record.claim, list(record.events))
    assert result.status == "disputed"
    assert result.rule_id == "R3"
    assert result.claim.billed_amount == Decimal("1.50")
    assert result.payable_amount == Decimal("0.00")
    assert result.engine_version == "2026.06.1"


def test_evidence_provenance_is_complete():
    for event in demo_fixture()[4820].events:
        assert event.source_system
        assert event.source_record_id
        assert event.event_type
        assert event.timestamp
        assert event.customer_id
        assert event.outcome_id == "OUT-004821"
        assert event.values
        assert event.ingested_at
