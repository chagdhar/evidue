"""Deterministic lowerer: validated clause-analysis proposals → AgreementIR.

The LLM proposes semantic structure. This module builds executable Expression
trees, resolves definitions and references, validates everything, and produces
an AgreementIR that can be approved and persisted.

The LLM never sees Expression operators. This module is the only code that
creates them.
"""

from __future__ import annotations

import json
from decimal import Decimal
from hashlib import sha256
from typing import Any

from .compiler_models import (
    AgreementCompilationProposal,
    ConditionProposal,
    DefinitionProposal,
    SettlementProposal,
)
from .legacy import conformance_report
from .models import (
    AgreementIR,
    AtomicPredicate,
    AutomationClass,
    ClauseCoverage,
    CompilerDiagnostic,
    ConformanceReport,
    EvidenceAuthority,
    Expression,
    Norm,
    NormType,
    ProofRequirement,
    SettlementPolicy,
    SourceClause,
)

# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def lower_to_agreement_ir(
    proposal: AgreementCompilationProposal,
    *,
    compilation_id: str,
    version: int,
    source_hash: str,
) -> tuple[AgreementIR, ConformanceReport]:
    """Convert a validated LLM proposal into executable AgreementIR."""
    diagnostics: list[CompilerDiagnostic] = []

    # M3: resolve definitions and references
    definitions = _resolve_definitions(proposal, diagnostics)
    _resolve_references(proposal, diagnostics)

    # M2: lower each clause
    clauses: list[SourceClause] = []
    norms: list[Norm] = []
    predicates: list[AtomicPredicate] = []
    proofs: list[ProofRequirement] = []
    coverage: list[ClauseCoverage] = []

    for clause_proposal in proposal.clauses:
        clause_id = f"NATIVE-{clause_proposal.clause_id}"
        clauses.append(
            SourceClause(
                id=clause_id,
                document_id=clause_proposal.source_document_id,
                text=clause_proposal.source_text,
                material=clause_proposal.material,
                source_start=clause_proposal.source_start,
                source_end=clause_proposal.source_end,
                text_hash=clause_proposal.source_text_hash,
            )
        )

        clause_norm_ids: list[str] = []
        for norm_proposal in clause_proposal.norms:
            norm_id = f"NORM-{norm_proposal.id}"
            clause_norm_ids.append(norm_id)
            try:
                condition_expr = _lower_condition(norm_proposal.condition)
            except LoweringError as exc:
                diagnostics.append(
                    CompilerDiagnostic(
                        code="LOWERING_FAILED",
                        severity="blocking",
                        message=f"Norm {norm_proposal.id}: {exc}",
                        clause_ids=[clause_id],
                    )
                )
                continue

            trigger_expr = None
            if norm_proposal.trigger is not None:
                try:
                    trigger_expr = _lower_condition(norm_proposal.trigger)
                except LoweringError as exc:
                    diagnostics.append(
                        CompilerDiagnostic(
                            code="TRIGGER_LOWERING_FAILED",
                            severity="blocking",
                            message=f"Trigger in {norm_proposal.id}: {exc}",
                            clause_ids=[clause_id],
                        )
                    )
                    continue

            exception_exprs = []
            for exception in norm_proposal.exceptions:
                try:
                    exception_exprs.append(_lower_condition(exception.condition))
                except LoweringError as exc:
                    diagnostics.append(
                        CompilerDiagnostic(
                            code="EXCEPTION_LOWERING_FAILED",
                            severity="blocking",
                            message=f"Exception in {norm_proposal.id}: {exc}",
                            clause_ids=[clause_id],
                        )
                    )

            norms.append(
                Norm(
                    id=norm_id,
                    norm_type=NormType(norm_proposal.norm_type),
                    subject=norm_proposal.subject,
                    beneficiary=norm_proposal.beneficiary,
                    trigger=trigger_expr,
                    condition=condition_expr,
                    exceptions=exception_exprs,
                    consequence=norm_proposal.consequence,
                    source_clause_ids=[clause_id],
                    automation_class=AutomationClass(clause_proposal.automation_classification),
                    violation_reason_code=norm_proposal.violation_reason_code,
                    indeterminate_reason_code=norm_proposal.indeterminate_reason_code,
                    violation_reason=norm_proposal.violation_reason,
                    indeterminate_reason=norm_proposal.indeterminate_reason,
                    indeterminate_consequence=norm_proposal.indeterminate_consequence,
                )
            )

            for i, proof in enumerate(norm_proposal.proof_requirements):
                predicate_id = f"PRED-{norm_proposal.id}-{i}"
                predicate_payload = condition_expr.model_dump(mode="json")
                predicate_hash = (
                    "sha256:"
                    + sha256(
                        json.dumps(predicate_payload, sort_keys=True, separators=(",", ":")).encode(
                            "utf-8"
                        )
                    ).hexdigest()
                )
                predicates.append(
                    AtomicPredicate(
                        id=predicate_id,
                        norm_id=norm_id,
                        description=proof.description,
                        expression=condition_expr,
                        source_clause_ids=[clause_id],
                        automation_class=AutomationClass(clause_proposal.automation_classification),
                        canonical_hash=predicate_hash,
                    )
                )
                proofs.append(
                    ProofRequirement(
                        id=f"PROOF-{norm_proposal.id}-{i}",
                        norm_id=norm_id,
                        predicate_id=predicate_id,
                        description=proof.description,
                        acceptable_fact_types=proof.fact_types,
                        preferred_authority=EvidenceAuthority(proof.preferred_authority),
                        acceptable_authorities=[
                            EvidenceAuthority.CUSTOMER_SYSTEM_OF_RECORD,
                            EvidenceAuthority.INDEPENDENT_THIRD_PARTY,
                            EvidenceAuthority.SIGNED_EXECUTION_LOG,
                            EvidenceAuthority.VENDOR_TOOL_TRACE,
                        ],
                        identity_keys=proof.identity_keys
                        or ["invoice_id", "outcome_id", "customer_id"],
                        required_entity_type=proof.entity_type,
                        required_fields=proof.required_fields,
                        observation_window=proof.observation_window,
                        requires_absence_proof=proof.requires_absence_proof,
                        missing_evidence_result=_truth_value_for(proof.missing_evidence_result),
                    )
                )

        # M4: lower settlement effects
        for settlement in clause_proposal.settlement_effects:
            # Handled below after all clauses are processed
            pass

        # Handle unsupported material clauses
        if clause_proposal.material and clause_proposal.automation_classification == "unsupported":
            diagnostics.append(
                CompilerDiagnostic(
                    code="UNSUPPORTED_MATERIAL_CLAUSE",
                    severity="blocking",
                    message=f"Material clause {clause_proposal.clause_id} contains "
                    f"unsupported concepts: {clause_proposal.unsupported_concepts}",
                    clause_ids=[clause_id],
                )
            )

        # Check for undefined terms
        for term in clause_proposal.defined_terms_used:
            if term not in definitions and clause_proposal.material:
                diagnostics.append(
                    CompilerDiagnostic(
                        code="UNRESOLVED_DEFINITION",
                        severity="blocking",
                        message=f"Material clause {clause_proposal.clause_id} uses "
                        f"undefined term: '{term}'",
                        clause_ids=[clause_id],
                    )
                )

        # Propagate clause-level diagnostics
        for diag in clause_proposal.diagnostics:
            diagnostics.append(
                CompilerDiagnostic(
                    code=diag.code,
                    severity=diag.severity,
                    message=diag.message,
                    clause_ids=[clause_id],
                )
            )

        coverage.append(
            ClauseCoverage(
                clause_id=clause_id,
                clause_text=clause_proposal.source_text,
                classification=AutomationClass(clause_proposal.automation_classification),
                norm_ids=clause_norm_ids,
                rationale="Natively compiled from clause analysis proposal.",
                material=clause_proposal.material,
            )
        )

    # Propagate global diagnostics
    for diag in proposal.global_diagnostics:
        diagnostics.append(
            CompilerDiagnostic(
                code=diag.code,
                severity=diag.severity,
                message=diag.message,
            )
        )

    # M4: Build settlement policies from settlement_effects
    settlement_policies = _lower_settlements(proposal, clauses, norms, diagnostics)

    agreement = AgreementIR(
        agreement_id=compilation_id,
        source_hash=source_hash,
        clauses=clauses,
        norms=norms,
        predicates=predicates,
        proof_requirements=proofs,
        settlement_policies=settlement_policies,
        coverage=coverage,
        diagnostics=diagnostics,
    )

    return agreement, conformance_report(agreement)


# ---------------------------------------------------------------------------
# Condition lowering — one match arm per AllowedConditionType
# ---------------------------------------------------------------------------


class LoweringError(Exception):
    pass


def _field(path: str) -> Expression:
    return Expression(operator="field", path=path)


def _constant(value: Any) -> Expression:
    return Expression(operator="constant", value=value)


def _lower_condition(condition: ConditionProposal) -> Expression:
    """Deterministically map a ConditionProposal to an Expression tree."""
    ct = condition.condition_type
    p = condition.parameters

    if ct == "field_present":
        return Expression(
            operator="present",
            operands=[_field(f"claim.{p['field']}")],
        )

    if ct == "field_equals":
        return Expression(
            operator="equals",
            operands=[_field(f"claim.{p['field']}"), _constant(p["expected_value"])],
        )

    if ct == "field_in_set":
        return Expression(
            operator="in",
            operands=[_field(f"claim.{p['field']}"), _constant(p["values"])],
        )

    if ct == "datetime_in_range":
        claim_field = _field(f"claim.{p['field']}")
        return Expression(
            operator="and",
            operands=[
                Expression(
                    operator="greater_than_or_equal",
                    operands=[claim_field, _constant(p["start"])],
                ),
                Expression(
                    operator="less_than",
                    operands=[claim_field, _constant(p["end_exclusive"])],
                ),
            ],
        )

    if ct == "amount_equals":
        return Expression(
            operator="equals",
            operands=[_field(f"claim.{p['field']}"), _constant(p["expected_amount"])],
        )

    if ct == "event_exists":
        return Expression(
            operator="exists_event",
            parameters={"event_types": p["event_types"]},
        )

    if ct == "event_absent":
        return Expression(
            operator="not_exists_event",
            parameters={"event_types": p["event_types"]},
        )

    if ct == "event_within_window":
        event_params: dict[str, Any] = {
            "event_types": p["event_types"],
            "window": {
                "anchor_path": f"claim.{p['anchor_field']}",
                "value": p["window_value"],
                "unit": p["window_unit"],
                "start_exclusive": p.get("start_exclusive", False),
            },
        }
        compare_fields = p.get("compare_fields")
        if isinstance(compare_fields, list) and compare_fields:
            event_params["dynamic_field_equals"] = [
                {
                    "event_field": cf["event_field"],
                    "claim_field": f"claim.{cf['claim_field']}",
                    "normalizer": cf.get("normalizer"),
                    "comparison": cf.get("comparison", "equals"),
                }
                for cf in compare_fields
                if isinstance(cf, dict)
            ]
        match_mode = p.get("match_mode")
        if match_mode:
            event_params["dynamic_field_match_mode"] = match_mode
        return Expression(operator="exists_event", parameters=event_params)

    if ct == "terminal_outcome":
        params: dict[str, Any] = {
            "success_event_types": p["success_types"],
            "failure_event_types": p["failure_types"],
        }
        if "anchor_field" in p and "window_value" in p:
            params["window"] = {
                "anchor_path": f"claim.{p['anchor_field']}",
                "value": p["window_value"],
                "unit": p.get("window_unit", "hours"),
                "start_exclusive": p.get("start_exclusive", False),
            }
        return Expression(operator="terminal_event_outcome", parameters=params)

    if ct == "field_mismatch":
        return Expression(
            operator="exists_event",
            parameters={
                "event_types": [p["event_type"]],
                "dynamic_field_match_mode": "any",
                "dynamic_field_equals": [
                    {
                        "event_field": comp["event_field"],
                        "claim_field": f"claim.{comp['claim_field']}",
                        "comparison": "not_equals",
                    }
                    for comp in p["comparisons"]
                    if isinstance(comp, dict)
                ],
            },
        )

    if ct == "duplicate_in_window":
        normalizers = p.get("normalizers", {})
        generic_normalizers = {
            f"claim.{field}": ("text" if name == "intent" else name)
            for field, name in normalizers.items()
        }
        return Expression(
            operator="unique_by",
            parameters={
                "fields": [f"claim.{f}" for f in p["group_by"]],
                "order_by": [f"claim.{f}" for f in p["order_by"]],
                "scope": "native_duplicate",
                "window": {
                    "value": p["window_value"],
                    "unit": p["window_unit"],
                },
                "group_normalizers": generic_normalizers,
            },
        )

    if ct == "count_events_exceeds":
        return Expression(
            operator="greater_than",
            operands=[
                Expression(
                    operator="count_events",
                    parameters={"event_types": p["event_types"]},
                ),
                _constant(p["threshold"]),
            ],
        )

    if ct == "all_of":
        sub_conditions = [ConditionProposal.model_validate(sub) for sub in p["conditions"]]
        return Expression(
            operator="and",
            operands=[_lower_condition(sub) for sub in sub_conditions],
        )

    if ct == "any_of":
        sub_conditions = [ConditionProposal.model_validate(sub) for sub in p["conditions"]]
        return Expression(
            operator="or",
            operands=[_lower_condition(sub) for sub in sub_conditions],
        )

    if ct == "none_of":
        sub_conditions = [ConditionProposal.model_validate(sub) for sub in p["conditions"]]
        inner = Expression(
            operator="or",
            operands=[_lower_condition(sub) for sub in sub_conditions],
        )
        return Expression(operator="not", operands=[inner])

    raise LoweringError(f"Unknown condition type: {ct}")


# ---------------------------------------------------------------------------
# M3: Definition and reference resolution
# ---------------------------------------------------------------------------


def _resolve_definitions(
    proposal: AgreementCompilationProposal,
    diagnostics: list[CompilerDiagnostic],
) -> dict[str, DefinitionProposal]:
    """Build term→definition map, flag conflicts."""
    definitions: dict[str, DefinitionProposal] = {}
    for defn in proposal.definitions:
        if defn.term in definitions:
            existing = definitions[defn.term]
            if existing.meaning != defn.meaning:
                diagnostics.append(
                    CompilerDiagnostic(
                        code="CONFLICTING_DEFINITION",
                        severity="blocking",
                        message=(
                            f"Term '{defn.term}' is defined differently in "
                            f"clauses {existing.source_clause_id} and {defn.source_clause_id}"
                        ),
                    )
                )
        definitions[defn.term] = defn
    return definitions


def _resolve_references(
    proposal: AgreementCompilationProposal,
    diagnostics: list[CompilerDiagnostic],
) -> None:
    """Check that all references are resolved, flag missing targets."""
    clause_ids = {c.clause_id for c in proposal.clauses}
    for clause in proposal.clauses:
        for ref in clause.references:
            if not ref.resolved and clause.material:
                diagnostics.append(
                    CompilerDiagnostic(
                        code="UNRESOLVED_REFERENCE",
                        severity="blocking",
                        message=(
                            f"Material clause {clause.clause_id} references "
                            f"unresolved {ref.reference_type}: '{ref.target}'"
                        ),
                        clause_ids=[f"NATIVE-{clause.clause_id}"],
                    )
                )
            if ref.resolved and ref.resolved_clause_id and ref.resolved_clause_id not in clause_ids:
                diagnostics.append(
                    CompilerDiagnostic(
                        code="DANGLING_REFERENCE",
                        severity="warning",
                        message=(
                            f"Reference from {clause.clause_id} resolves to "
                            f"{ref.resolved_clause_id} which is not in the proposal"
                        ),
                    )
                )
    # Check for circular references
    graph: dict[str, set[str]] = {}
    for clause in proposal.clauses:
        graph[clause.clause_id] = set()
        for ref in clause.references:
            if ref.resolved and ref.resolved_clause_id:
                graph[clause.clause_id].add(ref.resolved_clause_id)
    visited: set[str] = set()
    path: set[str] = set()

    def _has_cycle(node: str) -> bool:
        if node in path:
            return True
        if node in visited:
            return False
        visited.add(node)
        path.add(node)
        for neighbor in graph.get(node, set()):
            if _has_cycle(neighbor):
                return True
        path.discard(node)
        return False

    for node in graph:
        if _has_cycle(node):
            diagnostics.append(
                CompilerDiagnostic(
                    code="CIRCULAR_REFERENCE",
                    severity="blocking",
                    message=f"Circular clause reference detected involving {node}",
                )
            )
            break


# ---------------------------------------------------------------------------
# M4: Settlement lowering
# ---------------------------------------------------------------------------


def _lower_settlements(
    proposal: AgreementCompilationProposal,
    clauses: list[SourceClause],
    norms: list[Norm],
    diagnostics: list[CompilerDiagnostic],
) -> list[SettlementPolicy]:
    """Lower settlement proposals into SettlementPolicy objects."""
    policies: list[SettlementPolicy] = []
    clause_id_map = {c.clause_id: f"NATIVE-{c.clause_id}" for c in proposal.clauses}

    for clause in proposal.clauses:
        for settlement in clause.settlement_effects:
            source_id = clause_id_map.get(settlement.source_clause_id)
            if source_id is None:
                source_id = f"NATIVE-{settlement.source_clause_id}"

            eligibility_norm_ids = [n.id for n in norms if n.condition.operator != "unique_by"]

            try:
                amount_expr = _lower_settlement_expression(settlement)
            except LoweringError as exc:
                diagnostics.append(
                    CompilerDiagnostic(
                        code="SETTLEMENT_LOWERING_FAILED",
                        severity="blocking",
                        message=f"Settlement {settlement.id}: {exc}",
                        clause_ids=[source_id],
                    )
                )
                continue

            policies.append(
                SettlementPolicy(
                    id=f"SETTLEMENT-{settlement.id}",
                    claim_type="outcome",
                    eligibility_norm_ids=eligibility_norm_ids,
                    amount_expression=amount_expr,
                    source_clause_ids=[source_id],
                )
            )

    return policies


def _lower_settlement_expression(settlement: SettlementProposal) -> Expression:
    """Map a SettlementProposal to an executable Expression."""
    st = settlement.settlement_type
    p = settlement.parameters

    if st == "fixed_per_unit":
        quantity_field = p.get("quantity_field")
        if not quantity_field:
            return Expression(
                operator="multiply",
                operands=[_constant(p["unit_price"]), _constant("1")],
            )
        return Expression(
            operator="multiply",
            operands=[
                _constant(p["unit_price"]),
                Expression(operator="field", path=f"claim.{quantity_field}"),
            ],
        )

    if st == "rate_table":
        return Expression(
            operator="rate_table",
            path=f"claim.{p['lookup_field']}",
            parameters={
                "rates": p["rates"],
                "default": p.get("default", "0"),
            },
        )

    if st == "percentage":
        ratio = Decimal(str(p["percent"])) / Decimal(100)
        base_field = str(p.get("base_field", "billed_amount"))
        return Expression(
            operator="multiply",
            operands=[
                _field(f"claim.{base_field}"),
                _constant(format(ratio, "f")),
            ],
        )

    if st == "cap":
        base = p.get("base_expression")
        base_expr = (
            _lower_settlement_expression(
                SettlementProposal.model_validate(
                    {
                        "id": f"{settlement.id}-base",
                        "source_clause_id": settlement.source_clause_id,
                        "description": "base",
                        **base,
                    }
                )
            )
            if isinstance(base, dict)
            else _field("claim.billed_amount")
        )
        return Expression(
            operator="cap",
            operands=[base_expr, _constant(p["maximum"])],
        )

    if st in {"floor", "deduction"}:
        base = p.get("base_expression")
        base_expr = (
            _lower_settlement_expression(
                SettlementProposal.model_validate(
                    {
                        "id": f"{settlement.id}-base",
                        "source_clause_id": settlement.source_clause_id,
                        "description": "base",
                        **base,
                    }
                )
            )
            if isinstance(base, dict)
            else _field("claim.billed_amount")
        )
        if st == "floor":
            return Expression(
                operator="floor",
                operands=[base_expr, _constant(p["minimum"])],
            )
        return Expression(
            operator="subtract",
            operands=[base_expr, _constant(p["amount"])],
        )

    if st == "conditional_eligibility":
        eligible_field = str(p.get("eligible_flag_field", "eligible_flag"))
        return Expression(
            operator="multiply",
            operands=[
                _field("claim.billed_amount"),
                Expression(
                    operator="rate_table",
                    path=f"settlement.{eligible_field}",
                    parameters={"rates": {"true": "1", "false": "0"}, "default": "0"},
                ),
            ],
        )

    if st == "tiered_rate":
        return Expression(
            operator="tiered_rate",
            path=f"claim.{p.get('quantity_field', 'quantity')}",
            parameters={"tiers": p["tiers"]},
        )

    raise LoweringError(f"Unknown settlement type: {st}")


def _truth_value_for(value: str) -> Any:
    from .models import TruthValue

    return TruthValue.UNKNOWN if value == "unknown" else TruthValue(value)
