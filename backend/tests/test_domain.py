from dataclasses import replace
from datetime import datetime, timedelta
from decimal import Decimal

from app.domain.engine import (
    attribute_evidence,
    evaluate,
    reconcile,
    summarize,
)
from app.domain.models import OperationalEvent
from app.fixtures.demo import (
    CATEGORY_COUNTS,
    demo_fixture,
    demo_records,
    events_for,
    review_record,
)


def _event(record, category: str, event_type: str) -> OperationalEvent:
    return next(
        event for event in events_for(record.claim, category) if event.event_type == event_type
    )


def _payable_record():
    return demo_fixture()[2000]


def _claim_with_events(
    outcome_id: str,
    customer_id: str,
    closed_at: datetime,
    category: str = "payable",
):
    claim = replace(
        _payable_record().claim,
        outcome_id=outcome_id,
        customer_id=customer_id,
        closed_at=closed_at,
    )
    return claim, list(events_for(claim, category))


def test_exact_demo_totals_and_mutually_exclusive_categories():
    records = demo_records()
    assert summarize(records) == {
        "claimed_outcomes": 10_000,
        "payable_outcomes": 8_320,
        "disputed_outcomes": 1_680,
        "needs_review_outcomes": 0,
        "submitted_amount": "15000.00",
        "confirmed_payable_amount": "12480.00",
        "recommended_deduction": "2520.00",
        "needs_review_amount": "0.00",
        "categories": {"R1": 720, "R2": 360, "R3": 300, "R4": 180, "R5": 120},
    }
    assert sum(CATEGORY_COUNTS.values()) == 10_000
    assert all(record.status in {"payable", "disputed"} for record in records)


def test_fixture_regeneration_is_deterministic():
    assert demo_fixture() == demo_fixture()
    assert demo_records() == demo_records()


def test_money_uses_decimal_and_explicit_financial_buckets():
    records = demo_records()
    assert all(isinstance(item.claim.billed_amount, Decimal) for item in records)
    assert all(isinstance(item.confirmed_payable_amount, Decimal) for item in records)
    assert all(isinstance(item.confirmed_disputed_amount, Decimal) for item in records)
    assert all(isinstance(item.needs_review_amount, Decimal) for item in records)
    assert sum((item.confirmed_payable_amount for item in records), Decimal()) == Decimal(
        "12480.00"
    )
    assert sum((item.confirmed_disputed_amount for item in records), Decimal()) == Decimal(
        "2520.00"
    )


def test_ambiguous_evidence_is_review_not_a_recommended_deduction():
    result = review_record()
    assert result.status == "needs_review"
    assert result.confirmed_payable_amount == Decimal("0.00")
    assert result.confirmed_disputed_amount == Decimal("0.00")
    assert result.needs_review_amount == Decimal("1.50")
    assert summarize([result]) == {
        "claimed_outcomes": 1,
        "payable_outcomes": 0,
        "disputed_outcomes": 0,
        "needs_review_outcomes": 1,
        "submitted_amount": "1.50",
        "confirmed_payable_amount": "0.00",
        "recommended_deduction": "0.00",
        "needs_review_amount": "1.50",
        "categories": {},
    }


def test_same_intent_different_customer_is_unrelated_and_inert():
    record = _payable_record()
    unrelated = replace(
        _event(record, "recontact", "customer_recontact"),
        id="EV-OTHER-CUSTOMER",
        source_record_id="other-customer",
        customer_id="CUST-OTHER",
    )
    events = list(events_for(record.claim, "payable")) + [unrelated]
    attribution = attribute_evidence(record.claim, events)
    assert [item.event.id for item in attribution.unrelated] == ["EV-OTHER-CUSTOMER"]
    assert evaluate(record.claim, events).status == "payable"


def test_same_customer_different_outcome_is_unrelated_and_inert():
    record = _payable_record()
    unrelated = replace(
        _event(record, "recontact", "customer_recontact"),
        id="EV-OTHER-OUTCOME",
        source_record_id="other-outcome",
        outcome_id="OUT-OTHER",
    )
    events = list(events_for(record.claim, "payable")) + [unrelated]
    attribution = attribute_evidence(record.claim, events)
    assert len(attribution.unrelated) == 1
    assert evaluate(record.claim, events).status == "payable"


def test_same_outcome_wrong_customer_is_unrelated_and_inert():
    record = _payable_record()
    unrelated = replace(
        _event(record, "recontact", "customer_recontact"),
        id="EV-WRONG-CUSTOMER",
        source_record_id="wrong-customer",
        customer_id="CUST-WRONG",
        outcome_id=record.claim.outcome_id,
    )
    events = list(events_for(record.claim, "payable")) + [unrelated]
    attribution = attribute_evidence(record.claim, events)
    assert len(attribution.unrelated) == 1
    assert evaluate(record.claim, events).status == "payable"


def test_correct_action_wrong_account_requires_review():
    record = _payable_record()
    closure = _event(record, "payable", "ai_closed")
    wrong_account = replace(
        _event(record, "payable", "downstream_succeeded"),
        values={"account_id": "ACC-WRONG", "action": record.claim.expected_action},
    )
    attribution = attribute_evidence(record.claim, [closure, wrong_account])
    assert len(attribution.requires_review) == 1
    result = evaluate(record.claim, [closure, wrong_account])
    assert result.status == "needs_review"
    assert result.needs_review_amount == Decimal("1.50")


def test_correct_account_wrong_action_requires_review():
    record = _payable_record()
    closure = _event(record, "payable", "ai_closed")
    wrong_action = replace(
        _event(record, "payable", "downstream_succeeded"),
        values={"account_id": record.claim.account_id, "action": "wrong_action"},
    )
    attribution = attribute_evidence(record.claim, [closure, wrong_action])
    assert len(attribution.requires_review) == 1
    assert evaluate(record.claim, [closure, wrong_action]).status == "needs_review"


def test_event_without_outcome_id_requires_review():
    record = _payable_record()
    unidentified = replace(
        _event(record, "payable", "downstream_succeeded"),
        id="EV-NO-OUTCOME",
        source_record_id="no-outcome",
        outcome_id=None,
    )
    events = [_event(record, "payable", "ai_closed"), unidentified]
    attribution = attribute_evidence(record.claim, events)
    assert len(attribution.requires_review) == 1
    assert evaluate(record.claim, events).status == "needs_review"


def test_duplicated_evidence_record_requires_review_and_is_not_counted_twice():
    record = _payable_record()
    closure, success = events_for(record.claim, "payable")
    attribution = attribute_evidence(record.claim, [closure, success, success])
    assert len(attribution.directly_matched) == 2
    assert len(attribution.requires_review) == 1
    result = evaluate(record.claim, [closure, success, success])
    assert result.status == "needs_review"
    assert len(result.evidence) == 1


def test_contradictory_directly_matched_events_require_review():
    record = _payable_record()
    closure, success = events_for(record.claim, "payable")
    failed = replace(
        success,
        id="EV-CONTRADICTORY-FAILURE",
        source_record_id="contradictory-failure",
        event_type="downstream_failed",
    )
    attribution = attribute_evidence(record.claim, [closure, success, failed])
    assert len(attribution.contradictory) == 2
    result = evaluate(record.claim, [closure, success, failed])
    assert result.status == "needs_review"
    assert result.confirmed_disputed_amount == Decimal("0.00")
    assert result.needs_review_amount == Decimal("1.50")


def test_direct_attribution_keeps_only_exactly_matched_evidence():
    record = _payable_record()
    direct = list(events_for(record.claim, "payable"))
    unrelated = replace(
        direct[1],
        id="EV-UNRELATED",
        source_record_id="unrelated",
        customer_id="CUST-UNRELATED",
    )
    attribution = attribute_evidence(record.claim, direct + [unrelated])
    assert [item.classification for item in attribution.directly_matched] == [
        "directly_matched",
        "directly_matched",
    ]
    assert [item.classification for item in attribution.unrelated] == ["unrelated"]
    assert not attribution.requires_review
    assert not attribution.contradictory


def test_duplicate_detection_uses_claim_context_and_deterministic_winner():
    winner_record = _payable_record()
    loser_claim = replace(
        winner_record.claim,
        outcome_id="OUT-DUPLICATE",
        intent=f" {winner_record.claim.intent.replace('_', '-').title()} ",
        closed_at=winner_record.claim.closed_at + timedelta(hours=23),
    )
    loser_events = list(events_for(loser_claim, "payable"))
    results = reconcile(
        [
            (loser_claim, loser_events),
            (winner_record.claim, list(events_for(winner_record.claim, "payable"))),
        ]
    )
    by_id = {item.claim.outcome_id: item for item in results}
    assert by_id[winner_record.claim.outcome_id].status == "payable"
    duplicate = by_id["OUT-DUPLICATE"]
    assert duplicate.rule_id == "R4"
    assert duplicate.duplicate_decision is not None
    assert duplicate.duplicate_decision.winner_outcome_id == winner_record.claim.outcome_id
    assert {reference.outcome_id for reference in duplicate.evidence} == {
        winner_record.claim.outcome_id,
        loser_claim.outcome_id,
    }
    assert winner_record.claim.outcome_id in duplicate.reason
    assert loser_claim.outcome_id in duplicate.reason


def test_failed_claim_cannot_win_duplicate_attribution():
    at = datetime(2026, 6, 10, 9)
    failed = _claim_with_events("OUT-R3-FIRST", "CUST-PRECEDENCE-1", at, "downstream")
    valid = _claim_with_events(
        "OUT-VALID-SECOND",
        "CUST-PRECEDENCE-1",
        at + timedelta(hours=1),
    )

    by_id = {item.claim.outcome_id: item for item in reconcile([failed, valid])}

    assert by_id["OUT-R3-FIRST"].rule_id == "R3"
    assert by_id["OUT-VALID-SECOND"].status == "payable"
    assert by_id["OUT-VALID-SECOND"].duplicate_decision is None


def test_needs_review_claim_cannot_win_duplicate_attribution():
    at = datetime(2026, 6, 10, 9)
    review_claim, review_events = _claim_with_events(
        "OUT-REVIEW-FIRST",
        "CUST-PRECEDENCE-2",
        at,
    )
    valid = _claim_with_events(
        "OUT-VALID-SECOND",
        "CUST-PRECEDENCE-2",
        at + timedelta(hours=1),
    )

    by_id = {
        item.claim.outcome_id: item
        for item in reconcile([(review_claim, review_events[:1]), valid])
    }

    assert by_id["OUT-REVIEW-FIRST"].status == "needs_review"
    assert by_id["OUT-VALID-SECOND"].status == "payable"
    assert by_id["OUT-VALID-SECOND"].duplicate_decision is None


def test_out_of_period_claim_cannot_win_duplicate_attribution():
    outside = _claim_with_events(
        "OUT-R6-FIRST",
        "CUST-PRECEDENCE-3",
        datetime(2026, 5, 31, 23, 30),
    )
    valid = _claim_with_events(
        "OUT-VALID-SECOND",
        "CUST-PRECEDENCE-3",
        datetime(2026, 6, 1, 0, 30),
    )

    by_id = {item.claim.outcome_id: item for item in reconcile([outside, valid])}

    assert by_id["OUT-R6-FIRST"].rule_id == "R6"
    assert by_id["OUT-VALID-SECOND"].status == "payable"
    assert by_id["OUT-VALID-SECOND"].duplicate_decision is None


def test_two_otherwise_payable_claims_make_only_the_later_claim_r4():
    at = datetime(2026, 6, 10, 9)
    first = _claim_with_events("OUT-PAYABLE-1", "CUST-PRECEDENCE-4", at)
    second = _claim_with_events(
        "OUT-PAYABLE-2",
        "CUST-PRECEDENCE-4",
        at + timedelta(hours=1),
    )

    by_id = {item.claim.outcome_id: item for item in reconcile([second, first])}

    assert by_id["OUT-PAYABLE-1"].status == "payable"
    duplicate = by_id["OUT-PAYABLE-2"]
    assert duplicate.rule_id == "R4"
    assert duplicate.duplicate_decision is not None
    assert duplicate.duplicate_decision.winner_outcome_id == "OUT-PAYABLE-1"
    assert {reference.outcome_id for reference in duplicate.evidence} == {
        "OUT-PAYABLE-1",
        "OUT-PAYABLE-2",
    }


def test_three_otherwise_payable_claims_in_one_window_make_later_two_r4():
    at = datetime(2026, 6, 10, 9)
    claims = [
        _claim_with_events("OUT-PAYABLE-1", "CUST-PRECEDENCE-5", at),
        _claim_with_events(
            "OUT-PAYABLE-2",
            "CUST-PRECEDENCE-5",
            at + timedelta(hours=8),
        ),
        _claim_with_events(
            "OUT-PAYABLE-3",
            "CUST-PRECEDENCE-5",
            at + timedelta(hours=23),
        ),
    ]

    by_id = {item.claim.outcome_id: item for item in reconcile(claims)}

    assert by_id["OUT-PAYABLE-1"].status == "payable"
    assert by_id["OUT-PAYABLE-2"].rule_id == "R4"
    assert by_id["OUT-PAYABLE-3"].rule_id == "R4"
    assert {
        by_id[outcome_id].duplicate_decision.winner_outcome_id
        for outcome_id in ("OUT-PAYABLE-2", "OUT-PAYABLE-3")
        if by_id[outcome_id].duplicate_decision
    } == {"OUT-PAYABLE-1"}


def test_otherwise_payable_claims_more_than_24_hours_apart_are_both_payable():
    at = datetime(2026, 6, 10, 9)
    first = _claim_with_events("OUT-PAYABLE-1", "CUST-PRECEDENCE-6", at)
    second = _claim_with_events(
        "OUT-PAYABLE-2",
        "CUST-PRECEDENCE-6",
        at + timedelta(hours=24, seconds=1),
    )

    results = reconcile([first, second])

    assert [item.status for item in results] == ["payable", "payable"]
    assert all(item.duplicate_decision is None for item in results)


def test_duplicate_timestamp_tie_is_broken_deterministically_by_outcome_id():
    at = datetime(2026, 6, 10, 9)
    higher = _claim_with_events("OUT-TIE-002", "CUST-PRECEDENCE-7", at)
    lower = _claim_with_events("OUT-TIE-001", "CUST-PRECEDENCE-7", at)

    by_id = {item.claim.outcome_id: item for item in reconcile([higher, lower])}

    assert by_id["OUT-TIE-001"].status == "payable"
    assert by_id["OUT-TIE-002"].rule_id == "R4"
    assert by_id["OUT-TIE-002"].duplicate_decision is not None
    assert by_id["OUT-TIE-002"].duplicate_decision.winner_outcome_id == "OUT-TIE-001"


def test_duplicate_label_alone_cannot_create_a_duplicate_determination():
    record = _payable_record()
    result = evaluate(record.claim, list(events_for(record.claim, "duplicate")))
    assert result.status == "payable"
    assert result.rule_id is None


def test_fixture_preserves_180_contextual_duplicates():
    duplicates = [item for item in demo_records() if item.rule_id == "R4"]
    assert len(duplicates) == 180
    assert all(item.duplicate_decision is not None for item in duplicates)
    assert all(
        item.duplicate_decision.winner_outcome_id != item.claim.outcome_id
        for item in duplicates
        if item.duplicate_decision
    )


def test_decisive_rule_references_only_evidence_it_used():
    record = demo_fixture()[0]
    recontact = evaluate(record.claim, list(record.events))
    assert [reference.purpose for reference in recontact.evidence] == [
        "ai_closed",
        "customer_recontact",
    ]

    payable_record = _payable_record()
    payable = evaluate(payable_record.claim, list(payable_record.events))
    assert [reference.purpose for reference in payable.evidence] == [
        "ai_closed",
        "downstream_succeeded",
    ]


def test_recontact_and_human_boundaries():
    record = _payable_record()
    events = list(events_for(record.claim, "payable"))
    events.append(
        replace(
            _event(record, "recontact", "customer_recontact"),
            id="EV-BOUNDARY",
            source_record_id="boundary",
            timestamp=record.claim.closed_at + timedelta(days=7, seconds=1),
        )
    )
    assert evaluate(record.claim, events).status == "payable"

    human = replace(
        _event(record, "human", "human_completion"),
        timestamp=record.claim.closed_at + timedelta(hours=24),
    )
    assert (
        evaluate(
            record.claim,
            [_event(record, "payable", "ai_closed"), human],
        ).rule_id
        == "R2"
    )


def test_billing_period_boundaries():
    record = _payable_record()
    for timestamp, expected in [
        (datetime(2026, 6, 1), "payable"),
        (datetime(2026, 5, 31, 23, 59, 59), "disputed"),
        (datetime(2026, 7, 1), "disputed"),
    ]:
        claim = replace(record.claim, closed_at=timestamp)
        result = evaluate(claim, list(events_for(claim, "payable")))
        assert result.status == expected
        if expected == "disputed":
            assert result.rule_id == "R6"


def test_out_004821_uses_operational_evidence_and_computed_deadline_separately():
    record = demo_fixture()[4820]
    assert [event.event_type for event in record.events] == [
        "ai_closed",
        "downstream_failed",
        "human_refund_completed",
    ]
    result = evaluate(record.claim, list(record.events))
    assert result.status == "disputed"
    assert result.rule_id == "R3"
    assert result.confirmed_payable_amount == Decimal("0.00")
    assert result.confirmed_disputed_amount == Decimal("1.50")
    assert result.needs_review_amount == Decimal("0.00")
    assert [reference.purpose for reference in result.evidence] == [
        "ai_closed",
        "downstream_failed",
        "human_refund_completed",
    ]
    assert "completion_window_expired" not in {reference.purpose for reference in result.evidence}


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
