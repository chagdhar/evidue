# Native AIR compilation — implementation plan

## Current architecture (verified)

```
contract text
→ Gemini proposes CompilationProposal (RuleProposal[] with operation/parameters)
→ Pydantic validates against AllowedOperation + per-operation parameter schemas
→ _rule_program_from_proposal() builds legacy RuleProgram
→ legacy_rule_program_to_agreement_ir() translates to AgreementIR
→ agreement_artifacts_for_proposal() remaps clause IDs and adds settlement
→ Human approves → immutable version
→ Reconciliation: legacy engine runs, optional dual-run with AIR evaluator
```

The LLM currently proposes **operation-level rules** (`prohibit_event_within`,
`require_success_event_within`, etc.) — it has to know the engine's vocabulary.

## Target architecture

```
contract text
→ Gemini proposes AgreementCompilationProposal (ClauseAnalysisProposal[])
→ Pydantic validates semantic structure (no expression trees)
→ lower_to_agreement_ir() deterministically builds AgreementIR
→ Human approves → immutable persisted AIR version
→ Reconciliation: legacy engine + persisted AIR dual-run
```

The LLM proposes **semantic structure** (norm type, condition type, evidence
requirements, settlement effect) — it does not know expression operators. The
deterministic lowerer builds Expression trees from condition types.

## What the two-stage design buys

The legacy compiler has a clever safety model: the LLM proposes structured
JSON, Pydantic validates it, humans approve immutable versions. The native
compiler keeps exactly this shape but changes what the LLM proposes:

| | Legacy | Native |
|---|---|---|
| LLM output | Operation name + parameters | Clause analysis + condition type |
| Validation | Per-operation parameter schema | Strict semantic schema |
| Expression trees | Built by legacy.py translation | Built by deterministic lowerer |
| Settlement | Blanket "billed × eligible" | Precise per-pricing-clause |
| Definitions | Not tracked | First-class with resolution |

The LLM never sees Expression operators in either path.

---

## Milestone 1 — Native clause analysis schema

### File: `backend/app/agreements/compiler_models.py`

All models use `ConfigDict(extra="forbid")`.

```python
class DefinitionProposal(BaseModel):
    term: str                           # "Qualified Outcome"
    meaning: str                        # "An outcome where..."
    source_clause_id: str               # which clause defined it
    source_text: str                    # exact quote

class ReferenceProposal(BaseModel):
    from_clause_id: str
    reference_type: Literal["clause", "exhibit", "schedule", "definition", "external"]
    target: str                         # "Section 4.2" or "Exhibit A"
    resolved: bool                      # can we find the target?
    resolved_clause_id: str | None      # if resolved, which clause
    resolution_note: str | None         # why unresolved

class ConditionProposal(BaseModel):
    """What the LLM proposes instead of an expression tree."""
    condition_type: AllowedConditionType  # Literal enum
    parameters: dict[str, Any]          # type-specific, validated per condition_type
    description: str                    # human-readable

class ExceptionProposal(BaseModel):
    condition: ConditionProposal
    description: str

class ProofRequirementProposal(BaseModel):
    description: str
    fact_types: list[str]               # what evidence proves/disproves this
    preferred_authority: str
    missing_evidence_result: Literal["unknown", "needs_review"]

class NormProposal(BaseModel):
    id: str
    norm_type: Literal["obligation", "prohibition", "permission", ...]
    subject: str
    beneficiary: str | None
    trigger: ConditionProposal | None
    condition: ConditionProposal
    exceptions: list[ExceptionProposal]
    consequence: Literal["payable", "disputed", "needs_review"]
    indeterminate_consequence: Literal["payable", "disputed", "needs_review"]
    proof_requirements: list[ProofRequirementProposal]
    confidence: float                   # 0.0-1.0
    ambiguity_notes: list[str]

class SettlementProposal(BaseModel):
    id: str
    settlement_type: AllowedSettlementType  # Literal enum
    parameters: dict[str, Any]          # per-type validated
    source_clause_id: str               # the specific pricing clause
    description: str

class ClauseAnalysisProposal(BaseModel):
    clause_id: str
    source_document_id: str
    source_text: str
    material: bool
    clause_type: Literal["pricing", "performance", "quality", "timing",
                          "scope", "definition", "procedural", "boilerplate"]
    parties: list[str]
    defined_terms_used: list[str]
    references: list[ReferenceProposal]
    norms: list[NormProposal]
    settlement_effects: list[SettlementProposal]
    automation_classification: AutomationClass
    unsupported_concepts: list[str]
    diagnostics: list[DiagnosticProposal]

class AgreementCompilationProposal(BaseModel):
    compiler_version: str
    contract_id: str
    model: str
    provider: str
    source_documents: list[SourceDocumentRef]
    definitions: list[DefinitionProposal]
    clauses: list[ClauseAnalysisProposal]
    global_diagnostics: list[DiagnosticProposal]
```

### Allowed condition types (what the LLM can propose)

```python
AllowedConditionType = Literal[
    "field_present",            # claim field exists and is non-empty
    "field_equals",             # claim field == expected value
    "field_in_set",             # claim field in {set of values}
    "datetime_in_range",        # claim datetime within billing period
    "amount_equals",            # billed amount matches contract rate
    "event_exists",             # event of type X exists in evidence
    "event_absent",             # no event of type X in evidence
    "event_within_window",      # event within time window of anchor
    "terminal_outcome",         # success/failure terminal evidence
    "field_mismatch",           # claim field != event field
    "duplicate_in_window",      # same group key within time window
    "count_events_exceeds",     # more than N events of type X
    "all_of",                   # AND of sub-conditions
    "any_of",                   # OR of sub-conditions
    "none_of",                  # NOT of sub-condition
]
```

Each condition_type has a per-type parameter schema validated in
`ConditionProposal`. The lowerer maps each to the correct Expression tree.

### Allowed settlement types

```python
AllowedSettlementType = Literal[
    "fixed_per_unit",           # price × quantity
    "rate_table",               # lookup by outcome type
    "tiered_rate",              # volume-based tiers
    "percentage",               # % of submitted
    "cap",                      # min(amount, cap)
    "floor",                    # max(amount, floor)
    "deduction",                # submitted - deduction
    "conditional_eligibility",  # binary eligible/not
]
```

---

## Milestone 2 — Deterministic AIR lowering

### File: `backend/app/agreements/compiler.py`

Main entry point:

```python
def lower_to_agreement_ir(
    proposal: AgreementCompilationProposal,
    *,
    compilation_id: str,
    version: int,
    source_hash: str,
) -> tuple[AgreementIR, ConformanceReport]:
```

### Lowering pipeline

```
1. resolve_definitions(proposal)
   - build term → definition mapping
   - flag undefined terms used in norms
   - flag conflicting definitions
   - flag circular references

2. resolve_references(proposal)
   - for each ReferenceProposal, check target exists
   - flag unresolved material references
   - detect circular clause references

3. lower_clauses(proposal)
   - for each ClauseAnalysisProposal:
     - create SourceClause
     - lower each NormProposal → Norm (with Expression tree)
     - lower each SettlementProposal → SettlementPolicy
     - create ProofRequirement per norm
     - create ClauseCoverage

4. build_diagnostics()
   - unresolved material definitions → blocking
   - unresolved material references → blocking
   - unsupported material clauses → blocking
   - settlement without pricing clause → blocking
   - low confidence norms → warning

5. build_conformance_report()

6. validate AgreementIR (Pydantic cross-reference checks)
```

### Condition lowering (the core safety boundary)

Each `AllowedConditionType` maps to one known Expression pattern. The LLM
cannot invent expressions — it can only select from these types and fill
in their parameters. The lowerer validates parameters and builds the tree:

```python
def _lower_condition(condition: ConditionProposal) -> Expression:
    match condition.condition_type:
        case "field_present":
            return Expression(operator="present", operands=[
                Expression(operator="field", path=f"claim.{condition.parameters['field']}")
            ])
        case "event_within_window":
            return Expression(operator="exists_event", parameters={
                "event_types": condition.parameters["event_types"],
                "window": {
                    "anchor_path": f"claim.{condition.parameters['anchor_field']}",
                    "value": condition.parameters["window_value"],
                    "unit": condition.parameters["window_unit"],
                    "start_exclusive": condition.parameters.get("start_exclusive", False),
                },
                # + dynamic_field_equals if compare_fields present
            })
        case "terminal_outcome":
            return Expression(operator="terminal_event_outcome", parameters={
                "success_event_types": condition.parameters["success_types"],
                "failure_event_types": condition.parameters["failure_types"],
                "window": { ... },
            })
        # ... one case per AllowedConditionType
```

This is exhaustive — no `else: pass`. Unknown types are rejected by Pydantic
before they reach the lowerer.

### Settlement lowering

```python
def _lower_settlement(settlement: SettlementProposal) -> Expression:
    match settlement.settlement_type:
        case "fixed_per_unit":
            return Expression(operator="multiply", operands=[
                Expression(operator="constant", value=settlement.parameters["unit_price"]),
                Expression(operator="field", path="claim.quantity"),
            ])
        case "rate_table":
            return Expression(operator="rate_table",
                path=f"claim.{settlement.parameters['lookup_field']}",
                parameters={"rates": settlement.parameters["rates"],
                            "default": settlement.parameters.get("default")})
        case "cap":
            return Expression(operator="cap", operands=[
                _lower_settlement(settlement.parameters["base"]),
                Expression(operator="constant", value=settlement.parameters["maximum"]),
            ])
        # ... one case per AllowedSettlementType
```

Each settlement policy references ONLY its specific pricing clause, not every
clause in the contract.

---

## Milestone 3 — Definitions and references

### New models in `compiler_models.py`

```python
class Definition(BaseModel):
    term: str
    meaning: str
    source_clause_id: str
    source_document_id: str

class DefinedTermReference(BaseModel):
    term: str
    used_in_clause_id: str
    resolved: bool
    definition: Definition | None

class UnresolvedReference(BaseModel):
    from_clause_id: str
    target: str
    reference_type: str
    reason: str  # why it can't be resolved
```

### Approval blocking rules

The lowerer generates blocking diagnostics when:

```
- A material clause uses a defined term that has no Definition → UNRESOLVED_DEFINITION
- A material clause references a clause/exhibit that doesn't exist → UNRESOLVED_REFERENCE
- Two documents define the same term differently → CONFLICTING_DEFINITION
- Clause references form a cycle → CIRCULAR_REFERENCE
- An amendment references a clause that was already superseded → SUPERSEDED_REFERENCE
```

These are checked in `resolve_definitions()` and `resolve_references()`.

---

## Milestone 4 — Native settlement compilation

The current settlement policy is:

```
billed_amount × rate_table(eligible_flag: true→1, false→0)
```

This attaches every clause as a source and treats settlement as binary. Native
settlement must be precise:

```python
# From a pricing clause: "$1.50 per qualified outcome"
SettlementProposal(
    id="SETTLE-PRICING",
    settlement_type="fixed_per_unit",
    parameters={"unit_price": "1.50", "quantity_field": "quantity"},
    source_clause_id="CLAUSE-PRICING-1",   # ONLY the pricing clause
    description="$1.50 per qualified outcome",
)
```

The lowerer produces:

```python
SettlementPolicy(
    id="SETTLEMENT-1",
    claim_type="outcome",
    eligibility_norm_ids=[...],  # which norms must be satisfied
    amount_expression=Expression(operator="multiply", operands=[
        Expression(operator="constant", value="1.50"),
        Expression(operator="field", path="claim.quantity"),
    ]),
    source_clause_ids=["SOURCE-CLAUSE-PRICING-1"],  # precise provenance
)
```

The settlement trace becomes:

```
submitted: $1.50
→ eligibility: all norms satisfied → eligible
→ pricing: $1.50 × 1 unit = $1.50 (from "CLAUSE-PRICING-1")
→ adjustments: none
→ payable: $1.50
```

---

## Milestone 5 — Persisted AIR versions

### New DB tables in `backend/app/upload/models.py`

```python
class PilotAIRVersionRow(Base):
    __tablename__ = "pilot_air_versions"
    id: str                     # "PAIR-xxxx"
    contract_id: str            # FK → PilotContractRow
    compilation_id: str         # FK → PilotRuleCompilationRow
    version_number: int
    schema_version: str         # "air-0.1"
    source_bundle_hash: str
    compiler_mode: str          # "legacy_translation" or "native"
    compiler_model: str | None
    prompt_version: str | None
    created_at: datetime
    approved_at: datetime | None
    approved_by: str | None
    payload_hash: str           # SHA-256 of the serialized AgreementIR
    superseded_by_id: str | None
    air_json: JSON              # the complete AgreementIR, immutable once approved

class PilotAIRDiagnosticRow(Base):
    __tablename__ = "pilot_air_diagnostics"
    id: int                     # autoincrement
    air_version_id: str         # FK → PilotAIRVersionRow
    code: str
    severity: str
    message: str
    clause_ids_json: JSON       # list[str]
```

### Store functions

```python
def persist_air_version(session, contract_id, compilation_id, air, mode, ...)
    → PilotAIRVersionRow

def approve_air_version(session, air_version_id, approved_by)
    → PilotAIRVersionRow  # sets approved_at, immutable after

def get_approved_air(session, contract_id)
    → AgreementIR | None  # loads from air_json

def get_air_version(session, air_version_id)
    → AgreementIR
```

### Immutability constraint

Once `approved_at` is set, `air_json` and `payload_hash` can never change. A
new compilation creates a new version row; it does not modify the approved one.

---

## Milestone 6 — Dual-run uses persisted AIR

### Current behavior (in `reconcile_invoice`, store.py line 1011):

```python
agreement = legacy_rule_program_to_agreement_ir(program)
comparison_report = dual_run(claim_evidence, agreement, program)
```

This reconstructs AIR from the legacy program every time.

### Target behavior:

```python
approved_air = get_approved_air(session, contract.id)
if dual_run_enabled:
    if approved_air is None:
        raise ValueError("Dual-run requires an approved AIR version")
    comparison_report = dual_run(claim_evidence, approved_air, program)
```

### Changes to PilotReconciliationRunRow:

Add column:
```python
air_version_id: str | None  # FK → PilotAIRVersionRow, which exact AIR was used
```

This makes the reconciliation audit trail complete: every run records the exact
legacy program version AND the exact AIR version that was compared.

---

## Files created

```
backend/app/agreements/compiler_models.py  — LLM proposal schema (M1)
backend/app/agreements/compiler.py         — deterministic lowerer (M2)
backend/tests/test_air_compiler.py         — lowerer + definition/reference tests (M1-4)
```

## Files modified

```
backend/app/upload/models.py               — PilotAIRVersionRow, PilotAIRDiagnosticRow (M5)
backend/app/upload/store.py                — persist/approve/load AIR, change dual-run to use persisted (M5-6)
backend/app/upload/router.py               — endpoints for AIR versions (M5)
backend/tests/test_agreements.py           — settlement, lowering, definition tests (M1-4)
```

## Files NOT modified

```
backend/app/agreements/models.py           — AgreementIR schema is already correct
backend/app/agreements/runtime.py          — expression evaluator is already correct
backend/app/agreements/evaluation.py       — dual-run comparator is already correct
backend/app/agreements/legacy.py           — legacy adapter stays for backward compat
backend/app/contracts/compiler.py          — legacy compiler stays for legacy path
backend/app/domain/engine.py               — legacy engine untouched
frontend/*                                 — no frontend changes in this milestone
```

## Test plan

### Compiler tests (test_air_compiler.py)

```
test_lower_field_present_condition
test_lower_datetime_in_range_condition
test_lower_event_within_window_condition
test_lower_terminal_outcome_condition
test_lower_field_mismatch_condition
test_lower_duplicate_in_window_condition
test_lower_amount_equals_condition
test_lower_all_of_condition
test_lower_none_of_condition

test_unresolved_definition_blocks_approval
test_unresolved_reference_blocks_approval
test_conflicting_definition_blocks_approval
test_circular_reference_blocks_approval
test_non_material_unresolved_does_not_block

test_settlement_fixed_per_unit
test_settlement_rate_table
test_settlement_cap
test_settlement_floor
test_settlement_percentage
test_settlement_precise_clause_provenance

test_unknown_condition_type_rejected_by_pydantic
test_unknown_settlement_type_rejected_by_pydantic
test_lowered_air_passes_agreement_ir_validation
```

### Persistence tests (test_agreements.py additions)

```
test_air_version_persisted_and_retrievable
test_approved_air_is_immutable
test_recompilation_creates_new_version
test_superseded_version_remains_readable
```

### Integration tests

```
test_native_compile_lower_approve_reconcile_lifecycle
test_dual_run_uses_persisted_air_not_live_translation
test_dual_run_fails_clearly_without_approved_air
test_reconciliation_records_air_version_id
```

### Regression

```
test_air_dual_run_produces_exact_equivalence_on_10k_demo_fixture  — UNCHANGED
test_demo_financial_result_unchanged                               — UNCHANGED
```

## What this does NOT do

- Does not change the legacy compiler or engine
- Does not change demo results
- Does not add a Gemini prompt for native compilation (that's a separate milestone — the prompt engineering for producing AgreementCompilationProposal is future work; the lowerer can be tested with hand-built proposals)
- Does not add frontend screens (separate milestone)
- Does not add semantic fact extraction
- Does not add full evidence graph
- Does not claim Evidue is contract-general (that requires the cross-domain corpus)
