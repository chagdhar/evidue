"""Deterministic assurance gates for approved Agreement IR.

This module deliberately does not ask another LLM to declare a compilation
"correct".  It proves the properties Evidue can verify mechanically: source
grounding, complete material coverage, referential integrity, predicate
fingerprints, pricing provenance, and executable runtime behavior.  Human
review remains responsible for the semantic meaning of the source language.
"""

from __future__ import annotations

import json
from copy import deepcopy
from hashlib import sha256
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from .legacy import conformance_report
from .models import AgreementIR, AtomicPredicate
from .runtime import EvaluationContext, evaluate_expression

ASSURANCE_VERSION = "compiler-assurance-v1"


class AssuranceCheck(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    status: Literal["pass", "fail", "review"]
    hard_gate: bool = True
    summary: str
    details: list[str] = Field(default_factory=list)


class ExecutionProbe(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    predicate_id: str
    status: Literal["pass", "fail"]
    observed_truth: str | None = None
    detail: str


class MutationProbe(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    predicate_id: str
    status: Literal["pass", "fail", "not_applicable"]
    original_hash: str
    mutated_hash: str | None = None
    detail: str


class CompilerAssuranceReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    assurance_version: str = ASSURANCE_VERSION
    agreement_id: str
    source_hash: str
    checks: list[AssuranceCheck]
    execution_probes: list[ExecutionProbe]
    mutation_probes: list[MutationProbe]
    hard_gate_passed: bool
    review_required: bool


def _canonical_hash(payload: object) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()
    return "sha256:" + sha256(encoded).hexdigest()


def _predicate_hash(predicate: AtomicPredicate) -> str:
    return _canonical_hash(predicate.expression.model_dump(mode="json"))


def _mutated_expression_payload(predicate: AtomicPredicate) -> dict[str, Any] | None:
    """Create a deterministic semantic mutation for common contract constants."""

    payload = deepcopy(predicate.expression.model_dump(mode="json"))

    def visit(node: Any) -> bool:
        if isinstance(node, dict):
            params = node.get("parameters")
            if isinstance(params, dict):
                window = params.get("window")
                if isinstance(window, dict) and isinstance(window.get("value"), (int, float, str)):
                    value = window["value"]
                    try:
                        window["value"] = (
                            str(float(value) + 1) if isinstance(value, str) else value + 1
                        )
                    except (TypeError, ValueError):
                        pass
                    else:
                        return True
                rates = params.get("rates")
                if isinstance(rates, dict) and rates:
                    key = min(rates)
                    try:
                        rates[key] = str(float(rates[key]) + 1)
                    except (TypeError, ValueError):
                        pass
                    else:
                        return True
            if node.get("operator") == "constant" and node.get("value") is not None:
                value = node["value"]
                if isinstance(value, bool):
                    node["value"] = not value
                    return True
                if isinstance(value, (int, float)):
                    node["value"] = value + 1
                    return True
                if isinstance(value, str):
                    try:
                        node["value"] = str(float(value) + 1)
                    except ValueError:
                        pass
                    else:
                        return True
            for value in node.values():
                if visit(value):
                    return True
        elif isinstance(node, list):
            for value in node:
                if visit(value):
                    return True
        return False

    return payload if visit(payload) else None


def assure_agreement(agreement: AgreementIR) -> CompilerAssuranceReport:
    report = conformance_report(agreement)
    clause_by_id = {clause.id: clause for clause in agreement.clauses}
    predicate_by_id = {predicate.id: predicate for predicate in agreement.predicates}
    checks: list[AssuranceCheck] = []

    ungrounded: list[str] = []
    for clause in agreement.clauses:
        if not clause.material:
            continue
        expected_hash = sha256(clause.text.encode("utf-8")).hexdigest()
        has_valid_span = (
            clause.source_start is not None
            and clause.source_end is not None
            and clause.source_start >= 0
            and clause.source_end > clause.source_start
            and clause.source_end - clause.source_start == len(clause.text)
        )
        if not has_valid_span or clause.text_hash != expected_hash:
            ungrounded.append(clause.id)
    checks.append(
        AssuranceCheck(
            id="source_grounding",
            status="fail" if ungrounded else "pass",
            summary=(
                "Every material clause is bound to an exact source span and hash."
                if not ungrounded
                else "Some material clauses are not exact-span source bound."
            ),
            details=ungrounded,
        )
    )

    coverage_failures: list[str] = []
    if report.coverage_percent != 100.0:
        coverage_failures.append(f"material coverage is {report.coverage_percent}%")
    if report.blocking_diagnostic_count:
        coverage_failures.append(f"{report.blocking_diagnostic_count} blocking diagnostic(s)")
    if report.unsupported_count:
        coverage_failures.append(f"{report.unsupported_count} unsupported clause(s)")
    if report.unrepresented_material_clause_count:
        coverage_failures.append(
            f"{report.unrepresented_material_clause_count} unrepresented material clause(s)"
        )
    checks.append(
        AssuranceCheck(
            id="material_coverage",
            status="fail" if coverage_failures else "pass",
            summary="Material contract coverage passes the deterministic conformance gate."
            if not coverage_failures
            else "Material contract coverage is incomplete.",
            details=coverage_failures,
        )
    )

    predicate_failures: list[str] = []
    for requirement in agreement.proof_requirements:
        predicate = predicate_by_id.get(requirement.predicate_id)
        if predicate is None:
            predicate_failures.append(
                f"{requirement.id}: missing predicate {requirement.predicate_id}"
            )
            continue
        if predicate.norm_id != requirement.norm_id:
            predicate_failures.append(f"{requirement.id}: predicate/norm mismatch")
        if predicate.canonical_hash != _predicate_hash(predicate):
            predicate_failures.append(f"{predicate.id}: canonical hash mismatch")
        if not set(predicate.source_clause_ids).issubset(clause_by_id):
            predicate_failures.append(f"{predicate.id}: unknown source clause")
    checks.append(
        AssuranceCheck(
            id="predicate_integrity",
            status="fail" if predicate_failures else "pass",
            summary="Proof requirements resolve to immutable deterministic predicates."
            if not predicate_failures
            else "Proof-to-predicate integrity failed.",
            details=predicate_failures,
        )
    )

    pricing_failures: list[str] = []
    for policy in agreement.settlement_policies:
        if not policy.source_clause_ids:
            pricing_failures.append(f"{policy.id}: no source clauses")
        for clause_id in policy.source_clause_ids:
            clause = clause_by_id.get(clause_id)
            if clause is None:
                pricing_failures.append(f"{policy.id}: unknown source clause {clause_id}")
            elif not clause.text.strip():
                pricing_failures.append(f"{policy.id}: empty source clause {clause_id}")
    checks.append(
        AssuranceCheck(
            id="settlement_provenance",
            status="fail" if pricing_failures else "pass",
            summary="Every settlement rule is traceable to contract source language."
            if not pricing_failures
            else "Settlement source provenance is incomplete.",
            details=pricing_failures,
        )
    )

    execution_probes: list[ExecutionProbe] = []
    context = EvaluationContext(fields={"claim": {}, "settlement": {}}, events=())
    for predicate in agreement.predicates:
        try:
            result = evaluate_expression(predicate.expression, context)
            observed = result.truth.value if result.truth is not None else None
            execution_probes.append(
                ExecutionProbe(
                    id=f"EXEC-{predicate.id}",
                    predicate_id=predicate.id,
                    status="pass",
                    observed_truth=observed,
                    detail="Expression executes safely against an evidence-empty boundary context.",
                )
            )
        except (ArithmeticError, IndexError, KeyError, TypeError, ValueError) as exc:
            execution_probes.append(
                ExecutionProbe(
                    id=f"EXEC-{predicate.id}",
                    predicate_id=predicate.id,
                    status="fail",
                    detail=f"Expression raised {type(exc).__name__}: {exc}",
                )
            )
    failed_execution = [probe.id for probe in execution_probes if probe.status == "fail"]
    checks.append(
        AssuranceCheck(
            id="execution_boundary_probes",
            status="fail" if failed_execution else "pass",
            summary="Generated predicate execution probes are safe at missing-evidence boundaries."
            if not failed_execution
            else "One or more generated execution probes failed.",
            details=failed_execution,
        )
    )

    mutation_probes: list[MutationProbe] = []
    for predicate in agreement.predicates:
        mutated = _mutated_expression_payload(predicate)
        if mutated is None:
            mutation_probes.append(
                MutationProbe(
                    id=f"MUT-{predicate.id}",
                    predicate_id=predicate.id,
                    status="not_applicable",
                    original_hash=predicate.canonical_hash,
                    detail="Predicate contains no supported scalar contract constant to mutate.",
                )
            )
            continue
        mutated_hash = _canonical_hash(mutated)
        mutation_probes.append(
            MutationProbe(
                id=f"MUT-{predicate.id}",
                predicate_id=predicate.id,
                status="pass" if mutated_hash != predicate.canonical_hash else "fail",
                original_hash=predicate.canonical_hash,
                mutated_hash=mutated_hash,
                detail="A deterministic contract-constant mutation changes the predicate fingerprint.",
            )
        )
    mutation_failures = [probe.id for probe in mutation_probes if probe.status == "fail"]
    checks.append(
        AssuranceCheck(
            id="metamorphic_fingerprint",
            status="fail" if mutation_failures else "pass",
            hard_gate=True,
            summary="Supported semantic constant mutations change the compiled predicate fingerprint."
            if not mutation_failures
            else "A semantic constant mutation failed to change the predicate fingerprint.",
            details=mutation_failures,
        )
    )

    semantic_review = [
        item.clause_id
        for item in agreement.coverage
        if item.material
        and item.classification.value
        in {"model_assisted", "human_attestation_required", "procedural_only"}
    ]
    checks.append(
        AssuranceCheck(
            id="semantic_review_boundary",
            status="review" if semantic_review else "pass",
            hard_gate=False,
            summary="Human semantic review is required for clauses outside deterministic execution."
            if semantic_review
            else "No material clause requires model/human semantic attestation.",
            details=semantic_review,
        )
    )

    hard_gate_passed = all(check.status == "pass" for check in checks if check.hard_gate)
    return CompilerAssuranceReport(
        agreement_id=agreement.agreement_id,
        source_hash=agreement.source_hash,
        checks=checks,
        execution_probes=execution_probes,
        mutation_probes=mutation_probes,
        hard_gate_passed=hard_gate_passed,
        review_required=any(check.status == "review" for check in checks),
    )
