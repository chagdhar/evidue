from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any

from .models import (
    CommercialClaim,
    Expression,
    Fact,
    Norm,
    NormType,
    ObligationStatus,
    SettlementLine,
    TruthValue,
)


@dataclass(frozen=True)
class EvaluationContext:
    fields: dict[str, Any]
    events: tuple[dict[str, Any], ...] = ()
    facts: dict[str, Fact] = field(default_factory=dict)
    uniqueness_sets: dict[str, set[tuple[Any, ...]]] = field(default_factory=dict)


@dataclass(frozen=True)
class EvaluationResult:
    truth: TruthValue | None = None
    value: Any | None = None
    evidence_ids: tuple[str, ...] = ()


def lookup_path(data: dict[str, Any], path: str) -> Any | None:
    current: Any = data
    for part in path.split("."):
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


def truth_value(result: EvaluationResult) -> TruthValue:
    if result.truth is not None:
        return result.truth
    if result.value is None:
        return TruthValue.UNKNOWN
    return TruthValue.TRUE if bool(result.value) else TruthValue.FALSE


def _and(values: list[TruthValue]) -> TruthValue:
    if TruthValue.FALSE in values:
        return TruthValue.FALSE
    if TruthValue.CONFLICTING in values:
        return TruthValue.CONFLICTING
    if TruthValue.UNKNOWN in values:
        return TruthValue.UNKNOWN
    return TruthValue.TRUE


def _or(values: list[TruthValue]) -> TruthValue:
    if TruthValue.TRUE in values:
        return TruthValue.TRUE
    if TruthValue.CONFLICTING in values:
        return TruthValue.CONFLICTING
    if TruthValue.UNKNOWN in values:
        return TruthValue.UNKNOWN
    return TruthValue.FALSE


def _negate(value: TruthValue) -> TruthValue:
    if value == TruthValue.TRUE:
        return TruthValue.FALSE
    if value == TruthValue.FALSE:
        return TruthValue.TRUE
    return value


def normalize_text(value: object) -> str:
    """Normalize text for contract-neutral identity comparisons."""
    return " ".join(str(value).casefold().replace("_", " ").replace("-", " ").split())


def _apply_normalizer(value: Any, normalizer: str | None) -> Any:
    if normalizer == "text":
        return normalize_text(value)
    return value


def _duration(value: object, unit: object) -> timedelta | None:
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None
    if amount < 0:
        return None
    seconds_per_unit = {
        "seconds": Decimal(1),
        "minutes": Decimal(60),
        "hours": Decimal(3600),
        "days": Decimal(86400),
        "calendar_days": Decimal(86400),
    }
    multiplier = seconds_per_unit.get(str(unit))
    if multiplier is None:
        return None
    seconds = amount * multiplier
    whole_seconds = int(seconds)
    microseconds = int((seconds - Decimal(whole_seconds)) * Decimal(1_000_000))
    return timedelta(seconds=whole_seconds, microseconds=microseconds)


def _resolve_window(
    parameters: dict[str, Any], context: EvaluationContext
) -> tuple[tuple[datetime, datetime], bool, bool] | None:
    window = parameters.get("window")
    if not isinstance(window, dict):
        return None
    anchor_path = window.get("anchor_path")
    anchor = lookup_path(context.fields, str(anchor_path)) if anchor_path else None
    if not isinstance(anchor, datetime):
        return None
    duration = _duration(window.get("value"), window.get("unit", "hours"))
    if duration is None:
        return None
    start_exclusive = bool(window.get("start_exclusive", False))
    end_exclusive = bool(window.get("end_exclusive", False))
    return (anchor, anchor + duration), start_exclusive, end_exclusive


def _compatible_datetimes(left: datetime, right: datetime) -> bool:
    return (left.tzinfo is None) == (right.tzinfo is None)


def _event_in_window(
    event_timestamp: datetime,
    window_bounds: tuple[datetime, datetime],
    start_exclusive: bool,
    end_exclusive: bool,
) -> bool:
    lower, upper = window_bounds
    if not _compatible_datetimes(event_timestamp, lower):
        return False
    lower_match = lower < event_timestamp if start_exclusive else lower <= event_timestamp
    upper_match = event_timestamp < upper if end_exclusive else event_timestamp <= upper
    return lower_match and upper_match


def _event_matches(
    event: dict[str, Any], expression: Expression, context: EvaluationContext
) -> bool:
    event_types = {str(item) for item in expression.parameters.get("event_types", [])}
    if str(event.get("event_type")) not in event_types:
        return False
    filters = expression.parameters.get("filters", {})
    if not isinstance(filters, dict):
        return False
    if not all(lookup_path(event, str(path)) == expected for path, expected in filters.items()):
        return False

    window = expression.parameters.get("window")
    if isinstance(window, dict):
        resolved = _resolve_window(expression.parameters, context)
        if resolved is None:
            return False
        bounds, start_exclusive, end_exclusive = resolved
        timestamp = event.get("timestamp")
        if not isinstance(timestamp, datetime) or not _event_in_window(
            timestamp, bounds, start_exclusive, end_exclusive
        ):
            return False

    dynamic = expression.parameters.get("dynamic_field_equals")
    if isinstance(dynamic, list):
        match_mode = expression.parameters.get("dynamic_field_match_mode", "all")
        outcomes: list[bool] = []
        for pair in dynamic:
            if not isinstance(pair, dict):
                return False
            event_value = _apply_normalizer(
                event.get(str(pair.get("event_field"))), pair.get("normalizer")
            )
            claim_value = _apply_normalizer(
                lookup_path(context.fields, str(pair.get("claim_field"))),
                pair.get("normalizer"),
            )
            comparison = pair.get("comparison", "equals")
            matched = event_value == claim_value
            if comparison == "not_equals":
                matched = not matched
            outcomes.append(matched)
        if match_mode == "any":
            if not any(outcomes):
                return False
        elif not all(outcomes):
            return False
    return True


def _comparison(operator: str, left: Any, right: Any) -> TruthValue:
    if left is None or right is None:
        return TruthValue.UNKNOWN
    if isinstance(left, datetime) and isinstance(right, str):
        try:
            right = datetime.fromisoformat(right)
        except ValueError:
            return TruthValue.UNKNOWN
    if isinstance(right, datetime) and isinstance(left, str):
        try:
            left = datetime.fromisoformat(left)
        except ValueError:
            return TruthValue.UNKNOWN
    if (
        isinstance(left, datetime)
        and isinstance(right, datetime)
        and not _compatible_datetimes(left, right)
    ):
        return TruthValue.UNKNOWN
    if isinstance(left, Decimal) and isinstance(right, str):
        try:
            right = Decimal(right)
        except (InvalidOperation, ValueError):
            pass
    if isinstance(right, Decimal) and isinstance(left, str):
        try:
            left = Decimal(left)
        except (InvalidOperation, ValueError):
            pass
    try:
        if operator == "equals":
            result = left == right
        elif operator == "not_equals":
            result = left != right
        elif operator == "less_than":
            result = left < right
        elif operator == "less_than_or_equal":
            result = left <= right
        elif operator == "greater_than":
            result = left > right
        elif operator == "greater_than_or_equal":
            result = left >= right
        elif operator == "in":
            result = left in right
        else:
            raise ValueError(f"Unsupported comparison: {operator}")
    except (TypeError, ValueError):
        return TruthValue.UNKNOWN
    return TruthValue.TRUE if result else TruthValue.FALSE


def _decimal(value: Any) -> Decimal | None:
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None


def _rate_key(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, Decimal):
        return format(value.normalize(), "f")
    return str(value)


def evaluate_expression(expression: Expression, context: EvaluationContext) -> EvaluationResult:
    operator = expression.operator
    if operator == "constant":
        return EvaluationResult(value=expression.value)
    if operator == "field":
        return EvaluationResult(value=lookup_path(context.fields, str(expression.path)))
    if operator == "fact":
        fact = context.facts.get(str(expression.path))
        if fact is None:
            return EvaluationResult(truth=TruthValue.UNKNOWN)
        return EvaluationResult(
            truth=fact.truth,
            value=fact.value,
            evidence_ids=tuple(fact.evidence_ids),
        )
    if operator == "present":
        value = evaluate_expression(expression.operands[0], context).value
        present = value is not None and value != ""
        return EvaluationResult(truth=TruthValue.TRUE if present else TruthValue.FALSE)
    if operator in {"and", "or"}:
        results = [evaluate_expression(item, context) for item in expression.operands]
        values = [truth_value(item) for item in results]
        truth = _and(values) if operator == "and" else _or(values)
        evidence = tuple(item for result in results for item in result.evidence_ids)
        return EvaluationResult(truth=truth, evidence_ids=evidence)
    if operator == "not":
        result = evaluate_expression(expression.operands[0], context)
        return EvaluationResult(
            truth=_negate(truth_value(result)), evidence_ids=result.evidence_ids
        )
    if operator == "implies":
        left = truth_value(evaluate_expression(expression.operands[0], context))
        right = truth_value(evaluate_expression(expression.operands[1], context))
        return EvaluationResult(truth=_or([_negate(left), right]))
    if operator in {
        "equals",
        "not_equals",
        "less_than",
        "less_than_or_equal",
        "greater_than",
        "greater_than_or_equal",
        "in",
    }:
        left = evaluate_expression(expression.operands[0], context)
        right = evaluate_expression(expression.operands[1], context)
        return EvaluationResult(
            truth=_comparison(operator, left.value, right.value),
            evidence_ids=left.evidence_ids + right.evidence_ids,
        )
    if operator in {"exists_event", "not_exists_event", "count_events"}:
        matching = [event for event in context.events if _event_matches(event, expression, context)]
        evidence = tuple(str(event.get("id", "")) for event in matching if event.get("id"))
        if operator == "count_events":
            return EvaluationResult(value=len(matching), evidence_ids=evidence)
        truth = TruthValue.TRUE if matching else TruthValue.FALSE
        if operator == "not_exists_event":
            truth = _negate(truth)
        return EvaluationResult(truth=truth, evidence_ids=evidence)
    if operator == "terminal_event_outcome":
        success_types = {str(item) for item in expression.parameters.get("success_event_types", [])}
        failure_types = {str(item) for item in expression.parameters.get("failure_event_types", [])}
        success_expression = expression.model_copy(
            update={
                "operator": "exists_event",
                "parameters": {
                    **expression.parameters,
                    "event_types": list(success_types),
                },
            }
        )
        timely_successes = [
            event for event in context.events if _event_matches(event, success_expression, context)
        ]
        failures = [
            event for event in context.events if str(event.get("event_type")) in failure_types
        ]
        all_successes = [
            event for event in context.events if str(event.get("event_type")) in success_types
        ]
        evidence = tuple(
            str(event.get("id"))
            for event in [*failures, *timely_successes, *all_successes]
            if event.get("id")
        )
        if failures and all_successes:
            return EvaluationResult(
                truth=TruthValue.CONFLICTING,
                evidence_ids=tuple(dict.fromkeys(evidence)),
            )
        if failures:
            return EvaluationResult(truth=TruthValue.FALSE, evidence_ids=evidence)
        if timely_successes:
            return EvaluationResult(truth=TruthValue.TRUE, evidence_ids=evidence)
        if all_successes:
            return EvaluationResult(truth=TruthValue.FALSE, evidence_ids=evidence)
        return EvaluationResult(truth=TruthValue.UNKNOWN)
    if operator == "within":
        event_time = evaluate_expression(expression.operands[0], context).value
        anchor_time = evaluate_expression(expression.operands[1], context).value
        duration_seconds = evaluate_expression(expression.operands[2], context).value
        if not isinstance(event_time, datetime) or not isinstance(anchor_time, datetime):
            return EvaluationResult(truth=TruthValue.UNKNOWN)
        if not _compatible_datetimes(event_time, anchor_time):
            return EvaluationResult(truth=TruthValue.UNKNOWN)
        duration = _duration(duration_seconds, "seconds")
        if duration is None:
            return EvaluationResult(truth=TruthValue.UNKNOWN)
        limit = anchor_time + duration
        return EvaluationResult(
            truth=TruthValue.TRUE if anchor_time <= event_time <= limit else TruthValue.FALSE
        )
    if operator == "state_equals":
        actual = lookup_path(context.fields, str(expression.path))
        return EvaluationResult(truth=_comparison("equals", actual, expression.value))
    if operator == "unique_by":
        fields = [str(item) for item in expression.parameters["fields"]]
        scope = str(expression.parameters.get("scope", "default"))
        key = tuple(lookup_path(context.fields, path) for path in fields)
        if any(item is None for item in key):
            return EvaluationResult(truth=TruthValue.UNKNOWN)
        seen = context.uniqueness_sets.get(scope, set())
        return EvaluationResult(truth=TruthValue.FALSE if key in seen else TruthValue.TRUE)
    if operator in {"add", "multiply", "sum", "minimum", "maximum"}:
        values = [
            _decimal(evaluate_expression(item, context).value) for item in expression.operands
        ]
        if any(value is None for value in values):
            return EvaluationResult()
        numbers = [value for value in values if value is not None]
        if operator in {"add", "sum"}:
            value = sum(numbers, Decimal(0))
        elif operator == "multiply":
            value = Decimal(1)
            for number in numbers:
                value *= number
        elif operator == "minimum":
            value = min(numbers)
        else:
            value = max(numbers)
        return EvaluationResult(value=value)
    if operator in {"subtract", "divide", "cap", "floor"}:
        left = _decimal(evaluate_expression(expression.operands[0], context).value)
        right = _decimal(evaluate_expression(expression.operands[1], context).value)
        if left is None or right is None:
            return EvaluationResult()
        if operator == "subtract":
            value = left - right
        elif operator == "divide":
            if right == 0:
                return EvaluationResult()
            value = left / right
        elif operator == "cap":
            value = min(left, right)
        else:
            value = max(left, right)
        return EvaluationResult(value=value)
    if operator == "rate_table":
        key = lookup_path(context.fields, str(expression.path))
        rates = expression.parameters["rates"]
        if not isinstance(rates, dict):
            return EvaluationResult()
        normalized = {_rate_key(rate_key): rate for rate_key, rate in rates.items()}
        rate = normalized.get(_rate_key(key), expression.parameters.get("default"))
        return EvaluationResult(value=_decimal(rate))
    if operator == "tiered_rate":
        quantity = _decimal(lookup_path(context.fields, str(expression.path)))
        tiers = expression.parameters.get("tiers")
        if quantity is None or quantity < 0 or not isinstance(tiers, list):
            return EvaluationResult()
        remaining = quantity
        lower = Decimal(0)
        total = Decimal(0)
        for tier in tiers:
            if not isinstance(tier, dict):
                return EvaluationResult()
            unit_price = _decimal(tier.get("unit_price"))
            upper = _decimal(tier.get("up_to")) if tier.get("up_to") is not None else None
            if unit_price is None or (upper is not None and upper <= lower):
                return EvaluationResult()
            tier_capacity = remaining if upper is None else min(remaining, upper - lower)
            if tier_capacity > 0:
                total += tier_capacity * unit_price
                remaining -= tier_capacity
            if remaining <= 0:
                break
            if upper is None:
                break
            lower = upper
        if remaining > 0:
            return EvaluationResult()
        return EvaluationResult(value=total)
    raise ValueError(f"Unsupported Agreement IR operator: {operator}")


def evaluate_norm(norm: Norm, context: EvaluationContext) -> ObligationStatus:
    if norm.trigger is not None:
        trigger = truth_value(evaluate_expression(norm.trigger, context))
        if trigger == TruthValue.FALSE:
            return ObligationStatus.NOT_APPLICABLE
        if trigger in {TruthValue.UNKNOWN, TruthValue.CONFLICTING}:
            return ObligationStatus.INDETERMINATE
    for exception in norm.exceptions:
        value = truth_value(evaluate_expression(exception, context))
        if value == TruthValue.TRUE:
            return ObligationStatus.NOT_APPLICABLE
        if value in {TruthValue.UNKNOWN, TruthValue.CONFLICTING}:
            return ObligationStatus.INDETERMINATE
    truth = truth_value(evaluate_expression(norm.condition, context))
    if truth in {TruthValue.UNKNOWN, TruthValue.CONFLICTING}:
        return ObligationStatus.INDETERMINATE
    if norm.norm_type == NormType.PROHIBITION:
        return ObligationStatus.VIOLATED if truth == TruthValue.TRUE else ObligationStatus.SATISFIED
    return ObligationStatus.SATISFIED if truth == TruthValue.TRUE else ObligationStatus.VIOLATED


def calculate_settlement(
    claim: CommercialClaim,
    amount_expression: Expression,
    context: EvaluationContext,
) -> SettlementLine:
    submitted = _decimal(claim.submitted_amount)
    evaluated = _decimal(evaluate_expression(amount_expression, context).value)
    if submitted is None:
        raise ValueError("Commercial claim submitted_amount must be numeric")
    if evaluated is None:
        return SettlementLine(
            claim_id=claim.id,
            submitted_amount=f"{submitted:.2f}",
            payable_amount="0.00",
            disputed_amount="0.00",
            needs_review_amount=f"{submitted:.2f}",
            status="needs_review",
            explanation="Settlement expression could not be evaluated from available facts.",
        )
    payable = max(Decimal(0), min(submitted, evaluated))
    disputed = submitted - payable
    status = "payable" if disputed == 0 else "disputed"
    return SettlementLine(
        claim_id=claim.id,
        submitted_amount=f"{submitted:.2f}",
        payable_amount=f"{payable:.2f}",
        disputed_amount=f"{disputed:.2f}",
        needs_review_amount="0.00",
        status=status,
        explanation="Settlement calculated from the approved Agreement IR expression.",
    )
