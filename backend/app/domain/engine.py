from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta
from decimal import Decimal
from functools import lru_cache
from typing import Any

from .models import (
    AttributedEvidence,
    DuplicateDecision,
    EvidenceAttribution,
    EvidenceReference,
    ExecutableRule,
    OperationalEvent,
    OutcomeClaim,
    OutcomeDetermination,
    RuleProgram,
)

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


@lru_cache(maxsize=1)
def _default_program() -> RuleProgram:
    # Lazy import avoids a models/compiler import cycle and loads the immutable,
    # validated, human-approved recorded proposal only once per process.
    from app.contracts.compiler import recorded_rule_program

    return recorded_rule_program()


def normalize_intent(intent: str) -> str:
    return " ".join(intent.casefold().replace("_", " ").replace("-", " ").split())


def _is_prohibited_event(
    event: OperationalEvent,
    *,
    event_types: set[str],
    anchor: datetime,
    limit: datetime,
    compare_event: object | None,
    compare_claim: object | None,
    normalizer: object | None,
    claim: OutcomeClaim,
) -> bool:
    if event.event_type not in event_types or not (anchor < event.timestamp <= limit):
        return False
    if compare_event and compare_claim:
        return _normalize(
            event.values.get(str(compare_event), ""),
            normalizer,
        ) == _normalize(
            _claim_value(claim, str(compare_claim)),
            normalizer,
        )
    return True


def _has_field_mismatch(
    event: OperationalEvent,
    *,
    event_type: str,
    comparisons: list[dict[str, object]],
    claim: OutcomeClaim,
) -> bool:
    if event.event_type != event_type:
        return False
    return any(
        event.values.get(str(comparison["event_field"]))
        != str(_claim_value(claim, str(comparison["claim_field"])))
        for comparison in comparisons
    )


def attribute_evidence(claim: OutcomeClaim, events: list[OperationalEvent]) -> EvidenceAttribution:
    """Classify source evidence before any approved contract rule can inspect it."""
    direct: list[AttributedEvidence] = []
    review: list[AttributedEvidence] = []
    unrelated: list[AttributedEvidence] = []
    contradictory: list[AttributedEvidence] = []
    seen_ids: set[str] = set()
    seen_source_records: set[tuple[str, str]] = set()

    for event in events:
        source_key = (event.source_system, event.source_record_id)
        if event.id in seen_ids or source_key in seen_source_records:
            review.append(AttributedEvidence(event, "requires_review", "Duplicated evidence record"))
            continue
        seen_ids.add(event.id)
        seen_source_records.add(source_key)

        if event.outcome_id is None:
            review.append(
                AttributedEvidence(event, "requires_review", "Evidence has no outcome identifier")
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
    *,
    program: RuleProgram,
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
        engine_version=program.engine_version,
    )


def _window(parameters: dict[str, object]) -> timedelta:
    value = int(parameters["window_value"])
    unit = str(parameters["window_unit"])
    return timedelta(days=value) if unit == "days" else timedelta(hours=value)


def _claim_value(claim: OutcomeClaim, field: str) -> Any:
    if not hasattr(claim, field):
        raise ValueError(f"Approved rule references unsupported claim field: {field}")
    return getattr(claim, field)


def _normalize(value: object, normalizer: object | None) -> object:
    if normalizer == "intent":
        return normalize_intent(str(value))
    return value


def _review_rule(program: RuleProgram) -> ExecutableRule:
    return next(rule for rule in program.rules if rule.consequence == "needs_review")


def _rule_failure(
    claim: OutcomeClaim,
    rule: ExecutableRule,
    reason: str,
    evidence: list[OperationalEvent],
    program: RuleProgram,
) -> OutcomeDetermination:
    return _result(
        claim,
        rule.consequence,
        reason,
        rule.id,
        evidence,
        program=program,
    )


def _duplicate_rule(program: RuleProgram) -> ExecutableRule | None:
    return next((rule for rule in program.rules if rule.operation == "unique_first_claim_within"), None)


def _duplicate_decisions(
    provisional: list[OutcomeDetermination], program: RuleProgram
) -> dict[str, DuplicateDecision]:
    """Apply the approved uniqueness operation only after all per-claim rules pass."""
    rule = _duplicate_rule(program)
    if rule is None:
        return {}
    parameters = rule.parameters
    group_fields = [str(item) for item in parameters["group_by"]]  # type: ignore[index]
    normalizers = parameters.get("normalizers", {})
    if not isinstance(normalizers, dict):
        normalizers = {}
    order_fields = [str(item) for item in parameters["order_by"]]  # type: ignore[index]
    window = _window(parameters)

    groups: dict[tuple[object, ...], list[OutcomeClaim]] = defaultdict(list)
    for determination in provisional:
        if determination.status != "payable":
            continue
        claim = determination.claim
        key = tuple(
            _normalize(_claim_value(claim, field), normalizers.get(field))
            for field in group_fields
        )
        groups[key].append(claim)

    decisions: dict[str, DuplicateDecision] = {}
    for grouped_claims in groups.values():
        ordered = sorted(
            grouped_claims,
            key=lambda item: tuple(_claim_value(item, field) for field in order_fields),
        )
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
    *,
    program: RuleProgram | None = None,
) -> OutcomeDetermination:
    """Interpret one immutable approved rule program; no LLM runs here."""
    approved = program or _default_program()
    attribution = attribute_evidence(claim, events)
    direct = [item.event for item in attribution.directly_matched]
    closure: OperationalEvent | None = None
    success: OperationalEvent | None = None

    for rule in sorted(approved.rules, key=lambda item: item.priority):
        p = rule.parameters
        operation = rule.operation

        if operation == "unique_first_claim_within":
            continue

        if operation == "validate_evidence_envelope":
            missing = [
                str(field)
                for field in p["required_claim_fields"]  # type: ignore[index]
                if not _claim_value(claim, str(field))
            ]
            if missing:
                return _rule_failure(
                    claim,
                    rule,
                    "Missing required claim identifiers",
                    [],
                    approved,
                )
            if attribution.contradictory:
                return _rule_failure(
                    claim,
                    rule,
                    "; ".join(item.reason for item in attribution.contradictory),
                    [item.event for item in attribution.contradictory],
                    approved,
                )
            if attribution.requires_review:
                return _rule_failure(
                    claim,
                    rule,
                    "; ".join(item.reason for item in attribution.requires_review),
                    [item.event for item in attribution.requires_review],
                    approved,
                )
            closure_type = str(p["closure_event_type"])
            closure = next((event for event in direct if event.event_type == closure_type), None)
            if closure is None:
                return _rule_failure(
                    claim,
                    rule,
                    "Missing directly attributed AI closure evidence",
                    [],
                    approved,
                )
            continue

        if operation == "claim_datetime_in_range":
            value = _claim_value(claim, str(p["claim_field"]))
            start = datetime.fromisoformat(str(p["start"]))
            end = datetime.fromisoformat(str(p["end_exclusive"]))
            if not start <= value < end:
                return _rule_failure(
                    claim,
                    rule,
                    "Outcome falls outside the invoice billing period",
                    [closure] if closure else [],
                    approved,
                )
            continue

        if operation == "prohibit_event_within":
            anchor = _claim_value(claim, str(p["anchor_claim_field"]))
            limit = anchor + _window(p)
            event_types = {str(item) for item in p["event_types"]}  # type: ignore[index]
            compare_event = p.get("compare_event_value")
            compare_claim = p.get("compare_claim_field")
            normalizer = p.get("normalization")

            found = next(
                (
                    event
                    for event in direct
                    if _is_prohibited_event(
                        event,
                        event_types=event_types,
                        anchor=anchor,
                        limit=limit,
                        compare_event=compare_event,
                        compare_claim=compare_claim,
                        normalizer=normalizer,
                        claim=claim,
                    )
                ),
                None,
            )
            if found:
                reason = (
                    "Same-intent recontact within seven calendar days"
                    if rule.id == "R1"
                    else "Human completed or materially corrected the work within 24 hours"
                )
                return _rule_failure(
                    claim,
                    rule,
                    reason,
                    [item for item in [closure, found] if item],
                    approved,
                )
            continue

        if operation == "require_success_event_within":
            success_type = str(p["success_event_type"])
            failure_type = str(p["failure_event_type"])
            action_events = [
                event for event in direct if event.event_type in {success_type, failure_type}
            ]
            if not action_events:
                review_rule = _review_rule(approved)
                return _rule_failure(
                    claim,
                    review_rule,
                    "Missing directly attributed evidence for the promised downstream action",
                    [closure] if closure else [],
                    approved,
                )
            anchor = _claim_value(claim, str(p["anchor_claim_field"]))
            limit = anchor + _window(p)
            failed = next(
                (event for event in action_events if event.event_type == failure_type), None
            )
            success = next(
                (
                    event
                    for event in action_events
                    if event.event_type == success_type and anchor <= event.timestamp <= limit
                ),
                None,
            )
            if failed or not success:
                decisive = [closure] if closure else []
                if failed:
                    decisive.append(failed)
                support_types = {str(item) for item in p.get("supporting_event_types", [])}
                decisive.extend(event for event in direct if event.event_type in support_types)
                return _rule_failure(
                    claim,
                    rule,
                    "Promised downstream action failed within the required two-hour window",
                    decisive,
                    approved,
                )
            continue

        if operation == "prohibit_field_mismatch_event":
            event_type = str(p["event_type"])
            comparisons = p["comparisons"]

            typed_comparisons = [
                comparison
                for comparison in comparisons
                if isinstance(comparison, dict)
            ]
            found = next(
                (
                    event
                    for event in direct
                    if _has_field_mismatch(
                        event,
                        event_type=event_type,
                        comparisons=typed_comparisons,
                        claim=claim,
                    )
                ),
                None,
            )
            if found:
                return _rule_failure(
                    claim,
                    rule,
                    "Customer account or expected action did not match operational evidence",
                    [found],
                    approved,
                )
            continue

        raise ValueError(f"Unsupported approved operation: {operation}")

    duplicate_rule = _duplicate_rule(approved)
    if duplicate_decision and duplicate_rule:
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
            duplicate_rule.consequence,
            (
                f"{claim.outcome_id} duplicates winning outcome "
                f"{duplicate_decision.winner_outcome_id} in the 24-hour attribution window"
            ),
            duplicate_rule.id,
            duplicate_evidence,
            program=approved,
            duplicate_decision=duplicate_decision,
        )

    return _result(
        claim,
        "payable",
        "All applicable contractual rules passed",
        None,
        [event for event in [closure, success] if event],
        program=approved,
    )


def reconcile(
    claim_evidence: list[tuple[OutcomeClaim, list[OperationalEvent]]],
    *,
    program: RuleProgram | None = None,
) -> list[OutcomeDetermination]:
    approved = program or _default_program()
    provisional = [evaluate(claim, events, program=approved) for claim, events in claim_evidence]
    decisions = _duplicate_decisions(provisional, approved)
    events_by_outcome = {claim.outcome_id: events for claim, events in claim_evidence}
    final: list[OutcomeDetermination] = []
    for determination, (claim, events) in zip(provisional, claim_evidence, strict=True):
        decision = decisions.get(claim.outcome_id)
        if decision is None:
            final.append(determination)
            continue
        final.append(
            evaluate(
                claim,
                events,
                decision,
                events_by_outcome[decision.winner_outcome_id],
                program=approved,
            )
        )
    return final


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
