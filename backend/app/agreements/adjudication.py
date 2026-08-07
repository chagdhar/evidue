"""Contract-general adjudication over approved Agreement IR.

This module is the financial-authority evaluator for the product path.  It has
no knowledge of demo rule IDs or contract-specific operations: decisions are
derived only from the typed AIR expression/norm/settlement graph plus normalized
claims and evidence.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import fields as dataclass_fields
from datetime import timedelta
from decimal import Decimal, InvalidOperation
from typing import Any

from app.domain.engine import EVALUATED_AT, attribute_evidence
from app.domain.models import (
    DuplicateDecision,
    EvidenceReference,
    OperationalEvent,
    OutcomeClaim,
    OutcomeDetermination,
)

from .models import (
    AgreementIR,
    CommercialClaim,
    EvidenceAuthority,
    Fact,
    Norm,
    ObligationStatus,
    TruthValue,
)
from .runtime import (
    EvaluationContext,
    calculate_settlement,
    evaluate_expression,
    evaluate_norm,
    normalize_text,
)

ZERO = Decimal("0.00")


def _claim_payload(claim: OutcomeClaim) -> dict[str, Any]:
    return {field.name: getattr(claim, field.name) for field in dataclass_fields(claim)}


def _event_payload(event: OperationalEvent) -> dict[str, Any]:
    return {
        "id": event.id,
        "source_system": event.source_system,
        "source_record_id": event.source_record_id,
        "event_type": event.event_type,
        "timestamp": event.timestamp,
        "customer_id": event.customer_id,
        "outcome_id": event.outcome_id,
        **event.values,
    }


def _evidence_refs(events: list[OperationalEvent]) -> tuple[EvidenceReference, ...]:
    seen: set[str] = set()
    refs: list[EvidenceReference] = []
    for event in events:
        if event.id in seen:
            continue
        seen.add(event.id)
        refs.append(EvidenceReference(event.id, event.event_type, event.outcome_id))
    return tuple(refs)


def _line(
    claim: OutcomeClaim,
    *,
    status: str,
    reason: str,
    rule_id: str | None,
    evidence: list[OperationalEvent],
    air: AgreementIR,
    duplicate_decision: DuplicateDecision | None = None,
    payable_amount: Decimal | None = None,
) -> OutcomeDetermination:
    if payable_amount is None:
        payable = claim.billed_amount if status == "payable" else ZERO
    else:
        payable = max(ZERO, min(claim.billed_amount, payable_amount))
    if status == "needs_review":
        payable = ZERO
        disputed = ZERO
        review = claim.billed_amount
    else:
        disputed = claim.billed_amount - payable
        review = ZERO
        if status == "disputed" and disputed == ZERO:
            disputed = claim.billed_amount
            payable = ZERO
    return OutcomeDetermination(
        claim=claim,
        status=status,  # type: ignore[arg-type]
        reason=reason,
        rule_id=rule_id,
        evidence=_evidence_refs(evidence),
        confirmed_payable_amount=payable,
        confirmed_disputed_amount=disputed,
        needs_review_amount=review,
        evaluated_at=EVALUATED_AT,
        duplicate_decision=duplicate_decision,
        engine_version=f"air-generic-{air.schema_version}/norms-{len(air.norms)}",
    )


def _facts_for_attribution(
    contradictory: list[OperationalEvent],
    review: list[OperationalEvent],
) -> dict[str, Fact]:
    return {
        "evidence.contradictory": Fact(
            id="evidence.contradictory",
            fact_type="evidence.contradictory",
            truth=TruthValue.TRUE if contradictory else TruthValue.FALSE,
            evidence_ids=[event.id for event in contradictory],
            authority=EvidenceAuthority.CUSTOMER_SYSTEM_OF_RECORD,
        ),
        "evidence.requires_review": Fact(
            id="evidence.requires_review",
            fact_type="evidence.requires_review",
            truth=TruthValue.TRUE if review else TruthValue.FALSE,
            evidence_ids=[event.id for event in review],
            authority=EvidenceAuthority.CUSTOMER_SYSTEM_OF_RECORD,
        ),
    }


def _event_ids(
    expression_result: Any, event_index: dict[str, OperationalEvent]
) -> list[OperationalEvent]:
    return [
        event_index[event_id]
        for event_id in expression_result.evidence_ids
        if event_id in event_index
    ]


def evaluate_claim(
    claim: OutcomeClaim,
    events: list[OperationalEvent],
    air: AgreementIR,
) -> OutcomeDetermination:
    """Evaluate one claim without contract-specific branches."""

    attribution = attribute_evidence(claim, events)
    direct = [item.event for item in attribution.directly_matched]
    contradictory = [item.event for item in attribution.contradictory]
    requires_review = [item.event for item in attribution.requires_review]
    context = EvaluationContext(
        fields={"claim": _claim_payload(claim)},
        events=tuple(_event_payload(event) for event in direct),
        facts=_facts_for_attribution(contradictory, requires_review),
    )
    event_index = {event.id: event for event in [*direct, *contradictory, *requires_review]}

    # Identity conflicts are an evidence-layer uncertainty.  Norms can explicitly
    # reference these facts, but a contract must never silently convert ambiguous
    # attribution into a financial deduction.
    if contradictory or requires_review:
        evidence = [*contradictory, *requires_review]
        return _line(
            claim,
            status="needs_review",
            reason="Evidence attribution is conflicting or requires human confirmation.",
            rule_id=None,
            evidence=evidence,
            air=air,
        )

    for norm in air.norms:
        if norm.condition.operator == "unique_by":
            continue
        expression_result = evaluate_expression(norm.condition, context)
        status = evaluate_norm(norm, context)
        if status in {ObligationStatus.SATISFIED, ObligationStatus.NOT_APPLICABLE}:
            continue
        decisive = _event_ids(expression_result, event_index)
        if status == ObligationStatus.INDETERMINATE:
            return _line(
                claim,
                status=norm.indeterminate_consequence,
                reason=norm.indeterminate_reason
                or f"Required evidence could not determine contractual norm {norm.id}.",
                rule_id=norm.indeterminate_rule_id or norm.violation_reason_code or norm.id,
                evidence=decisive,
                air=air,
            )
        if norm.consequence == "payable":
            # A payable consequence does not create a deduction; continue so the
            # settlement graph remains the final amount authority.
            continue
        return _line(
            claim,
            status=norm.consequence,
            reason=norm.violation_reason or f"Contractual norm {norm.id} was violated.",
            rule_id=norm.violation_reason_code or norm.id,
            evidence=decisive,
            air=air,
        )

    if air.settlement_policies:
        policies = [
            policy for policy in air.settlement_policies if policy.claim_type in {"outcome", "*"}
        ]
        policy = policies[0] if policies else air.settlement_policies[0]
        commercial_claim = CommercialClaim(
            id=claim.outcome_id,
            claim_type=policy.claim_type,
            submitted_amount=f"{claim.billed_amount:.2f}",
            fields=_claim_payload(claim),
        )
        settlement_context = EvaluationContext(
            fields={
                "claim": _claim_payload(claim),
                "settlement": {"eligible_flag": True},
            },
            events=context.events,
            facts=context.facts,
        )
        settlement = calculate_settlement(
            commercial_claim, policy.amount_expression, settlement_context
        )
        if settlement.status == "needs_review":
            return _line(
                claim,
                status="needs_review",
                reason=settlement.explanation,
                rule_id=policy.id,
                evidence=direct,
                air=air,
            )
        payable = Decimal(settlement.payable_amount)
        if payable < claim.billed_amount:
            return _line(
                claim,
                status="disputed",
                reason=settlement.explanation,
                rule_id=policy.id,
                evidence=direct,
                air=air,
                payable_amount=payable,
            )
        return _line(
            claim,
            status="payable",
            reason="All applicable approved contractual norms passed.",
            rule_id=policy.id,
            evidence=direct,
            air=air,
            payable_amount=payable,
        )

    return _line(
        claim,
        status="payable",
        reason="All applicable approved contractual norms passed.",
        rule_id=None,
        evidence=direct,
        air=air,
    )


def _window(norm: Norm) -> timedelta | None:
    spec = norm.condition.parameters.get("window")
    if not isinstance(spec, dict):
        return None
    try:
        value = Decimal(str(spec.get("value")))
    except (InvalidOperation, TypeError, ValueError):
        return None
    unit = str(spec.get("unit", "hours"))
    multipliers = {
        "seconds": Decimal(1),
        "minutes": Decimal(60),
        "hours": Decimal(3600),
        "days": Decimal(86400),
        "calendar_days": Decimal(86400),
    }
    multiplier = multipliers.get(unit)
    if multiplier is None:
        return None
    return timedelta(seconds=float(value * multiplier))


def _uniqueness_decisions(
    provisional: list[OutcomeDetermination],
    norm: Norm,
) -> dict[str, DuplicateDecision]:
    params = norm.condition.parameters
    group_paths = [str(item) for item in params.get("fields", [])]
    order_paths = [str(item) for item in params.get("order_by", [])]
    if not group_paths or not order_paths:
        return {}
    normalizers = params.get("group_normalizers", {})
    window = _window(norm)

    def value(claim: OutcomeClaim, path: str) -> Any:
        return _claim_payload(claim).get(path.removeprefix("claim."))

    def grouped_value(claim: OutcomeClaim, path: str) -> Any:
        raw = value(claim, path)
        return normalize_text(raw) if normalizers.get(path) == "text" else raw

    groups: dict[tuple[Any, ...], list[OutcomeClaim]] = defaultdict(list)
    for determination in provisional:
        if determination.status != "payable":
            continue
        key = tuple(grouped_value(determination.claim, path) for path in group_paths)
        if any(item is None for item in key):
            continue
        groups[key].append(determination.claim)

    decisions: dict[str, DuplicateDecision] = {}
    for claims in groups.values():
        ordered = sorted(
            claims, key=lambda claim: tuple(value(claim, path) for path in order_paths)
        )
        winner = ordered[0]
        for candidate in ordered[1:]:
            within = True if window is None else candidate.closed_at <= winner.closed_at + window
            if within:
                decisions[candidate.outcome_id] = DuplicateDecision(
                    winner_outcome_id=winner.outcome_id,
                    duplicate_outcome_id=candidate.outcome_id,
                    winner_closed_at=winner.closed_at,
                    duplicate_closed_at=candidate.closed_at,
                )
            else:
                winner = candidate
    return decisions


def reconcile_agreement(
    claim_evidence: list[tuple[OutcomeClaim, list[OperationalEvent]]],
    air: AgreementIR,
) -> list[OutcomeDetermination]:
    """Reconcile a batch using only the approved AIR as contractual authority."""

    provisional = [evaluate_claim(claim, events, air) for claim, events in claim_evidence]
    events_by_outcome = {claim.outcome_id: events for claim, events in claim_evidence}
    result_by_outcome = {row.claim.outcome_id: row for row in provisional}

    for norm in [item for item in air.norms if item.condition.operator == "unique_by"]:
        decisions = _uniqueness_decisions(list(result_by_outcome.values()), norm)
        for outcome_id, decision in decisions.items():
            existing = result_by_outcome[outcome_id]
            if existing.status != "payable":
                continue
            candidate_events = events_by_outcome.get(outcome_id, [])
            winner_events = events_by_outcome.get(decision.winner_outcome_id, [])
            status = norm.consequence if norm.consequence != "payable" else "disputed"
            result_by_outcome[outcome_id] = _line(
                existing.claim,
                status=status,
                reason=norm.violation_reason
                or (
                    f"Claim duplicates earlier eligible claim {decision.winner_outcome_id} "
                    "within the contractual uniqueness window."
                ),
                rule_id=norm.violation_reason_code or norm.id,
                evidence=[*candidate_events, *winner_events],
                air=air,
                duplicate_decision=decision,
            )

    return [result_by_outcome[claim.outcome_id] for claim, _ in claim_evidence]
