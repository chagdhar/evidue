from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class TruthValue(StrEnum):
    TRUE = "true"
    FALSE = "false"
    UNKNOWN = "unknown"
    CONFLICTING = "conflicting"


class ObligationStatus(StrEnum):
    SATISFIED = "satisfied"
    VIOLATED = "violated"
    INDETERMINATE = "indeterminate"
    NOT_APPLICABLE = "not_applicable"


class NormType(StrEnum):
    OBLIGATION = "obligation"
    PROHIBITION = "prohibition"
    PERMISSION = "permission"
    ENTITLEMENT = "entitlement"
    DECLARATION = "declaration"
    DEFINITION = "definition"
    REMEDY = "remedy"
    PROCEDURE = "procedure"


class AutomationClass(StrEnum):
    FULLY_EXECUTABLE = "fully_executable"
    EXECUTABLE_IF_DATA_AVAILABLE = "executable_if_data_available"
    MODEL_ASSISTED = "model_assisted"
    HUMAN_ATTESTATION_REQUIRED = "human_attestation_required"
    PROCEDURAL_ONLY = "procedural_only"
    NON_OPERATIONAL = "non_operational"
    UNSUPPORTED = "unsupported"


class EvidenceAuthority(StrEnum):
    CUSTOMER_SYSTEM_OF_RECORD = "customer_system_of_record"
    INDEPENDENT_THIRD_PARTY = "independent_third_party"
    SIGNED_EXECUTION_LOG = "signed_execution_log"
    VENDOR_TOOL_TRACE = "vendor_tool_trace"
    CONVERSATION_TRANSCRIPT = "conversation_transcript"
    MODEL_DERIVED = "model_derived"
    VENDOR_ASSERTION = "vendor_assertion"
    HUMAN_ATTESTATION = "human_attestation"


RequirementKind = Literal[
    "eligibility",
    "pricing",
    "exclusion",
    "performance",
    "identity",
    "uniqueness",
    "timing",
    "evidence",
    "procedure",
    "other",
]
RequirementMateriality = Literal["financial", "operational", "supporting", "non_material"]
RequirementDataDependency = Literal[
    "claim",
    "invoice",
    "contract_constant",
    "batch_claims",
    "customer_evidence",
    "external_document",
    "human_attestation",
]
RequirementDisposition = Literal[
    "norm",
    "settlement",
    "manual_review",
    "unresolved_dependency",
    "non_operational",
]
RequirementBindingStatus = Literal[
    "mapped",
    "unmapped",
    "invalid_binding",
    "manual_review",
    "unresolved_dependency",
    "non_operational",
]


ExpressionOperator = Literal[
    "constant",
    "field",
    "fact",
    "present",
    "and",
    "or",
    "not",
    "implies",
    "equals",
    "not_equals",
    "less_than",
    "less_than_or_equal",
    "greater_than",
    "greater_than_or_equal",
    "in",
    "exists_event",
    "not_exists_event",
    "terminal_event_outcome",
    "count_events",
    "within",
    "state_equals",
    "unique_by",
    "add",
    "subtract",
    "multiply",
    "divide",
    "sum",
    "minimum",
    "maximum",
    "rate_table",
    "tiered_rate",
    "cap",
    "floor",
]


class Expression(BaseModel):
    """Small compositional AST used by the contract-agnostic verification runtime."""

    model_config = ConfigDict(extra="forbid")

    operator: ExpressionOperator
    operands: list[Expression] = Field(default_factory=list)
    value: Any | None = None
    path: str | None = None
    parameters: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_shape(self) -> Expression:
        if self.operator in {"field", "fact"} and not self.path:
            raise ValueError(f"{self.operator} requires path")
        if self.operator == "constant" and self.value is None:
            raise ValueError("constant requires value")
        exact_operands = {
            "not": 1,
            "implies": 2,
            "equals": 2,
            "not_equals": 2,
            "less_than": 2,
            "less_than_or_equal": 2,
            "greater_than": 2,
            "greater_than_or_equal": 2,
            "in": 2,
            "within": 3,
            "subtract": 2,
            "divide": 2,
            "cap": 2,
            "floor": 2,
        }
        expected = exact_operands.get(self.operator)
        if expected is not None and len(self.operands) != expected:
            raise ValueError(f"{self.operator} requires exactly {expected} operands")
        if (
            self.operator
            in {
                "and",
                "or",
                "add",
                "multiply",
                "sum",
                "minimum",
                "maximum",
            }
            and not self.operands
        ):
            raise ValueError(f"{self.operator} requires at least one operand")
        if self.operator in {
            "exists_event",
            "not_exists_event",
            "terminal_event_outcome",
            "count_events",
        }:
            if self.operator == "terminal_event_outcome":
                success_types = self.parameters.get("success_event_types")
                failure_types = self.parameters.get("failure_event_types")
                if not success_types or not failure_types:
                    raise ValueError(
                        "terminal_event_outcome requires success_event_types and "
                        "failure_event_types"
                    )
            elif not self.parameters.get("event_types"):
                raise ValueError(f"{self.operator} requires event_types")
            window = self.parameters.get("window")
            if window is not None and (
                not isinstance(window, dict) or "anchor_path" not in window or "value" not in window
            ):
                raise ValueError(f"{self.operator} window requires anchor_path and value")
            dynamic = self.parameters.get("dynamic_field_equals")
            if dynamic is not None:
                if not isinstance(dynamic, list) or not dynamic:
                    raise ValueError(
                        f"{self.operator} dynamic_field_equals must be a non-empty list"
                    )
                for pair in dynamic:
                    if (
                        not isinstance(pair, dict)
                        or "event_field" not in pair
                        or "claim_field" not in pair
                    ):
                        raise ValueError(
                            f"{self.operator} dynamic_field_equals entries require "
                            "event_field and claim_field"
                        )
        if self.operator == "present" and len(self.operands) != 1:
            raise ValueError("present requires exactly one operand")
        if self.operator == "state_equals" and not self.path:
            raise ValueError("state_equals requires path")
        if self.operator == "unique_by" and not self.parameters.get("fields"):
            raise ValueError("unique_by requires fields")
        if self.operator == "rate_table" and (
            not self.path or not isinstance(self.parameters.get("rates"), dict)
        ):
            raise ValueError("rate_table requires path and rates")
        if self.operator == "tiered_rate":
            if not self.path:
                raise ValueError("tiered_rate requires a quantity path")
            tiers = self.parameters.get("tiers")
            if not isinstance(tiers, list) or not tiers:
                raise ValueError("tiered_rate requires tiers")
        return self


class SourceClause(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    document_id: str
    text: str
    material: bool = True
    source_start: int | None = None
    source_end: int | None = None
    text_hash: str | None = None
    source_span_ids: list[str] = Field(default_factory=list)


class ClauseCoverage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    clause_id: str
    clause_text: str
    classification: AutomationClass
    norm_ids: list[str] = Field(default_factory=list)
    rationale: str
    material: bool = True


class CompilerDiagnostic(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    severity: Literal["info", "warning", "blocking"]
    message: str
    clause_ids: list[str] = Field(default_factory=list)


class AtomicRequirement(BaseModel):
    """One indivisible, source-grounded contractual requirement.

    The requirement ledger is interpretation metadata, not executable authority.
    Executable financial authority remains in approved norms and settlement policies.
    """

    model_config = ConfigDict(extra="forbid")

    id: str
    statement: str
    kind: RequirementKind
    materiality: RequirementMateriality
    data_dependencies: list[RequirementDataDependency] = Field(default_factory=list)
    disposition: RequirementDisposition
    parameters: dict[str, Any] = Field(default_factory=dict)
    source_document_id: str
    source_span_ids: list[str] = Field(default_factory=list)
    source_text: str
    source_start: int | None = None
    source_end: int | None = None
    source_text_hash: str | None = None
    source_clause_ids: list[str] = Field(default_factory=list)
    norm_ids: list[str] = Field(default_factory=list)
    settlement_policy_ids: list[str] = Field(default_factory=list)
    proof_requirement_ids: list[str] = Field(default_factory=list)
    binding_status: RequirementBindingStatus = "unmapped"


class AtomicPredicate(BaseModel):
    """Source-bound, deterministic boolean predicate used by proof planning and fact derivation."""

    model_config = ConfigDict(extra="forbid")

    id: str
    norm_id: str
    description: str
    expression: Expression
    source_clause_ids: list[str]
    automation_class: AutomationClass
    value_type: Literal["boolean"] = "boolean"
    canonical_hash: str


class ProofRequirement(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    norm_id: str
    predicate_id: str
    description: str
    acceptable_fact_types: list[str]
    preferred_authority: EvidenceAuthority
    acceptable_authorities: list[EvidenceAuthority]
    identity_keys: list[str] = Field(default_factory=list)
    required_entity_type: str | None = None
    required_fields: list[str] = Field(default_factory=list)
    observation_window: dict[str, Any] = Field(default_factory=dict)
    requires_absence_proof: bool = False
    missing_evidence_result: TruthValue = TruthValue.UNKNOWN
    conflict_result: TruthValue = TruthValue.CONFLICTING
    requirement_ids: list[str] = Field(default_factory=list)


class Norm(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    norm_type: NormType
    subject: str
    beneficiary: str | None = None
    trigger: Expression | None = None
    condition: Expression
    exceptions: list[Expression] = Field(default_factory=list)
    consequence: str
    source_clause_ids: list[str]
    automation_class: AutomationClass
    legacy_rule_id: str | None = None
    violation_reason_code: str | None = None
    indeterminate_reason_code: str | None = None
    violation_reason: str | None = None
    indeterminate_reason: str | None = None
    indeterminate_consequence: Literal["payable", "disputed", "needs_review"] = "needs_review"
    indeterminate_rule_id: str | None = None
    requirement_ids: list[str] = Field(default_factory=list)


class SettlementPolicy(BaseModel):
    """Contract-agnostic expression that calculates the payable amount for a claim."""

    model_config = ConfigDict(extra="forbid")

    id: str
    claim_type: str
    eligibility_norm_ids: list[str] = Field(default_factory=list)
    amount_expression: Expression
    source_clause_ids: list[str]
    currency: str = Field(default="USD", min_length=3, max_length=3)
    requirement_ids: list[str] = Field(default_factory=list)


class Fact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    fact_type: str
    predicate_id: str | None = None
    truth: TruthValue
    value: Any | None = None
    evidence_ids: list[str] = Field(default_factory=list)
    authority: EvidenceAuthority
    input_hash: str | None = None
    evaluator_version: str | None = None


class EvidenceArtifact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    source_id: str
    artifact_type: str
    payload_hash: str
    authority: EvidenceAuthority
    observed_at: str | None = None


class Observation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    artifact_id: str
    observation_type: str
    entity_id: str | None = None
    values: dict[str, Any] = Field(default_factory=dict)
    normalizer_version: str


class ProvenanceEdge(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_id: str
    target_id: str
    relation: Literal["derived_from", "generated_by", "attributed_to", "supports", "contradicts"]


class WorkGraph(BaseModel):
    model_config = ConfigDict(extra="forbid")

    artifacts: list[EvidenceArtifact] = Field(default_factory=list)
    observations: list[Observation] = Field(default_factory=list)
    facts: list[Fact] = Field(default_factory=list)
    provenance: list[ProvenanceEdge] = Field(default_factory=list)


class CommercialClaim(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    claim_type: str
    submitted_amount: str
    fields: dict[str, Any] = Field(default_factory=dict)


class SettlementLine(BaseModel):
    model_config = ConfigDict(extra="forbid")

    claim_id: str
    submitted_amount: str
    payable_amount: str
    disputed_amount: str
    needs_review_amount: str
    status: Literal["payable", "disputed", "needs_review"]
    explanation: str


class AgreementIR(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = "air-0.1"
    agreement_id: str
    source_hash: str
    clauses: list[SourceClause]
    requirements: list[AtomicRequirement] = Field(default_factory=list)
    norms: list[Norm]
    predicates: list[AtomicPredicate] = Field(default_factory=list)
    proof_requirements: list[ProofRequirement]
    settlement_policies: list[SettlementPolicy] = Field(default_factory=list)
    coverage: list[ClauseCoverage]
    diagnostics: list[CompilerDiagnostic] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_references(self) -> AgreementIR:
        clause_ids = [item.id for item in self.clauses]
        requirement_ids = [item.id for item in self.requirements]
        norm_ids = [item.id for item in self.norms]
        predicate_ids = [item.id for item in self.predicates]
        proof_ids = [item.id for item in self.proof_requirements]
        policy_ids = [item.id for item in self.settlement_policies]
        for label, values in {
            "clause": clause_ids,
            "atomic requirement": requirement_ids,
            "norm": norm_ids,
            "predicate": predicate_ids,
            "proof requirement": proof_ids,
            "settlement policy": policy_ids,
        }.items():
            if len(values) != len(set(values)):
                raise ValueError(f"Agreement IR {label} IDs must be unique")

        known_clauses = set(clause_ids)
        known_requirements = set(requirement_ids)
        known_norms = set(norm_ids)
        known_predicates = set(predicate_ids)
        for requirement in self.requirements:
            unknown_clauses = set(requirement.source_clause_ids) - known_clauses
            unknown_norms = set(requirement.norm_ids) - known_norms
            unknown_policies = set(requirement.settlement_policy_ids) - set(policy_ids)
            unknown_proofs = set(requirement.proof_requirement_ids) - set(proof_ids)
            if unknown_clauses:
                raise ValueError(
                    f"Atomic requirement {requirement.id} references unknown clauses: "
                    f"{sorted(unknown_clauses)}"
                )
            if unknown_norms:
                raise ValueError(
                    f"Atomic requirement {requirement.id} references unknown norms: "
                    f"{sorted(unknown_norms)}"
                )
            if unknown_policies:
                raise ValueError(
                    f"Atomic requirement {requirement.id} references unknown settlement policies: "
                    f"{sorted(unknown_policies)}"
                )
            if unknown_proofs:
                raise ValueError(
                    f"Atomic requirement {requirement.id} references unknown proof requirements: "
                    f"{sorted(unknown_proofs)}"
                )
        for predicate in self.predicates:
            if predicate.norm_id not in known_norms:
                raise ValueError(
                    f"Predicate {predicate.id} references unknown norm {predicate.norm_id}"
                )
            unknown = set(predicate.source_clause_ids) - known_clauses
            if unknown:
                raise ValueError(
                    f"Predicate {predicate.id} references unknown clauses: {sorted(unknown)}"
                )
        for norm in self.norms:
            unknown = set(norm.source_clause_ids) - known_clauses
            if unknown:
                raise ValueError(f"Norm {norm.id} references unknown clauses: {sorted(unknown)}")
            unknown_requirements = set(norm.requirement_ids) - known_requirements
            if unknown_requirements:
                raise ValueError(
                    f"Norm {norm.id} references unknown atomic requirements: "
                    f"{sorted(unknown_requirements)}"
                )
        predicate_by_id = {item.id: item for item in self.predicates}
        for requirement in self.proof_requirements:
            if requirement.norm_id not in known_norms:
                raise ValueError(
                    f"Proof requirement {requirement.id} references unknown norm "
                    f"{requirement.norm_id}"
                )
            if known_predicates and requirement.predicate_id not in known_predicates:
                raise ValueError(
                    f"Proof requirement {requirement.id} references unknown predicate "
                    f"{requirement.predicate_id}"
                )
            predicate = predicate_by_id.get(requirement.predicate_id)
            if predicate is not None and predicate.norm_id != requirement.norm_id:
                raise ValueError(f"Proof requirement {requirement.id} predicate/norm mismatch")
            unknown_requirements = set(requirement.requirement_ids) - known_requirements
            if unknown_requirements:
                raise ValueError(
                    f"Proof requirement {requirement.id} references unknown atomic requirements: "
                    f"{sorted(unknown_requirements)}"
                )
        for item in self.coverage:
            if item.clause_id not in known_clauses:
                raise ValueError(f"Coverage references unknown clause {item.clause_id}")
            unknown = set(item.norm_ids) - known_norms
            if unknown:
                raise ValueError(
                    f"Coverage for {item.clause_id} references unknown norms: {sorted(unknown)}"
                )
        for policy in self.settlement_policies:
            unknown_norms = set(policy.eligibility_norm_ids) - known_norms
            unknown_clauses = set(policy.source_clause_ids) - known_clauses
            if unknown_norms:
                raise ValueError(
                    f"Settlement policy {policy.id} references unknown norms: "
                    f"{sorted(unknown_norms)}"
                )
            if unknown_clauses:
                raise ValueError(
                    f"Settlement policy {policy.id} references unknown clauses: "
                    f"{sorted(unknown_clauses)}"
                )
            unknown_requirements = set(policy.requirement_ids) - known_requirements
            if unknown_requirements:
                raise ValueError(
                    f"Settlement policy {policy.id} references unknown atomic requirements: "
                    f"{sorted(unknown_requirements)}"
                )
        for diagnostic in self.diagnostics:
            unknown = set(diagnostic.clause_ids) - known_clauses
            if unknown:
                raise ValueError(
                    f"Diagnostic {diagnostic.code} references unknown clauses: {sorted(unknown)}"
                )
        return self


class ConformanceReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    agreement_id: str
    material_clause_count: int
    covered_material_clause_count: int
    fully_executable_count: int
    data_dependent_count: int
    model_assisted_count: int
    human_attestation_count: int
    procedural_count: int
    non_operational_count: int
    unsupported_count: int
    unrepresented_material_clause_count: int
    norm_count: int
    predicate_count: int = 0
    orphan_proof_requirement_count: int = 0
    proof_requirement_count: int
    settlement_policy_count: int
    atomic_requirement_count: int = 0
    mapped_atomic_requirement_count: int = 0
    unmapped_material_requirement_count: int = 0
    blocking_diagnostic_count: int
    approvable: bool
    coverage_percent: float
