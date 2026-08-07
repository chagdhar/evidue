"""Agreement IR compatibility evaluator and dual-run comparison.

The legacy deterministic engine remains the default financial authority. This
module executes Agreement IR against the same claim/evidence inputs and reports
complete line-level differences. It intentionally contains the compatibility
adapter from legacy domain objects into contract-neutral AIR inputs; the generic
expression runtime itself has no dependency on the legacy engine.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import timedelta
from decimal import Decimal
from typing import Any

from app.agreements.models import (
    AgreementIR,
    CommercialClaim,
    EvidenceAuthority,
    Fact,
    Norm,
    ObligationStatus,
    TruthValue,
)
from app.agreements.runtime import (
    EvaluationContext,
    calculate_settlement,
    evaluate_expression,
    evaluate_norm,
    normalize_text,
)
from app.domain.engine import EVALUATED_AT, attribute_evidence
from app.domain.models import (
    DuplicateDecision,
    EvidenceReference,
    OperationalEvent,
    OutcomeClaim,
    OutcomeDetermination,
    RuleProgram,
)

ZERO = Decimal("0.00")


def _claim_fields(claim: OutcomeClaim) -> dict[str, Any]:
    return {
        "claim": {
            "outcome_id": claim.outcome_id,
            "invoice_id": claim.invoice_id,
            "customer_id": claim.customer_id,
            "intent": claim.intent,
            "vendor_claim": claim.vendor_claim,
            "closed_at": claim.closed_at,
            "expected_action": claim.expected_action,
            "account_id": claim.account_id,
            "billed_amount": claim.billed_amount,
        }
    }


def _event_dict(event: OperationalEvent) -> dict[str, Any]:
    return {
        "id": event.id,
        "event_type": event.event_type,
        "timestamp": event.timestamp,
        "customer_id": event.customer_id,
        "outcome_id": event.outcome_id,
        **event.values,
    }


def _references(events: list[OperationalEvent]) -> tuple[EvidenceReference, ...]:
    return tuple(
        EvidenceReference(event.id, event.event_type, event.outcome_id) for event in events
    )


def _facts_from_attribution(
    contradictory: bool,
    requires_review: bool,
    contradictory_ids: list[str],
    review_ids: list[str],
) -> dict[str, Fact]:
    return {
        "evidence.contradictory": Fact(
            id="evidence.contradictory",
            fact_type="evidence.contradictory",
            truth=TruthValue.TRUE if contradictory else TruthValue.FALSE,
            evidence_ids=contradictory_ids,
            authority=EvidenceAuthority.CUSTOMER_SYSTEM_OF_RECORD,
        ),
        "evidence.requires_review": Fact(
            id="evidence.requires_review",
            fact_type="evidence.requires_review",
            truth=TruthValue.TRUE if requires_review else TruthValue.FALSE,
            evidence_ids=review_ids,
            authority=EvidenceAuthority.CUSTOMER_SYSTEM_OF_RECORD,
        ),
    }


def _settlement_amounts(
    claim: OutcomeClaim,
    status: str,
    air: AgreementIR,
) -> tuple[Decimal, Decimal, Decimal]:
    if status == "needs_review":
        return ZERO, ZERO, claim.billed_amount
    if not air.settlement_policies:
        payable = claim.billed_amount if status == "payable" else ZERO
        disputed = claim.billed_amount if status == "disputed" else ZERO
        return payable, disputed, ZERO
    policy = air.settlement_policies[0]
    commercial_claim = CommercialClaim(
        id=claim.outcome_id,
        claim_type=policy.claim_type,
        submitted_amount=f"{claim.billed_amount:.2f}",
        fields=_claim_fields(claim)["claim"],
    )
    context = EvaluationContext(
        fields={
            "claim": _claim_fields(claim)["claim"],
            "settlement": {"eligible_flag": status == "payable"},
        }
    )
    line = calculate_settlement(commercial_claim, policy.amount_expression, context)
    return (
        Decimal(line.payable_amount),
        Decimal(line.disputed_amount),
        Decimal(line.needs_review_amount),
    )


def _result(
    claim: OutcomeClaim,
    status: str,
    reason: str,
    rule_id: str | None,
    evidence: list[OperationalEvent],
    *,
    air: AgreementIR,
    duplicate_decision: DuplicateDecision | None = None,
) -> OutcomeDetermination:
    payable, disputed, review = _settlement_amounts(claim, status, air)
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
        engine_version=f"air-{air.schema_version}/norms-{len(air.norms)}",
    )


def _events_by_id(events: list[OperationalEvent]) -> dict[str, OperationalEvent]:
    return {event.id: event for event in events}


def _ordered_events(
    ids: tuple[str, ...],
    event_index: dict[str, OperationalEvent],
) -> list[OperationalEvent]:
    return [event_index[event_id] for event_id in ids if event_id in event_index]


def _r7_failure(
    claim: OutcomeClaim,
    events: list[OperationalEvent],
    air: AgreementIR,
    required_fields: list[str],
    closure_type: str,
) -> tuple[OutcomeDetermination | None, list[OperationalEvent]]:
    attribution = attribute_evidence(claim, events)
    direct = [item.event for item in attribution.directly_matched]
    missing = [field for field in required_fields if not getattr(claim, field)]
    if missing:
        return (
            _result(
                claim,
                "needs_review",
                "Missing required claim identifiers",
                "R7",
                [],
                air=air,
            ),
            direct,
        )
    if attribution.contradictory:
        return (
            _result(
                claim,
                "needs_review",
                "; ".join(item.reason for item in attribution.contradictory),
                "R7",
                [item.event for item in attribution.contradictory],
                air=air,
            ),
            direct,
        )
    if attribution.requires_review:
        return (
            _result(
                claim,
                "needs_review",
                "; ".join(item.reason for item in attribution.requires_review),
                "R7",
                [item.event for item in attribution.requires_review],
                air=air,
            ),
            direct,
        )
    closure = next((event for event in direct if event.event_type == closure_type), None)
    if closure is None:
        return (
            _result(
                claim,
                "needs_review",
                "Missing directly attributed AI closure evidence",
                "R7",
                [],
                air=air,
            ),
            direct,
        )
    return None, direct


def _compat_rule_id(norm: Norm) -> str | None:
    """Compatibility identifier used only while dual-running legacy and native AIR."""

    if norm.legacy_rule_id:
        return norm.legacy_rule_id
    code = norm.violation_reason_code
    return code if code and code.startswith("R") and code[1:].isdigit() else None


def _exact_violation_reason(norm: Norm, claim: OutcomeClaim) -> str:
    if _compat_rule_id(norm) == "R0":
        expected = next(
            (
                operand.value
                for operand in norm.condition.operands
                if operand.operator == "constant"
            ),
            "0.00",
        )
        return (
            f"Billed amount {claim.billed_amount:.2f} does not match the approved "
            f"contract rate {Decimal(str(expected)):.2f}"
        )
    return norm.violation_reason or norm.consequence


def _decisive_evidence(
    norm: Norm,
    result_ids: tuple[str, ...],
    direct: list[OperationalEvent],
    closure: OperationalEvent | None,
) -> list[OperationalEvent]:
    event_index = _events_by_id(direct)
    matched = _ordered_events(result_ids, event_index)
    if _compat_rule_id(norm) in {"R1", "R2"}:
        found = matched[0] if matched else None
        return [event for event in [closure, found] if event]
    if _compat_rule_id(norm) == "R3":
        failed = next(
            (event for event in matched if event.event_type == "downstream_failed"),
            None,
        )
        supporting_types = {"human_refund_completed"}
        supporting = [event for event in direct if event.event_type in supporting_types]
        return [event for event in [closure, failed, *supporting] if event]
    if _compat_rule_id(norm) == "R5":
        return matched[:1]
    if _compat_rule_id(norm) in {"R0", "R6"}:
        return [closure] if closure else []
    return matched


def evaluate_claim_air(
    claim: OutcomeClaim,
    events: list[OperationalEvent],
    air: AgreementIR,
    *,
    duplicate_decision: DuplicateDecision | None = None,
    winner_events: list[OperationalEvent] | None = None,
) -> OutcomeDetermination:
    """Evaluate one legacy-domain claim using Agreement IR semantics."""
    r7_norm = next((norm for norm in air.norms if _compat_rule_id(norm) == "R7"), None)
    required_fields = ["outcome_id", "customer_id", "account_id"]
    closure_type = "ai_closed"
    if r7_norm is not None:
        required_fields = [
            str(operand.operands[0].path).removeprefix("claim.")
            for operand in r7_norm.condition.operands
            if operand.operator == "present" and operand.operands
        ] or required_fields
        closure_expression = next(
            (
                operand
                for operand in r7_norm.condition.operands
                if operand.operator == "exists_event"
            ),
            None,
        )
        if closure_expression is not None:
            types = closure_expression.parameters.get("event_types", [])
            if types:
                closure_type = str(types[0])

    envelope_failure, direct = _r7_failure(
        claim,
        events,
        air,
        required_fields,
        closure_type,
    )
    if envelope_failure is not None:
        return envelope_failure

    direct_dicts = tuple(_event_dict(event) for event in direct)
    event_index = _events_by_id(direct)
    closure = next((event for event in direct if event.event_type == closure_type), None)
    facts = _facts_from_attribution(False, False, [], [])
    context = EvaluationContext(
        fields=_claim_fields(claim),
        events=direct_dicts,
        facts=facts,
    )
    success: OperationalEvent | None = None

    for norm in air.norms:
        if _compat_rule_id(norm) == "R7" or norm.condition.operator == "unique_by":
            continue
        expression_result = evaluate_expression(norm.condition, context)
        norm_status = evaluate_norm(norm, context)

        if norm_status == ObligationStatus.INDETERMINATE:
            decisive = _ordered_events(expression_result.evidence_ids, event_index)
            return _result(
                claim,
                norm.indeterminate_consequence,
                norm.indeterminate_reason or f"Indeterminate evaluation for norm {norm.id}",
                norm.indeterminate_rule_id or _compat_rule_id(norm),
                [event for event in [closure, *decisive] if event],
                air=air,
            )

        violated = norm_status == ObligationStatus.VIOLATED
        if violated:
            decisive = _decisive_evidence(
                norm,
                expression_result.evidence_ids,
                direct,
                closure,
            )
            return _result(
                claim,
                norm.consequence,
                _exact_violation_reason(norm, claim),
                _compat_rule_id(norm),
                decisive,
                air=air,
            )

        if _compat_rule_id(norm) == "R3":
            success = next(
                (event for event in direct if event.event_type == "downstream_succeeded"),
                None,
            )

    duplicate_norm = next(
        (norm for norm in air.norms if norm.condition.operator == "unique_by"),
        None,
    )
    if duplicate_decision and duplicate_norm:
        winner_closure = next(
            (
                event
                for event in (winner_events or [])
                if event.event_type == closure_type
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
            duplicate_norm.consequence,
            (
                f"{claim.outcome_id} duplicates winning outcome "
                f"{duplicate_decision.winner_outcome_id} in the 24-hour attribution window"
            ),
            _compat_rule_id(duplicate_norm),
            duplicate_evidence,
            air=air,
            duplicate_decision=duplicate_decision,
        )

    return _result(
        claim,
        "payable",
        "All applicable contractual rules passed",
        None,
        [event for event in [closure, success] if event],
        air=air,
    )


def _duplicate_window(norm: Norm) -> timedelta:
    spec = norm.condition.parameters.get("window", {})
    value = Decimal(str(spec.get("value", 24)))
    unit = str(spec.get("unit", "hours"))
    if unit == "hours":
        return timedelta(seconds=float(value * Decimal(3600)))
    if unit in {"days", "calendar_days"}:
        return timedelta(seconds=float(value * Decimal(86400)))
    raise ValueError(f"Unsupported duplicate window unit: {unit}")


def _duplicate_decisions_air(
    provisional: list[OutcomeDetermination],
    air: AgreementIR,
) -> dict[str, DuplicateDecision]:
    norm = next((item for item in air.norms if item.condition.operator == "unique_by"), None)
    if norm is None:
        return {}
    params = norm.condition.parameters
    group_fields = [str(field).removeprefix("claim.") for field in params["fields"]]
    order_fields = [str(field).removeprefix("claim.") for field in params.get("order_by", [])]
    normalizers = params.get("group_normalizers", {})
    window = _duplicate_window(norm)

    def normalize(field: str, value: Any) -> Any:
        normalizer = normalizers.get(f"claim.{field}")
        return normalize_text(value) if normalizer == "text" else value

    groups: dict[tuple[Any, ...], list[OutcomeClaim]] = defaultdict(list)
    for determination in provisional:
        if determination.status != "payable":
            continue
        claim = determination.claim
        key = tuple(normalize(field, getattr(claim, field)) for field in group_fields)
        groups[key].append(claim)

    decisions: dict[str, DuplicateDecision] = {}
    for claims in groups.values():
        ordered = sorted(
            claims,
            key=lambda item: tuple(getattr(item, field) for field in order_fields),
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


def reconcile_air(
    claim_evidence: list[tuple[OutcomeClaim, list[OperationalEvent]]],
    air: AgreementIR,
) -> list[OutcomeDetermination]:
    provisional = [evaluate_claim_air(claim, events, air) for claim, events in claim_evidence]
    decisions = _duplicate_decisions_air(provisional, air)
    events_by_outcome = {claim.outcome_id: events for claim, events in claim_evidence}
    final: list[OutcomeDetermination] = []
    for determination, (claim, events) in zip(provisional, claim_evidence, strict=True):
        decision = decisions.get(claim.outcome_id)
        if decision is None:
            final.append(determination)
            continue
        final.append(
            evaluate_claim_air(
                claim,
                events,
                air,
                duplicate_decision=decision,
                winner_events=events_by_outcome[decision.winner_outcome_id],
            )
        )
    return final


def _duplicate_payload(decision: DuplicateDecision | None) -> dict[str, str] | None:
    if decision is None:
        return None
    return {
        "winner_outcome_id": decision.winner_outcome_id,
        "duplicate_outcome_id": decision.duplicate_outcome_id,
        "winner_closed_at": decision.winner_closed_at.isoformat(),
        "duplicate_closed_at": decision.duplicate_closed_at.isoformat(),
    }


def _line_payload(item: OutcomeDetermination) -> dict[str, Any]:
    return {
        "status": item.status,
        "rule_id": item.rule_id,
        "reason": item.reason,
        "confirmed_payable_amount": f"{item.confirmed_payable_amount:.2f}",
        "confirmed_disputed_amount": f"{item.confirmed_disputed_amount:.2f}",
        "needs_review_amount": f"{item.needs_review_amount:.2f}",
        "evidence_ids": [reference.event_id for reference in item.evidence],
        "duplicate_decision": _duplicate_payload(item.duplicate_decision),
    }


def dual_run(
    claim_evidence: list[tuple[OutcomeClaim, list[OperationalEvent]]],
    air: AgreementIR,
    program: RuleProgram,
) -> dict[str, Any]:
    """Run legacy and AIR engines and compare complete line determinations."""
    from app.domain.engine import reconcile as legacy_reconcile

    legacy_results = legacy_reconcile(claim_evidence, program=program)
    air_results = reconcile_air(claim_evidence, air)
    differences: list[dict[str, Any]] = []
    status_matches = 0
    exact_matches = 0
    for legacy, air_item in zip(legacy_results, air_results, strict=True):
        legacy_payload = _line_payload(legacy)
        air_payload = _line_payload(air_item)
        if legacy.status == air_item.status:
            status_matches += 1
        if legacy_payload == air_payload:
            exact_matches += 1
            continue
        differences.append(
            {
                "outcome_id": legacy.claim.outcome_id,
                "legacy": legacy_payload,
                "air": air_payload,
            }
        )

    def total(field: str, items: list[OutcomeDetermination]) -> Decimal:
        return sum((getattr(item, field) for item in items), Decimal())

    legacy_payable = total("confirmed_payable_amount", legacy_results)
    legacy_disputed = total("confirmed_disputed_amount", legacy_results)
    legacy_review = total("needs_review_amount", legacy_results)
    air_payable = total("confirmed_payable_amount", air_results)
    air_disputed = total("confirmed_disputed_amount", air_results)
    air_review = total("needs_review_amount", air_results)
    total_claims = len(legacy_results)
    return {
        "total_claims": total_claims,
        "status_matches": status_matches,
        "status_mismatches": total_claims - status_matches,
        "exact_matches": exact_matches,
        "exact_mismatches": total_claims - exact_matches,
        "equivalence_rate": (
            f"{exact_matches / total_claims * 100:.2f}%" if total_claims else "N/A"
        ),
        "legacy_payable": f"{legacy_payable:.2f}",
        "legacy_disputed": f"{legacy_disputed:.2f}",
        "legacy_review": f"{legacy_review:.2f}",
        "air_payable": f"{air_payable:.2f}",
        "air_disputed": f"{air_disputed:.2f}",
        "air_review": f"{air_review:.2f}",
        "amounts_match": (
            legacy_payable == air_payable
            and legacy_disputed == air_disputed
            and legacy_review == air_review
        ),
        "differences": differences[:100],
        "legacy_results": legacy_results,
        "air_results": air_results,
    }
