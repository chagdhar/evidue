"""Atomic contractual requirement coverage and AIR binding assurance.

The requirement ledger is intentionally separate from executable AIR semantics.
A model may identify what the contract says, but only the deterministic lowerer
can bind those source-grounded requirements to executable norms or settlement
policies.  Missing, collapsed, or data-source-incompatible bindings are blocking.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable

from .compiler_models import (
    AgreementCompilationProposal,
    AtomicRequirementProposal,
    ConditionProposal,
)
from .models import (
    AtomicRequirement,
    AutomationClass,
    CompilerDiagnostic,
    Norm,
    ProofRequirement,
    SettlementPolicy,
    SourceClause,
)

_EXECUTABLE_AUTOMATION = {
    AutomationClass.FULLY_EXECUTABLE,
    AutomationClass.EXECUTABLE_IF_DATA_AVAILABLE,
}


def requirement_id(value: str) -> str:
    return value if value.startswith("REQ-") else f"REQ-{value}"


def condition_data_dependencies(condition: ConditionProposal) -> set[str]:
    """Return runtime data classes actually consumed by a proposed condition."""

    ct = condition.condition_type
    if ct in {
        "field_present",
        "field_equals",
        "field_in_set",
        "datetime_in_range",
        "amount_equals",
    }:
        return {"claim"}
    if ct in {
        "event_exists",
        "event_absent",
        "event_within_window",
        "terminal_outcome",
        "field_mismatch",
        "count_events_exceeds",
    }:
        return {"customer_evidence"}
    if ct == "duplicate_in_window":
        return {"batch_claims"}
    if ct in {"all_of", "any_of", "none_of"}:
        dependencies: set[str] = set()
        for raw in condition.parameters.get("conditions", []):
            dependencies.update(condition_data_dependencies(ConditionProposal.model_validate(raw)))
        return dependencies
    return set()


def _source_clause_ids(
    requirement: AtomicRequirementProposal,
    clauses: list[SourceClause],
) -> list[str]:
    matches: list[str] = []
    requirement_spans = set(requirement.source_span_ids)
    for clause in clauses:
        if clause.document_id != requirement.source_document_id:
            continue
        if requirement_spans and requirement_spans.intersection(clause.source_span_ids):
            matches.append(clause.id)
            continue
        if (
            requirement.source_start is not None
            and requirement.source_end is not None
            and clause.source_start is not None
            and clause.source_end is not None
        ):
            overlaps = max(requirement.source_start, clause.source_start) < min(
                requirement.source_end, clause.source_end
            )
            if overlaps:
                matches.append(clause.id)
                continue
        requirement_text = " ".join(requirement.source_text.split())
        clause_text = " ".join(clause.text.split())
        if requirement_text and (
            requirement_text in clause_text or clause_text in requirement_text
        ):
            matches.append(clause.id)
    return matches


def _append(
    diagnostics: list[CompilerDiagnostic],
    *,
    code: str,
    message: str,
    clause_ids: Iterable[str] = (),
) -> None:
    diagnostics.append(
        CompilerDiagnostic(
            code=code,
            severity="blocking",
            message=message,
            clause_ids=list(dict.fromkeys(clause_ids)),
        )
    )


def lower_atomic_requirements(
    proposal: AgreementCompilationProposal,
    *,
    clauses: list[SourceClause],
    norms: list[Norm],
    proofs: list[ProofRequirement],
    settlement_policies: list[SettlementPolicy],
) -> tuple[list[AtomicRequirement], list[CompilerDiagnostic]]:
    """Lower the authoritative requirement ledger and verify every binding.

    Older stored AIR proposals may not contain a ledger; the new native compiler
    always supplies one.  Backward compatibility therefore treats an absent ledger
    as legacy rather than retroactively making historical AIR payloads invalid.
    """

    if not proposal.requirements:
        return [], []

    diagnostics: list[CompilerDiagnostic] = []
    proposal_requirements = {requirement_id(item.id): item for item in proposal.requirements}
    proofs_by_norm: dict[str, list[ProofRequirement]] = defaultdict(list)
    for proof in proofs:
        proofs_by_norm[proof.norm_id].append(proof)

    bound_norms_by_requirement: dict[str, list[Norm]] = defaultdict(list)
    for norm in norms:
        for req_id in norm.requirement_ids:
            bound_norms_by_requirement[req_id].append(norm)

    bound_policies_by_requirement: dict[str, list[SettlementPolicy]] = defaultdict(list)
    for policy in settlement_policies:
        for req_id in policy.requirement_ids:
            bound_policies_by_requirement[req_id].append(policy)

    bound_proofs_by_requirement: dict[str, list[ProofRequirement]] = defaultdict(list)
    for proof in proofs:
        for req_id in proof.requirement_ids:
            bound_proofs_by_requirement[req_id].append(proof)

    lowered: list[AtomicRequirement] = []
    for proposal_requirement in proposal.requirements:
        req_id = requirement_id(proposal_requirement.id)
        bound_norms = bound_norms_by_requirement.get(req_id, [])
        bound_policies = bound_policies_by_requirement.get(req_id, [])
        bound_proofs = bound_proofs_by_requirement.get(req_id, [])
        source_clause_ids = _source_clause_ids(proposal_requirement, clauses)

        if proposal_requirement.disposition == "norm":
            binding_status = (
                "mapped"
                if len(bound_norms) == 1 and not bound_policies
                else ("unmapped" if not bound_norms and not bound_policies else "invalid_binding")
            )
        elif proposal_requirement.disposition == "settlement":
            binding_status = (
                "mapped"
                if len(bound_policies) == 1 and not bound_norms
                else ("unmapped" if not bound_norms and not bound_policies else "invalid_binding")
            )
        elif proposal_requirement.disposition == "manual_review":
            binding_status = (
                "manual_review" if not bound_norms and not bound_policies else "invalid_binding"
            )
        elif proposal_requirement.disposition == "unresolved_dependency":
            binding_status = (
                "unresolved_dependency"
                if not bound_norms and not bound_policies
                else "invalid_binding"
            )
        else:
            binding_status = (
                "non_operational" if not bound_norms and not bound_policies else "invalid_binding"
            )

        lowered.append(
            AtomicRequirement(
                id=req_id,
                statement=proposal_requirement.statement,
                kind=proposal_requirement.kind,
                materiality=proposal_requirement.materiality,
                data_dependencies=proposal_requirement.data_dependencies,
                disposition=proposal_requirement.disposition,
                parameters=proposal_requirement.parameters,
                source_document_id=proposal_requirement.source_document_id,
                source_span_ids=proposal_requirement.source_span_ids,
                source_text=proposal_requirement.source_text,
                source_start=proposal_requirement.source_start,
                source_end=proposal_requirement.source_end,
                source_text_hash=proposal_requirement.source_text_hash,
                source_clause_ids=source_clause_ids,
                norm_ids=[item.id for item in bound_norms],
                settlement_policy_ids=[item.id for item in bound_policies],
                proof_requirement_ids=[item.id for item in bound_proofs],
                binding_status=binding_status,
            )
        )

        material = proposal_requirement.materiality in {"financial", "operational"}
        if material and not source_clause_ids:
            _append(
                diagnostics,
                code="ATOMIC_REQUIREMENT_SOURCE_UNREPRESENTED",
                message=(
                    f"Material atomic requirement {req_id} is not represented by any "
                    "compiled source clause."
                ),
            )

        if material and binding_status in {"unmapped", "invalid_binding"}:
            _append(
                diagnostics,
                code="ATOMIC_REQUIREMENT_UNMAPPED",
                message=(
                    f"Material atomic requirement {req_id} has disposition "
                    f"{proposal_requirement.disposition!r} but binding status "
                    f"{binding_status!r}."
                ),
                clause_ids=source_clause_ids,
            )

        if material and binding_status == "unresolved_dependency":
            _append(
                diagnostics,
                code="MATERIAL_REQUIREMENT_UNRESOLVED",
                message=(
                    f"Material atomic requirement {req_id} depends on contract data "
                    "that is not present in the supplied agreement packet."
                ),
                clause_ids=source_clause_ids,
            )

        if proposal_requirement.disposition in {
            "manual_review",
            "unresolved_dependency",
            "non_operational",
        } and (bound_norms or bound_policies):
            _append(
                diagnostics,
                code="NONEXECUTABLE_REQUIREMENT_HAS_EXECUTABLE_BINDING",
                message=(
                    f"Atomic requirement {req_id} is {proposal_requirement.disposition} "
                    "but was bound to executable AIR semantics."
                ),
                clause_ids=source_clause_ids,
            )

        declared_dependencies = set(proposal_requirement.data_dependencies)
        for norm in bound_norms:
            proposal_norm = next(
                (
                    item
                    for clause in proposal.clauses
                    for item in clause.norms
                    if f"NORM-{item.id}" == norm.id
                ),
                None,
            )
            if proposal_norm is None:
                continue
            actual_dependencies = condition_data_dependencies(proposal_norm.condition)
            runtime_dependencies = {
                item
                for item in actual_dependencies
                if item in {"claim", "batch_claims", "customer_evidence"}
            }
            missing_declarations = runtime_dependencies - declared_dependencies
            if missing_declarations:
                _append(
                    diagnostics,
                    code="REQUIREMENT_DATA_DEPENDENCY_MISMATCH",
                    message=(
                        f"Norm {norm.id} consumes {sorted(missing_declarations)} but {req_id} "
                        "does not declare those data dependencies."
                    ),
                    clause_ids=norm.source_clause_ids,
                )

            norm_proofs = proofs_by_norm.get(norm.id, [])
            uses_customer_evidence = "customer_evidence" in actual_dependencies
            if uses_customer_evidence and not norm_proofs:
                _append(
                    diagnostics,
                    code="EVIDENCE_REQUIREMENT_MISSING_PROOF",
                    message=(
                        f"Norm {norm.id} consumes customer evidence but has no proof requirement."
                    ),
                    clause_ids=norm.source_clause_ids,
                )
            if not uses_customer_evidence and norm_proofs:
                _append(
                    diagnostics,
                    code="DIRECT_DATA_REQUIREMENT_HAS_EXTERNAL_PROOF",
                    message=(
                        f"Norm {norm.id} is evaluable from claim/batch data and must not "
                        "depend on external evidence proof."
                    ),
                    clause_ids=norm.source_clause_ids,
                )
            if "customer_evidence" in declared_dependencies and not uses_customer_evidence:
                _append(
                    diagnostics,
                    code="REQUIREMENT_DATA_DEPENDENCY_MISMATCH",
                    message=(
                        f"Atomic requirement {req_id} declares customer_evidence but bound "
                        f"norm {norm.id} does not consume customer evidence."
                    ),
                    clause_ids=norm.source_clause_ids,
                )
            if {"external_document", "human_attestation"}.intersection(
                declared_dependencies
            ) and norm.automation_class in _EXECUTABLE_AUTOMATION:
                _append(
                    diagnostics,
                    code="UNSAFE_REQUIREMENT_AUTOMATION",
                    message=(
                        f"Norm {norm.id} automates {req_id} despite an external-document or "
                        "human-attestation dependency."
                    ),
                    clause_ids=norm.source_clause_ids,
                )

    # A material clause cannot look covered merely because one unrelated rule points at it.
    for clause in [item for item in clauses if item.material]:
        covered_requirements = [
            item
            for item in lowered
            if clause.id in item.source_clause_ids
            and item.materiality in {"financial", "operational"}
        ]
        if not covered_requirements:
            _append(
                diagnostics,
                code="MATERIAL_CLAUSE_WITHOUT_ATOMIC_REQUIREMENT",
                message=(
                    f"Material clause {clause.id} has no financial/operational atomic "
                    "requirement in the independent requirement ledger."
                ),
                clause_ids=[clause.id],
            )

    # Executable artifacts must be one-to-one with atomic requirements. This catches
    # the dangerous 'one generic rule represents five separate contract conditions' case.
    for norm in norms:
        if len(norm.requirement_ids) > 1:
            _append(
                diagnostics,
                code="ATOMIC_REQUIREMENTS_COLLAPSED",
                message=(
                    f"Norm {norm.id} collapses multiple atomic requirements: "
                    + ", ".join(norm.requirement_ids)
                ),
                clause_ids=norm.source_clause_ids,
            )
        if norm.automation_class in _EXECUTABLE_AUTOMATION and not norm.requirement_ids:
            _append(
                diagnostics,
                code="ORPHAN_EXECUTABLE_SEMANTICS",
                message=f"Executable norm {norm.id} has no atomic requirement binding.",
                clause_ids=norm.source_clause_ids,
            )
        for req_id in norm.requirement_ids:
            requirement = proposal_requirements.get(req_id)
            if requirement is None:
                continue
            allowed_clauses = set(_source_clause_ids(requirement, clauses))
            if allowed_clauses and not allowed_clauses.intersection(norm.source_clause_ids):
                _append(
                    diagnostics,
                    code="REQUIREMENT_SOURCE_BINDING_MISMATCH",
                    message=(
                        f"Norm {norm.id} is bound to {req_id} but grounded in a different "
                        "source clause."
                    ),
                    clause_ids=norm.source_clause_ids,
                )

    for policy in settlement_policies:
        if len(policy.requirement_ids) > 1:
            _append(
                diagnostics,
                code="ATOMIC_REQUIREMENTS_COLLAPSED",
                message=(
                    f"Settlement policy {policy.id} collapses multiple atomic requirements: "
                    + ", ".join(policy.requirement_ids)
                ),
                clause_ids=policy.source_clause_ids,
            )
        if not policy.requirement_ids:
            _append(
                diagnostics,
                code="ORPHAN_EXECUTABLE_SEMANTICS",
                message=f"Settlement policy {policy.id} has no atomic requirement binding.",
                clause_ids=policy.source_clause_ids,
            )

    return lowered, diagnostics
