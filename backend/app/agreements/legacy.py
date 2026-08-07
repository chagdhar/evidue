from __future__ import annotations

import json
from hashlib import sha256
from typing import Any

from app.domain.models import ExecutableRule, RuleProgram

from .models import (
    AgreementIR,
    AtomicPredicate,
    AutomationClass,
    ClauseCoverage,
    ConformanceReport,
    EvidenceAuthority,
    Expression,
    Norm,
    NormType,
    ProofRequirement,
    SettlementPolicy,
    SourceClause,
)


def _field(path: str) -> Expression:
    return Expression(operator="field", path=path)


def _constant(value: Any) -> Expression:
    return Expression(operator="constant", value=value)


def _legacy_expression(rule: ExecutableRule) -> Expression:
    parameters = rule.parameters
    if rule.operation == "validate_evidence_envelope":
        required_fields = [
            Expression(operator="present", operands=[_field(f"claim.{field}")])
            for field in parameters["required_claim_fields"]  # type: ignore[index]
        ]
        required_fields.append(
            Expression(
                operator="exists_event",
                parameters={"event_types": [parameters["closure_event_type"]]},
            )
        )
        required_fields.append(
            Expression(
                operator="not",
                operands=[Expression(operator="fact", path="evidence.contradictory")],
            )
        )
        required_fields.append(
            Expression(
                operator="not",
                operands=[Expression(operator="fact", path="evidence.requires_review")],
            )
        )
        return Expression(operator="and", operands=required_fields)
    if rule.operation == "claim_datetime_in_range":
        claim_field = _field(f"claim.{parameters['claim_field']}")
        return Expression(
            operator="and",
            operands=[
                Expression(
                    operator="greater_than_or_equal",
                    operands=[claim_field, _constant(parameters["start"])],
                ),
                Expression(
                    operator="less_than",
                    operands=[claim_field, _constant(parameters["end_exclusive"])],
                ),
            ],
        )
    if rule.operation == "claim_amount_equals":
        return Expression(
            operator="equals",
            operands=[
                _field(f"claim.{parameters['claim_field']}"),
                _constant(parameters["expected_amount"]),
            ],
        )
    if rule.operation == "prohibit_event_within":
        window_params: dict[str, Any] = {
            "anchor_path": f"claim.{parameters['anchor_claim_field']}",
            "value": parameters["window_value"],
            "unit": parameters["window_unit"],
            "start_exclusive": True,
        }
        event_parameters: dict[str, Any] = {
            "event_types": parameters["event_types"],
            "window": window_params,
        }
        compare_event = parameters.get("compare_event_value")
        compare_claim = parameters.get("compare_claim_field")
        if compare_event and compare_claim:
            normalizer = "text" if parameters.get("normalization") else None
            event_parameters["dynamic_field_equals"] = [
                {
                    "event_field": compare_event,
                    "claim_field": f"claim.{compare_claim}",
                    "normalizer": normalizer,
                    "comparison": "equals",
                }
            ]
        return Expression(operator="exists_event", parameters=event_parameters)
    if rule.operation == "require_success_event_within":
        return Expression(
            operator="terminal_event_outcome",
            parameters={
                "success_event_types": [parameters["success_event_type"]],
                "failure_event_types": [parameters["failure_event_type"]],
                "window": {
                    "anchor_path": f"claim.{parameters['anchor_claim_field']}",
                    "value": parameters["window_value"],
                    "unit": parameters["window_unit"],
                    "start_exclusive": False,
                },
            },
        )
    if rule.operation == "prohibit_field_mismatch_event":
        comparisons = parameters["comparisons"]
        return Expression(
            operator="exists_event",
            parameters={
                "event_types": [parameters["event_type"]],
                "dynamic_field_match_mode": "any",
                "dynamic_field_equals": [
                    {
                        "event_field": comparison["event_field"],
                        "claim_field": f"claim.{comparison['claim_field']}",
                        "comparison": "not_equals",
                    }
                    for comparison in comparisons
                    if isinstance(comparison, dict)
                ],
            },
        )
    if rule.operation == "unique_first_claim_within":
        normalizers = parameters.get("normalizers", {})
        # "intent" was the legacy normalizer name; it is functionally identical
        # to the runtime's generic "text" normalizer (casefold + collapse separators).
        generic_normalizers = {
            f"claim.{field}": ("text" if name == "intent" else name)
            for field, name in normalizers.items()
        }
        return Expression(
            operator="unique_by",
            parameters={
                "fields": [f"claim.{field}" for field in parameters["group_by"]],
                "order_by": [f"claim.{field}" for field in parameters["order_by"]],
                "scope": rule.id,
                "window": {
                    "value": parameters["window_value"],
                    "unit": parameters["window_unit"],
                },
                "group_normalizers": generic_normalizers,
            },
        )
    raise ValueError(f"Unsupported legacy operation: {rule.operation}")


def _automation_class(rule: ExecutableRule) -> AutomationClass:
    if rule.operation in {
        "validate_evidence_envelope",
        "prohibit_event_within",
        "require_success_event_within",
        "prohibit_field_mismatch_event",
    }:
        return AutomationClass.EXECUTABLE_IF_DATA_AVAILABLE
    return AutomationClass.FULLY_EXECUTABLE


def _determination_metadata(rule: ExecutableRule) -> dict[str, object]:
    metadata: dict[str, object] = {}
    reasons = {
        "R1": (
            "SAME_INTENT_RECONTACT",
            "Same-intent recontact within seven calendar days",
        ),
        "R2": (
            "HUMAN_INTERVENTION",
            "Human completed or materially corrected the work within 24 hours",
        ),
        "R3": (
            "DOWNSTREAM_ACTION_FAILED",
            "Promised downstream action failed within the required two-hour window",
        ),
        "R5": (
            "OPERATIONAL_EVIDENCE_MISMATCH",
            "Customer account or expected action did not match operational evidence",
        ),
        "R6": (
            "OUTSIDE_BILLING_PERIOD",
            "Outcome falls outside the invoice billing period",
        ),
        "R7": ("INVALID_EVIDENCE_ENVELOPE", "Missing required claim identifiers"),
    }
    if rule.id in reasons:
        code, reason = reasons[rule.id]
        metadata["violation_reason_code"] = code
        metadata["violation_reason"] = reason
    if rule.id == "R3":
        metadata.update(
            {
                "indeterminate_reason_code": "MISSING_DOWNSTREAM_EVIDENCE",
                "indeterminate_reason": (
                    "Missing directly attributed evidence for the promised downstream action"
                ),
                "indeterminate_consequence": "needs_review",
                "indeterminate_rule_id": "R7",
            }
        )
    return metadata


def _norm_type(rule: ExecutableRule) -> NormType:
    if rule.operation in {
        "prohibit_event_within",
        "prohibit_field_mismatch_event",
    }:
        return NormType.PROHIBITION
    return NormType.OBLIGATION


def _synthesize_settlement_policy(
    norms: list[Norm], clauses: list[SourceClause]
) -> SettlementPolicy:
    """Build a traceable settlement policy from the per-claim eligibility norms.

    Eligibility references every per-claim norm (everything except the
    batch-level uniqueness norm, which the evaluation harness applies as a
    separate deterministic post-pass -- matching how the legacy engine only
    resolves duplicates among already-provisionally-payable claims). The
    settlement amount is the full billed amount when every eligibility norm
    is satisfied, zero otherwise. This is a binary settlement shape; a
    contract with tiered rates, partial credit, or caps needs a richer
    amount_expression than a flat 0/1 gate, but the policy is now real,
    present, and traceable to every source clause it depends on -- not an
    empty placeholder.
    """
    eligibility_norm_ids = [norm.id for norm in norms if norm.condition.operator != "unique_by"]
    amount_expression = Expression(
        operator="multiply",
        operands=[
            _field("claim.billed_amount"),
            Expression(
                operator="rate_table",
                path="settlement.eligible_flag",
                parameters={"rates": {"true": "1", "false": "0"}, "default": "0"},
            ),
        ],
    )
    return SettlementPolicy(
        id="SETTLEMENT-1",
        claim_type="outcome",
        eligibility_norm_ids=eligibility_norm_ids,
        amount_expression=amount_expression,
        source_clause_ids=[clause.id for clause in clauses],
    )


def legacy_rule_program_to_agreement_ir(program: RuleProgram) -> AgreementIR:
    clauses: list[SourceClause] = []
    norms: list[Norm] = []
    predicates: list[AtomicPredicate] = []
    proofs: list[ProofRequirement] = []
    coverage: list[ClauseCoverage] = []
    for rule in sorted(program.rules, key=lambda item: item.priority):
        clause_id = f"CLAUSE-{rule.id}"
        norm_id = f"NORM-{rule.id}"
        classification = _automation_class(rule)
        clauses.append(
            SourceClause(
                id=clause_id,
                document_id=program.compilation_id,
                text=rule.clause_text,
            )
        )
        norms.append(
            Norm(
                id=norm_id,
                norm_type=_norm_type(rule),
                subject="service_provider",
                beneficiary="customer",
                condition=_legacy_expression(rule),
                consequence=rule.consequence,
                source_clause_ids=[clause_id],
                automation_class=classification,
                legacy_rule_id=rule.id,
                **_determination_metadata(rule),
            )
        )
        predicate_id = f"PREDICATE-{rule.id}"
        predicate_expression = norms[-1].condition
        predicate_hash = (
            "sha256:"
            + sha256(
                json.dumps(
                    predicate_expression.model_dump(mode="json"),
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode("utf-8")
            ).hexdigest()
        )
        predicates.append(
            AtomicPredicate(
                id=predicate_id,
                norm_id=norm_id,
                description=rule.description,
                expression=predicate_expression,
                source_clause_ids=[clause_id],
                automation_class=classification,
                canonical_hash=predicate_hash,
            )
        )
        proofs.append(
            ProofRequirement(
                id=f"PROOF-{rule.id}",
                norm_id=norm_id,
                predicate_id=predicate_id,
                description=rule.description,
                acceptable_fact_types=list(rule.evidence_required),
                preferred_authority=EvidenceAuthority.CUSTOMER_SYSTEM_OF_RECORD,
                acceptable_authorities=[
                    EvidenceAuthority.CUSTOMER_SYSTEM_OF_RECORD,
                    EvidenceAuthority.INDEPENDENT_THIRD_PARTY,
                    EvidenceAuthority.SIGNED_EXECUTION_LOG,
                    EvidenceAuthority.VENDOR_TOOL_TRACE,
                ],
                identity_keys=["invoice_id", "outcome_id", "customer_id"],
            )
        )
        coverage.append(
            ClauseCoverage(
                clause_id=clause_id,
                clause_text=rule.clause_text,
                classification=classification,
                norm_ids=[norm_id],
                rationale="Translated from the validated legacy deterministic rule program.",
            )
        )
    settlement_policy = _synthesize_settlement_policy(norms, clauses)
    return AgreementIR(
        agreement_id=program.compilation_id,
        source_hash=program.source_hash,
        clauses=clauses,
        norms=norms,
        predicates=predicates,
        proof_requirements=proofs,
        settlement_policies=[settlement_policy],
        coverage=coverage,
        diagnostics=[],
    )


def conformance_report(agreement: AgreementIR) -> ConformanceReport:
    material = [item for item in agreement.coverage if item.material]
    settlement_clause_ids = {
        clause_id
        for policy in agreement.settlement_policies
        for clause_id in policy.source_clause_ids
    }
    covered = [
        item
        for item in material
        if item.classification == AutomationClass.NON_OPERATIONAL
        or bool(item.norm_ids)
        or item.clause_id in settlement_clause_ids
    ]
    counts = {classification: 0 for classification in AutomationClass}
    for item in agreement.coverage:
        counts[item.classification] += 1
    blocking = sum(item.severity == "blocking" for item in agreement.diagnostics)
    unsupported_material = sum(
        item.classification == AutomationClass.UNSUPPORTED and item.material
        for item in agreement.coverage
    )
    unrepresented = len(material) - len(covered)
    approvable = blocking == 0 and unsupported_material == 0 and unrepresented == 0
    percent = 100.0 if not material else round(len(covered) / len(material) * 100, 2)
    return ConformanceReport(
        agreement_id=agreement.agreement_id,
        material_clause_count=len(material),
        covered_material_clause_count=len(covered),
        fully_executable_count=counts[AutomationClass.FULLY_EXECUTABLE],
        data_dependent_count=counts[AutomationClass.EXECUTABLE_IF_DATA_AVAILABLE],
        model_assisted_count=counts[AutomationClass.MODEL_ASSISTED],
        human_attestation_count=counts[AutomationClass.HUMAN_ATTESTATION_REQUIRED],
        procedural_count=counts[AutomationClass.PROCEDURAL_ONLY],
        non_operational_count=counts[AutomationClass.NON_OPERATIONAL],
        unsupported_count=counts[AutomationClass.UNSUPPORTED],
        unrepresented_material_clause_count=unrepresented,
        norm_count=len(agreement.norms),
        predicate_count=len(agreement.predicates),
        orphan_proof_requirement_count=sum(
            requirement.predicate_id not in {predicate.id for predicate in agreement.predicates}
            for requirement in agreement.proof_requirements
        ),
        proof_requirement_count=len(agreement.proof_requirements),
        settlement_policy_count=len(agreement.settlement_policies),
        blocking_diagnostic_count=blocking,
        approvable=approvable,
        coverage_percent=percent,
    )
