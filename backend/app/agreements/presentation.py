from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

from .models import (
    AgreementIR,
    AutomationClass,
    Expression,
    Norm,
    NormType,
    ProofRequirement,
    SettlementPolicy,
)


def humanize_identifier(value: str) -> str:
    return (
        " ".join(part for part in value.replace("-", "_").split("_") if part).strip().capitalize()
    )


def verification_method(value: AutomationClass | str) -> str:
    raw = value.value if isinstance(value, AutomationClass) else str(value)
    return {
        "fully_executable": "Automatic",
        "executable_if_data_available": "Automatic when evidence is available",
        "model_assisted": "Assisted review",
        "human_attestation_required": "Manual review required",
        "procedural_only": "Process only",
        "non_operational": "Informational",
        "unsupported": "Not safely automated",
    }.get(raw, humanize_identifier(raw))


def rule_type_label(norm: Norm) -> str:
    if norm.norm_type == NormType.PROHIBITION:
        return "Not payable if"
    if norm.norm_type == NormType.OBLIGATION:
        return "Required for payment"
    if norm.norm_type == NormType.ENTITLEMENT:
        return "Payable when"
    if norm.norm_type == NormType.REMEDY:
        return "Financial adjustment"
    return humanize_identifier(norm.norm_type.value)


def _path(path: str | None) -> str:
    if not path:
        return "value"
    return humanize_identifier(path.split(".")[-1])


def _value(value: Any) -> str:
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, list):
        return ", ".join(_value(item) for item in value)
    if isinstance(value, dict):
        return ", ".join(f"{humanize_identifier(str(k))}: {_value(v)}" for k, v in value.items())
    return str(value)


def _window_text(window: dict[str, Any] | None) -> str:
    if not window:
        return ""
    value = window.get("value")
    unit = str(window.get("unit", "hours")).replace("_", " ")
    if value is None:
        return ""
    try:
        numeric = Decimal(str(value))
        rendered = format(numeric.normalize(), "f")
    except (InvalidOperation, ValueError):
        rendered = str(value)
    if rendered == "1" and unit.endswith("s"):
        unit = unit[:-1]
    return f" within {rendered} {unit}"


def _event_names(parameters: dict[str, Any]) -> str:
    values = parameters.get("event_types") or parameters.get("success_event_types") or []
    if not values:
        return "the required event"
    names = [humanize_identifier(str(item)).lower() for item in values]
    if len(names) == 1:
        return names[0]
    if len(names) == 2:
        return f"{names[0]} or {names[1]}"
    return ", ".join(names[:-1]) + f", or {names[-1]}"


def render_expression(expression: Expression) -> str:
    op = expression.operator
    if op == "constant":
        return _value(expression.value)
    if op in {"field", "fact"}:
        return _path(expression.path)
    if op == "present":
        return f"{render_expression(expression.operands[0])} is present"
    if op in {
        "equals",
        "not_equals",
        "less_than",
        "less_than_or_equal",
        "greater_than",
        "greater_than_or_equal",
    }:
        labels = {
            "equals": "equals",
            "not_equals": "does not equal",
            "less_than": "is less than",
            "less_than_or_equal": "is no more than",
            "greater_than": "is greater than",
            "greater_than_or_equal": "is at least",
        }
        return (
            f"{render_expression(expression.operands[0])} {labels[op]} "
            f"{render_expression(expression.operands[1])}"
        )
    if op == "in":
        return (
            f"{render_expression(expression.operands[0])} is one of "
            f"{render_expression(expression.operands[1])}"
        )
    if op == "and":
        return " and ".join(render_expression(item) for item in expression.operands)
    if op == "or":
        return " or ".join(render_expression(item) for item in expression.operands)
    if op == "not":
        return f"not ({render_expression(expression.operands[0])})"
    if op == "implies":
        return (
            f"if {render_expression(expression.operands[0])}, then "
            f"{render_expression(expression.operands[1])}"
        )
    if op == "exists_event":
        event = _event_names(expression.parameters)
        window = _window_text(expression.parameters.get("window"))
        comparisons = expression.parameters.get("dynamic_field_equals") or []
        qualifier = ""
        if comparisons:
            readable_pairs = []
            for pair in comparisons:
                event_field = humanize_identifier(
                    str(pair.get("event_field", "event value"))
                ).lower()
                claim_field = _path(str(pair.get("claim_field", "claim value"))).lower()
                comparison = pair.get("comparison", "equals")
                verb = "differs from" if comparison == "not_equals" else "matches"
                readable_pairs.append(f"{event_field} {verb} the claimed {claim_field}")
            qualifier = " where " + " and ".join(readable_pairs)
        return f"a {event} event occurs{window}{qualifier}"
    if op == "not_exists_event":
        event = _event_names(expression.parameters)
        return f"no {event} event exists{_window_text(expression.parameters.get('window'))}"
    if op == "terminal_event_outcome":
        success = [
            humanize_identifier(str(item)).lower()
            for item in expression.parameters.get("success_event_types", [])
        ]
        failure = [
            humanize_identifier(str(item)).lower()
            for item in expression.parameters.get("failure_event_types", [])
        ]
        window = _window_text(expression.parameters.get("window"))
        return (
            f"the final outcome{window} is {'/'.join(success) or 'successful'} rather than "
            f"{'/'.join(failure) or 'failed'}"
        )
    if op == "count_events":
        return f"number of {_event_names(expression.parameters)} events"
    if op == "unique_by":
        fields = [
            humanize_identifier(str(item).split(".")[-1]).lower()
            for item in expression.parameters.get("fields", [])
        ]
        window = _window_text(expression.parameters.get("window"))
        return (
            f"the claim is unique by {', '.join(fields) or 'the contract identity fields'}{window}"
        )
    if op == "state_equals":
        return f"{_path(expression.path)} equals {_value(expression.value)}"
    if op in {"add", "subtract", "multiply", "divide", "sum", "minimum", "maximum", "cap", "floor"}:
        label = humanize_identifier(op).lower()
        return f"{label} of " + ", ".join(render_expression(item) for item in expression.operands)
    if op == "rate_table":
        return f"the contract rate for {_path(expression.path).lower()}"
    if op == "tiered_rate":
        return f"the applicable tiered contract rate based on {_path(expression.path).lower()}"
    if op == "within":
        return " occurs within ".join(render_expression(item) for item in expression.operands)
    return humanize_identifier(op)


def render_norm(norm: Norm) -> str:
    condition = render_expression(norm.condition).strip().rstrip(".")
    # The executable condition, not a second generated explanation, is the primary description.
    condition_text = condition
    if norm.norm_type == NormType.PROHIBITION:
        return f"Not payable if {condition_text}."
    if norm.norm_type == NormType.OBLIGATION:
        return f"Payment requires that {condition_text}."
    if norm.norm_type == NormType.ENTITLEMENT:
        return f"Payable when {condition_text}."
    if norm.norm_type == NormType.PERMISSION:
        return f"Permitted when {condition_text}."
    if norm.norm_type == NormType.REMEDY:
        return f"Apply the contractual adjustment when {condition_text}."
    return f"{humanize_identifier(norm.norm_type.value)}: {condition_text}."


def render_settlement(policy: SettlementPolicy) -> str:
    expression = policy.amount_expression
    if expression.operator == "constant":
        return f"Pay {policy.currency} {_value(expression.value)} per eligible claim."
    if expression.operator == "rate_table":
        rates = expression.parameters.get("rates") or {}
        details = ", ".join(
            f"{humanize_identifier(str(key))}: {policy.currency} {_value(value)}"
            for key, value in rates.items()
        )
        default = expression.parameters.get("default")
        if default is not None:
            details += f"; default: {policy.currency} {_value(default)}"
        return f"Use the contract rate table ({details})."
    if expression.operator == "tiered_rate":
        tiers = expression.parameters.get("tiers") or []
        chunks: list[str] = []
        lower = Decimal(0)
        for tier in tiers:
            upper = tier.get("up_to")
            rate = tier.get("unit_price")
            if upper is None:
                chunks.append(f"above {format(lower, 'f')}: {policy.currency} {rate} each")
            else:
                chunks.append(f"up to {upper}: {policy.currency} {rate} each")
                try:
                    lower = Decimal(str(upper))
                except InvalidOperation:
                    pass
        return "Tiered pricing: " + "; ".join(chunks) + "."
    return f"Calculate payable amount using {render_expression(expression)} in {policy.currency}."


def _proofs_for_norm(agreement: AgreementIR, norm_id: str) -> list[ProofRequirement]:
    return [item for item in agreement.proof_requirements if item.norm_id == norm_id]


def finance_rule_views(agreement: AgreementIR) -> list[dict[str, Any]]:
    clauses = {item.id: item for item in agreement.clauses}
    result: list[dict[str, Any]] = []
    for norm in agreement.norms:
        proofs = _proofs_for_norm(agreement, norm.id)
        result.append(
            {
                "id": norm.id,
                "title": rule_type_label(norm),
                "description": render_norm(norm),
                "rule_type": rule_type_label(norm),
                "verification_method": verification_method(norm.automation_class),
                "consequence": norm.consequence,
                "source_clause_ids": list(norm.source_clause_ids),
                "source_clauses": [
                    {
                        "id": clause_id,
                        "document_id": clauses[clause_id].document_id,
                        "text": clauses[clause_id].text,
                    }
                    for clause_id in norm.source_clause_ids
                    if clause_id in clauses
                ],
                "evidence_needed": [proof.description for proof in proofs],
                "proof_requirement_ids": [proof.id for proof in proofs],
                "technical": {
                    "norm_type": norm.norm_type.value,
                    "automation_class": norm.automation_class.value,
                    "violation_reason_code": norm.violation_reason_code,
                    "condition": norm.condition.model_dump(mode="json"),
                },
            }
        )
    return result


def pricing_term_views(agreement: AgreementIR) -> list[dict[str, Any]]:
    clauses = {item.id: item for item in agreement.clauses}
    return [
        {
            "id": policy.id,
            "description": render_settlement(policy),
            "currency": policy.currency,
            "source_clause_ids": list(policy.source_clause_ids),
            "source_clauses": [
                {
                    "id": clause_id,
                    "document_id": clauses[clause_id].document_id,
                    "text": clauses[clause_id].text,
                }
                for clause_id in policy.source_clause_ids
                if clause_id in clauses
            ],
            "technical": {"amount_expression": policy.amount_expression.model_dump(mode="json")},
        }
        for policy in agreement.settlement_policies
    ]


def proof_requirement_views(agreement: AgreementIR) -> list[dict[str, Any]]:
    norms = {item.id: item for item in agreement.norms}
    result: list[dict[str, Any]] = []
    for proof in agreement.proof_requirements:
        norm = norms.get(proof.norm_id)
        result.append(
            {
                "id": proof.id,
                "rule_id": proof.norm_id,
                "rule_description": render_norm(norm) if norm else proof.norm_id,
                "description": proof.description,
                "fact_types": list(proof.acceptable_fact_types),
                "preferred_authority": humanize_identifier(proof.preferred_authority.value),
                "identity_keys": list(proof.identity_keys),
                "required_fields": list(proof.required_fields),
                "requires_complete_export": proof.requires_absence_proof,
                "missing_evidence_effect": "Needs review",
            }
        )
    return result


def agreement_finance_view(agreement: AgreementIR) -> dict[str, Any]:
    return {
        "contract_rules": finance_rule_views(agreement),
        "pricing_terms": pricing_term_views(agreement),
        "evidence_needed": proof_requirement_views(agreement),
    }


def rule_description_for_id(agreement: AgreementIR | None, rule_id: str | None) -> str | None:
    if agreement is None or not rule_id:
        return None
    for norm in agreement.norms:
        aliases = {norm.id, norm.violation_reason_code, norm.indeterminate_rule_id}
        if rule_id in {item for item in aliases if item}:
            return render_norm(norm)
    for policy in agreement.settlement_policies:
        if policy.id == rule_id:
            return render_settlement(policy)
    return None
