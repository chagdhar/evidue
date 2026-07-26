from collections import defaultdict
from datetime import datetime, timedelta
from decimal import Decimal

from .models import (
    AttributedEvidence,
    DuplicateDecision,
    EvidenceAttribution,
    EvidenceReference,
    OperationalEvent,
    OutcomeClaim,
    OutcomeDetermination,
)

START = datetime(2026, 6, 1)
END = datetime(2026, 7, 1)
EVALUATED_AT = datetime(2026, 7, 1, 12)
ZERO = Decimal("0.00")

ACCOUNT_SENSITIVE_EVENTS = {
    "downstream_succeeded",
    "downstream_failed",
    "account_verified",
    "account_action_mismatch",
}
ACTION_SENSITIVE_EVENTS = {
    "downstream_succeeded",
    "downstream_failed",
    "human_completion",
    "human_material_correction",
    "human_refund_completed",
    "account_action_mismatch",
}


def normalize_intent(intent: str) -> str:
    return " ".join(intent.casefold().replace("_", " ").replace("-", " ").split())


def attribute_evidence(claim: OutcomeClaim, events: list[OperationalEvent]) -> EvidenceAttribution:
    """Classify evidence before any contract rule can inspect it."""
    direct: list[AttributedEvidence] = []
    review: list[AttributedEvidence] = []
    unrelated: list[AttributedEvidence] = []
    contradictory: list[AttributedEvidence] = []
    seen_ids: set[str] = set()
    seen_source_records: set[tuple[str, str]] = set()

    for event in events:
        source_key = (event.source_system, event.source_record_id)
        if event.id in seen_ids or source_key in seen_source_records:
            review.append(
                AttributedEvidence(
                    event,
                    "requires_review",
                    "Duplicated evidence record",
                )
            )
            continue
        seen_ids.add(event.id)
        seen_source_records.add(source_key)

        if event.outcome_id is None:
            review.append(
                AttributedEvidence(
                    event,
                    "requires_review",
                    "Evidence has no outcome identifier",
                )
            )
            continue
        if event.customer_id != claim.customer_id or event.outcome_id != claim.outcome_id:
            unrelated.append(
                AttributedEvidence(
                    event,
                    "unrelated",
                    "Evidence customer or outcome does not match the claim",
                )
            )
            continue
        if event.values.get("contradictory") == "true":
            contradictory.append(
                AttributedEvidence(
                    event,
                    "contradictory",
                    "Directly matched evidence is explicitly contradictory",
                )
            )
            continue
        if (
            event.event_type in ACCOUNT_SENSITIVE_EVENTS
            and event.values.get("account_id") != claim.account_id
        ):
            review.append(
                AttributedEvidence(
                    event,
                    "requires_review",
                    "Account-sensitive evidence does not match the claim account",
                )
            )
            continue
        if (
            event.event_type in ACTION_SENSITIVE_EVENTS
            and event.values.get("action") != claim.expected_action
        ):
            review.append(
                AttributedEvidence(
                    event,
                    "requires_review",
                    "Action-sensitive evidence does not match the expected action",
                )
            )
            continue
        direct.append(
            AttributedEvidence(event, "directly_matched", "Customer and outcome match the claim")
        )

    direct_terminal = {
        item.event.event_type
        for item in direct
        if item.event.event_type in {"downstream_succeeded", "downstream_failed"}
    }
    if direct_terminal == {"downstream_succeeded", "downstream_failed"}:
        retained: list[AttributedEvidence] = []
        for item in direct:
            if item.event.event_type in direct_terminal:
                contradictory.append(
                    AttributedEvidence(
                        item.event,
                        "contradictory",
                        "Directly matched downstream events report conflicting terminal results",
                    )
                )
            else:
                retained.append(item)
        direct = retained

    return EvidenceAttribution(
        directly_matched=tuple(direct),
        requires_review=tuple(review),
        unrelated=tuple(unrelated),
        contradictory=tuple(contradictory),
    )


def _references(
    events: list[OperationalEvent], purpose: str | None = None
) -> tuple[EvidenceReference, ...]:
    return tuple(
        EvidenceReference(event.id, purpose or event.event_type, event.outcome_id)
        for event in events
    )


def _result(
    claim: OutcomeClaim,
    status: str,
    reason: str,
    rule_id: str | None,
    evidence: list[OperationalEvent],
    duplicate_decision: DuplicateDecision | None = None,
) -> OutcomeDetermination:
    payable = claim.billed_amount if status == "payable" else ZERO
    disputed = claim.billed_amount if status == "disputed" else ZERO
    review = claim.billed_amount if status == "needs_review" else ZERO
    return OutcomeDetermination(
        claim=claim,
        status=status,  # type: ignore[arg-type]
        reason=reason,
        rule_id=rule_id,
        evidence=_references(evidence),
        confirmed_payable_amount=payable,
        confirmed_disputed_amount=disputed,
        needs_review_amount=review,
        evaluated_at=EVALUATED_AT,
        duplicate_decision=duplicate_decision,
    )


def _duplicate_decisions(claims: list[OutcomeClaim]) -> dict[str, DuplicateDecision]:
    groups: dict[tuple[str, str], list[OutcomeClaim]] = defaultdict(list)
    for claim in claims:
        groups[(claim.customer_id, normalize_intent(claim.intent))].append(claim)

    decisions: dict[str, DuplicateDecision] = {}
    window = timedelta(hours=24)
    for grouped_claims in groups.values():
        ordered = sorted(grouped_claims, key=lambda item: (item.closed_at, item.outcome_id))
        winner = ordered[0]
        for candidate in ordered[1:]:
            if candidate.closed_at <= winner.closed_at + window:
                decisions[candidate.outcome_id] = DuplicateDecision(
                    winner_outcome_id=winner.outcome_id,
                    duplicate_outcome_id=candidate.outcome_id,
                    winner_closed_at=winner.closed_at,
                    duplicate_closed_at=candidate.closed_at,
                )
            else:
                winner = candidate
    return decisions


def evaluate(
    claim: OutcomeClaim,
    events: list[OperationalEvent],
    duplicate_decision: DuplicateDecision | None = None,
    winner_events: list[OperationalEvent] | None = None,
) -> OutcomeDetermination:
    """Evaluate one attributed claim with deterministic, ordered contract rules."""
    attribution = attribute_evidence(claim, events)
    direct = [item.event for item in attribution.directly_matched]

    if not claim.outcome_id or not claim.customer_id or not claim.account_id:
        return _result(
            claim,
            "needs_review",
            "Missing required claim identifiers",
            "R7",
            [],
        )
    if attribution.contradictory:
        return _result(
            claim,
            "needs_review",
            "; ".join(item.reason for item in attribution.contradictory),
            "R7",
            [item.event for item in attribution.contradictory],
        )
    if attribution.requires_review:
        return _result(
            claim,
            "needs_review",
            "; ".join(item.reason for item in attribution.requires_review),
            "R7",
            [item.event for item in attribution.requires_review],
        )

    closure = next((event for event in direct if event.event_type == "ai_closed"), None)
    if closure is None:
        return _result(
            claim,
            "needs_review",
            "Missing directly attributed AI closure evidence",
            "R7",
            [],
        )
    if not START <= claim.closed_at < END:
        return _result(
            claim,
            "disputed",
            "Outcome falls outside the invoice billing period",
            "R6",
            [closure],
        )

    recontact_limit = claim.closed_at + timedelta(days=7)
    recontact = next(
        (
            event
            for event in direct
            if event.event_type == "customer_recontact"
            and normalize_intent(event.values.get("intent", "")) == normalize_intent(claim.intent)
            and claim.closed_at < event.timestamp <= recontact_limit
        ),
        None,
    )
    if recontact:
        return _result(
            claim,
            "disputed",
            "Same-intent recontact within seven calendar days",
            "R1",
            [closure, recontact],
        )

    human_limit = claim.closed_at + timedelta(hours=24)
    human = next(
        (
            event
            for event in direct
            if event.event_type in {"human_completion", "human_material_correction"}
            and claim.closed_at < event.timestamp <= human_limit
        ),
        None,
    )
    if human:
        return _result(
            claim,
            "disputed",
            "Human completed or materially corrected the work within 24 hours",
            "R2",
            [closure, human],
        )

    action_events = [
        event
        for event in direct
        if event.event_type in {"downstream_succeeded", "downstream_failed"}
    ]
    if not action_events:
        return _result(
            claim,
            "needs_review",
            "Missing directly attributed evidence for the promised downstream action",
            "R7",
            [closure],
        )
    action_limit = claim.closed_at + timedelta(hours=2)
    failed = next(
        (event for event in action_events if event.event_type == "downstream_failed"),
        None,
    )
    succeeded = next(
        (
            event
            for event in action_events
            if event.event_type == "downstream_succeeded"
            and claim.closed_at <= event.timestamp <= action_limit
        ),
        None,
    )
    if failed or not succeeded:
        decisive = [closure]
        if failed:
            decisive.append(failed)
        decisive.extend(event for event in direct if event.event_type == "human_refund_completed")
        return _result(
            claim,
            "disputed",
            "Promised downstream action failed within the required two-hour window",
            "R3",
            decisive,
        )

    if duplicate_decision:
        winner_closure = next(
            (
                event
                for event in winner_events or []
                if event.event_type == "ai_closed"
                and event.outcome_id == duplicate_decision.winner_outcome_id
            ),
            None,
        )
        duplicate_evidence = [event for event in [winner_closure, closure] if event]
        duplicate_evidence.extend(
            event for event in direct if event.event_type == "duplicate_attribution"
        )
        return _result(
            claim,
            "disputed",
            (
                f"{claim.outcome_id} duplicates winning outcome "
                f"{duplicate_decision.winner_outcome_id} in the 24-hour attribution window"
            ),
            "R4",
            duplicate_evidence,
            duplicate_decision,
        )

    mismatch = next(
        (
            event
            for event in direct
            if event.event_type == "account_action_mismatch"
            and (
                event.values.get("observed_account_id") != claim.account_id
                or event.values.get("observed_action") != claim.expected_action
            )
        ),
        None,
    )
    if mismatch:
        return _result(
            claim,
            "disputed",
            "Customer account or expected action did not match operational evidence",
            "R5",
            [mismatch],
        )

    return _result(
        claim,
        "payable",
        "All applicable contractual rules passed",
        None,
        [closure, succeeded],
    )


def reconcile(
    claim_evidence: list[tuple[OutcomeClaim, list[OperationalEvent]]],
) -> list[OutcomeDetermination]:
    decisions = _duplicate_decisions([claim for claim, _ in claim_evidence])
    events_by_outcome = {claim.outcome_id: events for claim, events in claim_evidence}
    return [
        evaluate(
            claim,
            events,
            decisions.get(claim.outcome_id),
            events_by_outcome.get(decisions[claim.outcome_id].winner_outcome_id, [])
            if claim.outcome_id in decisions
            else None,
        )
        for claim, events in claim_evidence
    ]


def summarize(items: list[OutcomeDetermination]) -> dict[str, object]:
    submitted = sum((item.claim.billed_amount for item in items), Decimal())
    payable = sum((item.confirmed_payable_amount for item in items), Decimal())
    disputed = sum((item.confirmed_disputed_amount for item in items), Decimal())
    review = sum((item.needs_review_amount for item in items), Decimal())
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
        "submitted_amount": f"{submitted:.2f}",
        "confirmed_payable_amount": f"{payable:.2f}",
        "recommended_deduction": f"{disputed:.2f}",
        "needs_review_amount": f"{review:.2f}",
        "categories": categories,
    }
