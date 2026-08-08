"""Native clause-analysis proposal schema.

These models define the structured output an LLM must produce when analyzing
a commercial agreement. The LLM proposes semantic structure — condition types,
norm types, settlement types — but never expression trees, executable code,
or financial determinations.

A deterministic lowerer (agreements/compiler.py) converts validated proposals
into executable AgreementIR. The LLM never sees Expression operators.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

# ---------------------------------------------------------------------------
# Allowed vocabularies — the LLM can ONLY use these
# ---------------------------------------------------------------------------

AllowedConditionType = Literal[
    "field_present",
    "field_equals",
    "field_in_set",
    "datetime_in_range",
    "amount_equals",
    "event_exists",
    "event_absent",
    "event_within_window",
    "terminal_outcome",
    "field_mismatch",
    "duplicate_in_window",
    "count_events_exceeds",
    "all_of",
    "any_of",
    "none_of",
]

AllowedSettlementType = Literal[
    "fixed_per_unit",
    "rate_table",
    "tiered_rate",
    "percentage",
    "cap",
    "floor",
    "deduction",
    "conditional_eligibility",
]

AllowedNormType = Literal[
    "obligation",
    "prohibition",
    "permission",
    "entitlement",
    "declaration",
    "definition",
    "remedy",
    "procedure",
]

AllowedConsequence = Literal["payable", "disputed", "needs_review"]

AllowedClauseType = Literal[
    "pricing",
    "performance",
    "quality",
    "timing",
    "scope",
    "definition",
    "procedural",
    "boilerplate",
]

AllowedAutomationClass = Literal[
    "fully_executable",
    "executable_if_data_available",
    "model_assisted",
    "human_attestation_required",
    "procedural_only",
    "non_operational",
    "unsupported",
]

AllowedDiagnosticSeverity = Literal["info", "warning", "blocking"]

AllowedEvidenceAuthority = Literal[
    "customer_system_of_record",
    "independent_third_party",
    "signed_execution_log",
    "vendor_tool_trace",
]


AllowedRequirementKind = Literal[
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
AllowedRequirementMateriality = Literal["financial", "operational", "supporting", "non_material"]
AllowedRequirementDataDependency = Literal[
    "claim",
    "invoice",
    "contract_constant",
    "batch_claims",
    "customer_evidence",
    "external_document",
    "human_attestation",
]
AllowedRequirementDisposition = Literal[
    "norm",
    "settlement",
    "manual_review",
    "unresolved_dependency",
    "non_operational",
]


def _reject_unknown_keys(parameters: dict[str, Any], allowed: set[str], label: str) -> None:
    unknown = sorted(set(parameters) - allowed)
    if unknown:
        raise ValueError(f"{label} contains unsupported parameters: {unknown}")


def _decimal_string(value: Any, label: str) -> str:
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError(f"{label} must be a decimal value") from exc
    if not amount.is_finite():
        raise ValueError(f"{label} must be finite")
    return format(amount, "f")


# ---------------------------------------------------------------------------
# Sub-proposal models
# ---------------------------------------------------------------------------


class AtomicRequirementProposal(BaseModel):
    """One indivisible source-grounded contractual requirement.

    This is produced by the independent requirement-decomposition pass. The
    downstream clause compiler may bind it to executable AIR semantics but may
    not merge, delete, or rewrite the requirement itself.
    """

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, max_length=50)
    statement: str = Field(min_length=1, max_length=1200)
    kind: AllowedRequirementKind
    materiality: AllowedRequirementMateriality
    data_dependencies: list[AllowedRequirementDataDependency] = Field(default_factory=list)
    disposition: AllowedRequirementDisposition
    parameters: dict[str, Any] = Field(default_factory=dict)
    source_document_id: str
    source_span_ids: list[str] = Field(default_factory=list, max_length=6)
    source_text: str = Field(min_length=1, max_length=5000)
    source_start: int | None = Field(default=None, ge=0)
    source_end: int | None = Field(default=None, ge=1)
    source_text_hash: str | None = Field(default=None, min_length=64, max_length=64)
    review_notes: list[str] = Field(default_factory=list)

    @field_validator("data_dependencies")
    @classmethod
    def dependencies_unique(
        cls, values: list[AllowedRequirementDataDependency]
    ) -> list[AllowedRequirementDataDependency]:
        if len(values) != len(set(values)):
            raise ValueError("Atomic requirement data_dependencies must be unique")
        return values


class RequirementLedgerProposal(BaseModel):
    """Authoritative output of the independent atomic-requirement pass."""

    model_config = ConfigDict(extra="forbid")

    ledger_version: str = Field(min_length=1)
    contract_id: str = Field(min_length=1)
    requirements: list[AtomicRequirementProposal] = Field(default_factory=list)

    @field_validator("requirements")
    @classmethod
    def requirement_ids_unique(
        cls, values: list[AtomicRequirementProposal]
    ) -> list[AtomicRequirementProposal]:
        ids = [item.id for item in values]
        if len(ids) != len(set(ids)):
            raise ValueError("Atomic requirement IDs must be unique")
        return values


class DefinitionProposal(BaseModel):
    """A defined term extracted from the agreement."""

    model_config = ConfigDict(extra="forbid")

    term: str = Field(min_length=1, max_length=200)
    meaning: str = Field(min_length=1, max_length=2000)
    source_clause_id: str
    source_text: str = Field(min_length=1, max_length=2000)


class ReferenceProposal(BaseModel):
    """A cross-reference between clauses or documents."""

    model_config = ConfigDict(extra="forbid")

    from_clause_id: str
    reference_type: Literal["clause", "exhibit", "schedule", "definition", "external"]
    target: str = Field(min_length=1, max_length=500)
    resolved: bool
    resolved_clause_id: str | None = None
    resolution_note: str | None = None

    @model_validator(mode="after")
    def validate_resolution(self) -> ReferenceProposal:
        if self.resolved and not self.resolved_clause_id:
            raise ValueError("Resolved references must specify resolved_clause_id")
        return self


class DiagnosticProposal(BaseModel):
    """A compiler diagnostic about a clause or the agreement as a whole."""

    model_config = ConfigDict(extra="forbid")

    code: str = Field(min_length=1, max_length=100)
    severity: AllowedDiagnosticSeverity
    message: str = Field(min_length=1, max_length=1000)
    clause_id: str | None = None
    suggested_action: str | None = None


class ConditionProposal(BaseModel):
    """A testable condition the LLM proposes — NOT an expression tree."""

    model_config = ConfigDict(extra="forbid")

    condition_type: AllowedConditionType
    parameters: dict[str, Any] = Field(default_factory=dict)
    description: str = Field(min_length=1, max_length=1000)

    @model_validator(mode="after")
    def validate_condition_parameters(self) -> ConditionProposal:
        p = self.parameters
        ct = self.condition_type
        common_window = {
            "event_types",
            "anchor_field",
            "window_value",
            "window_unit",
            "start_exclusive",
            "end_exclusive",
            "compare_fields",
            "filters",
        }
        allowed: dict[str, set[str]] = {
            "field_present": {"field"},
            "field_equals": {"field", "expected_value", "normalizer"},
            "field_in_set": {"field", "values", "normalizer"},
            "datetime_in_range": {"field", "start", "end_exclusive"},
            "amount_equals": {"field", "expected_amount"},
            "event_exists": {"event_types", "filters", "compare_fields"},
            "event_absent": {"event_types", "filters", "compare_fields", "absence_authoritative"},
            "event_within_window": common_window,
            "terminal_outcome": {
                "success_types",
                "failure_types",
                "anchor_field",
                "window_value",
                "window_unit",
                "start_exclusive",
                "end_exclusive",
                "compare_fields",
                "filters",
            },
            "field_mismatch": {"event_type", "comparisons", "filters"},
            "duplicate_in_window": {
                "group_by",
                "order_by",
                "window_value",
                "window_unit",
                "normalizers",
            },
            "count_events_exceeds": {"event_types", "threshold", "filters"},
            "all_of": {"conditions"},
            "any_of": {"conditions"},
            "none_of": {"conditions"},
        }
        _reject_unknown_keys(p, allowed[ct], ct)

        if ct == "field_present":
            if "field" not in p:
                raise ValueError("field_present requires 'field' parameter")
        elif ct == "field_equals":
            if "field" not in p or "expected_value" not in p:
                raise ValueError("field_equals requires 'field' and 'expected_value'")
        elif ct == "field_in_set":
            if "field" not in p or "values" not in p:
                raise ValueError("field_in_set requires 'field' and 'values'")
            if not isinstance(p["values"], list) or not p["values"]:
                raise ValueError("field_in_set 'values' must be a non-empty list")
        elif ct == "datetime_in_range":
            if "field" not in p or "start" not in p or "end_exclusive" not in p:
                raise ValueError("datetime_in_range requires 'field', 'start', 'end_exclusive'")
        elif ct == "amount_equals":
            if "field" not in p or "expected_amount" not in p:
                raise ValueError("amount_equals requires 'field' and 'expected_amount'")
            p["expected_amount"] = _decimal_string(p["expected_amount"], "expected_amount")
        elif ct in {"event_exists", "event_absent"}:
            if not isinstance(p.get("event_types"), list) or not p["event_types"]:
                raise ValueError(f"{ct} requires a non-empty 'event_types' list")
        elif ct == "event_within_window":
            for required in ("event_types", "anchor_field", "window_value", "window_unit"):
                if required not in p:
                    raise ValueError(f"event_within_window requires '{required}'")
            if p["window_unit"] not in ("seconds", "minutes", "hours", "days", "calendar_days"):
                raise ValueError(f"Unsupported window_unit: {p['window_unit']}")
        elif ct == "terminal_outcome":
            if not isinstance(p.get("success_types"), list) or not p["success_types"]:
                raise ValueError("terminal_outcome requires non-empty 'success_types'")
            if not isinstance(p.get("failure_types"), list) or not p["failure_types"]:
                raise ValueError("terminal_outcome requires non-empty 'failure_types'")
            if "window_unit" in p and p["window_unit"] not in (
                "seconds",
                "minutes",
                "hours",
                "days",
                "calendar_days",
            ):
                raise ValueError(f"Unsupported window_unit: {p['window_unit']}")
        elif ct == "field_mismatch":
            if "event_type" not in p or "comparisons" not in p:
                raise ValueError("field_mismatch requires 'event_type' and 'comparisons'")
            if not isinstance(p["comparisons"], list) or not p["comparisons"]:
                raise ValueError("field_mismatch 'comparisons' must be a non-empty list")
        elif ct == "duplicate_in_window":
            for required in ("group_by", "order_by", "window_value", "window_unit"):
                if required not in p:
                    raise ValueError(f"duplicate_in_window requires '{required}'")
            if p["window_unit"] not in ("seconds", "minutes", "hours", "days", "calendar_days"):
                raise ValueError(f"Unsupported window_unit: {p['window_unit']}")
        elif ct == "count_events_exceeds":
            if "event_types" not in p or "threshold" not in p:
                raise ValueError("count_events_exceeds requires 'event_types' and 'threshold'")
            if not isinstance(p["threshold"], int) or p["threshold"] < 0:
                raise ValueError("count_events_exceeds threshold must be a non-negative integer")
        elif ct in ("all_of", "any_of", "none_of"):
            if "conditions" not in p:
                raise ValueError(f"{ct} requires 'conditions'")
            if not isinstance(p["conditions"], list) or not p["conditions"]:
                raise ValueError(f"{ct} 'conditions' must be a non-empty list")
            for i, sub in enumerate(p["conditions"]):
                if not isinstance(sub, dict):
                    raise ValueError(f"{ct} condition {i} must be a dict")  # noqa: TRY004
                ConditionProposal.model_validate(sub)
        return self


class ExceptionProposal(BaseModel):
    """An exception to a norm's condition."""

    model_config = ConfigDict(extra="forbid")

    condition: ConditionProposal
    description: str = Field(min_length=1, max_length=1000)


class ProofRequirementProposal(BaseModel):
    """What evidence is needed to evaluate a norm."""

    model_config = ConfigDict(extra="forbid")

    description: str = Field(min_length=1, max_length=1000)
    fact_types: list[str] = Field(min_length=1)
    preferred_authority: AllowedEvidenceAuthority = "customer_system_of_record"
    entity_type: str | None = None
    required_fields: list[str] = Field(default_factory=list)
    identity_keys: list[str] = Field(default_factory=list)
    observation_window: dict[str, Any] = Field(default_factory=dict)
    requires_absence_proof: bool = False
    missing_evidence_result: Literal["unknown"] = "unknown"
    requirement_ids: list[str] = Field(default_factory=list)


class NormProposal(BaseModel):
    """A contractual obligation, prohibition, or other norm."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, max_length=30)
    norm_type: AllowedNormType
    subject: str = Field(min_length=1, max_length=200)
    beneficiary: str | None = None
    trigger: ConditionProposal | None = None
    condition: ConditionProposal
    exceptions: list[ExceptionProposal] = Field(default_factory=list)
    consequence: AllowedConsequence
    indeterminate_consequence: AllowedConsequence = "needs_review"
    proof_requirements: list[ProofRequirementProposal] = Field(default_factory=list)
    violation_reason_code: str | None = None
    violation_reason: str | None = None
    indeterminate_reason_code: str | None = None
    indeterminate_reason: str | None = None
    confidence: float = Field(ge=0.0, le=1.0, default=1.0)
    ambiguity_notes: list[str] = Field(default_factory=list)
    requirement_ids: list[str] = Field(default_factory=list)


class SettlementProposal(BaseModel):
    """How a pricing clause affects the payable amount."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, max_length=30)
    settlement_type: AllowedSettlementType
    parameters: dict[str, Any] = Field(default_factory=dict)
    source_clause_id: str
    description: str = Field(min_length=1, max_length=1000)
    requirement_ids: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_settlement_parameters(self) -> SettlementProposal:
        p = self.parameters
        st = self.settlement_type
        allowed: dict[str, set[str]] = {
            "fixed_per_unit": {"unit_price", "quantity_field"},
            "rate_table": {"lookup_field", "rates", "default"},
            "tiered_rate": {"quantity_field", "tiers"},
            "percentage": {"percent", "base_field"},
            "cap": {"maximum", "base_expression"},
            "floor": {"minimum", "base_expression"},
            "deduction": {"amount", "base_expression"},
            "conditional_eligibility": {"eligible_flag_field"},
        }
        _reject_unknown_keys(p, allowed[st], st)

        if st == "fixed_per_unit":
            if "unit_price" not in p:
                raise ValueError("fixed_per_unit requires 'unit_price'")
            p["unit_price"] = _decimal_string(p["unit_price"], "unit_price")
        elif st == "rate_table":
            if "lookup_field" not in p or "rates" not in p:
                raise ValueError("rate_table requires 'lookup_field' and 'rates'")
            if not isinstance(p["rates"], dict) or not p["rates"]:
                raise ValueError("rate_table 'rates' must be a non-empty dict")
            p["rates"] = {
                str(key): _decimal_string(value, f"rate[{key}]")
                for key, value in p["rates"].items()
            }
            if "default" in p:
                p["default"] = _decimal_string(p["default"], "default")
        elif st == "tiered_rate":
            if "tiers" not in p:
                raise ValueError("tiered_rate requires 'tiers'")
            if not isinstance(p["tiers"], list) or not p["tiers"]:
                raise ValueError("tiered_rate 'tiers' must be a non-empty list")
            previous_up_to: Decimal | None = None
            normalized: list[dict[str, str | None]] = []
            for index, tier in enumerate(p["tiers"]):
                if not isinstance(tier, dict):
                    raise ValueError(f"tiered_rate tier {index} must be an object")  # noqa: TRY004
                _reject_unknown_keys(tier, {"up_to", "unit_price"}, f"tiered_rate tier {index}")
                if "unit_price" not in tier:
                    raise ValueError(f"tiered_rate tier {index} requires unit_price")
                up_to = tier.get("up_to")
                up_to_decimal = (
                    None
                    if up_to is None
                    else Decimal(_decimal_string(up_to, f"tier {index} up_to"))
                )
                if previous_up_to is None and index > 0:
                    raise ValueError("Only the final tier may be unbounded")
                if (
                    up_to_decimal is not None
                    and previous_up_to is not None
                    and up_to_decimal <= previous_up_to
                ):
                    raise ValueError("tiered_rate tiers must have increasing up_to values")
                normalized.append(
                    {
                        "up_to": None if up_to_decimal is None else format(up_to_decimal, "f"),
                        "unit_price": _decimal_string(
                            tier["unit_price"], f"tier {index} unit_price"
                        ),
                    }
                )
                previous_up_to = up_to_decimal
            p["tiers"] = normalized
        elif st == "percentage":
            if "percent" not in p:
                raise ValueError("percentage requires 'percent'")
            percent = Decimal(_decimal_string(p["percent"], "percent"))
            if percent < 0:
                raise ValueError("percent cannot be negative")
            p["percent"] = format(percent, "f")
        elif st == "cap":
            if "maximum" not in p:
                raise ValueError("cap requires 'maximum'")
            p["maximum"] = _decimal_string(p["maximum"], "maximum")
        elif st == "floor":
            if "minimum" not in p:
                raise ValueError("floor requires 'minimum'")
            p["minimum"] = _decimal_string(p["minimum"], "minimum")
        elif st == "deduction":
            if "amount" not in p:
                raise ValueError("deduction requires 'amount'")
            p["amount"] = _decimal_string(p["amount"], "amount")
        return self


class SourceDocumentRef(BaseModel):
    """Reference to a source document in the agreement packet."""

    model_config = ConfigDict(extra="forbid")

    document_id: str
    title: str
    document_type: str = "agreement"


# ---------------------------------------------------------------------------
# Clause analysis — one per material clause
# ---------------------------------------------------------------------------


class ClauseAnalysisProposal(BaseModel):
    """Complete analysis of one agreement clause."""

    model_config = ConfigDict(extra="forbid")

    clause_id: str = Field(min_length=1, max_length=50)
    source_document_id: str
    source_span_ids: list[str] = Field(default_factory=list, max_length=6)
    source_text: str = Field(min_length=1, max_length=5000)
    source_start: int | None = Field(default=None, ge=0)
    source_end: int | None = Field(default=None, ge=1)
    source_text_hash: str | None = Field(default=None, min_length=64, max_length=64)
    material: bool = True
    clause_type: AllowedClauseType
    parties: list[str] = Field(default_factory=list)
    defined_terms_used: list[str] = Field(default_factory=list)
    references: list[ReferenceProposal] = Field(default_factory=list)
    norms: list[NormProposal] = Field(default_factory=list)
    settlement_effects: list[SettlementProposal] = Field(default_factory=list)
    automation_classification: AllowedAutomationClass = "fully_executable"
    unsupported_concepts: list[str] = Field(default_factory=list)
    diagnostics: list[DiagnosticProposal] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Top-level compilation proposal
# ---------------------------------------------------------------------------


class AgreementCompilationProposal(BaseModel):
    """Complete LLM output for agreement analysis."""

    model_config = ConfigDict(extra="forbid")

    compiler_version: str = Field(min_length=1)
    contract_id: str = Field(min_length=1)
    model: str = Field(min_length=1)
    provider: str = Field(min_length=1)
    source_documents: list[SourceDocumentRef] = Field(min_length=1)
    definitions: list[DefinitionProposal] = Field(default_factory=list)
    requirements: list[AtomicRequirementProposal] = Field(default_factory=list)
    clauses: list[ClauseAnalysisProposal] = Field(min_length=1)
    global_diagnostics: list[DiagnosticProposal] = Field(default_factory=list)

    @field_validator("clauses")
    @classmethod
    def clause_ids_unique(cls, v: list[ClauseAnalysisProposal]) -> list[ClauseAnalysisProposal]:
        ids = [c.clause_id for c in v]
        if len(ids) != len(set(ids)):
            raise ValueError("Clause IDs must be unique")
        return v

    @model_validator(mode="after")
    def validate_cross_references(self) -> AgreementCompilationProposal:
        requirement_ids = [item.id for item in self.requirements]
        if len(requirement_ids) != len(set(requirement_ids)):
            raise ValueError("Atomic requirement IDs must be globally unique")
        known_requirements = set(requirement_ids)

        norm_ids: list[str] = []
        settlement_ids: list[str] = []
        for clause in self.clauses:
            for norm in clause.norms:
                norm_ids.append(norm.id)
                unknown = set(norm.requirement_ids) - known_requirements
                if unknown:
                    raise ValueError(
                        f"Norm {norm.id} references unknown atomic requirements: {sorted(unknown)}"
                    )
                for proof in norm.proof_requirements:
                    unknown_proof = set(proof.requirement_ids) - known_requirements
                    if unknown_proof:
                        raise ValueError(
                            f"Proof in norm {norm.id} references unknown atomic requirements: "
                            f"{sorted(unknown_proof)}"
                        )
                    if proof.requirement_ids and not set(proof.requirement_ids).issubset(
                        set(norm.requirement_ids)
                    ):
                        raise ValueError(
                            f"Proof in norm {norm.id} must bind only requirements bound to its norm"
                        )
            for settlement in clause.settlement_effects:
                settlement_ids.append(settlement.id)
                unknown = set(settlement.requirement_ids) - known_requirements
                if unknown:
                    raise ValueError(
                        f"Settlement {settlement.id} references unknown atomic requirements: "
                        f"{sorted(unknown)}"
                    )

        if len(norm_ids) != len(set(norm_ids)):
            raise ValueError("Norm IDs must be globally unique across all clauses")
        if len(settlement_ids) != len(set(settlement_ids)):
            raise ValueError("Settlement IDs must be globally unique across all clauses")
        return self
