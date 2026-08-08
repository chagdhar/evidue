# Atomic Contract Requirement Ledger

Evidue does not treat a structurally valid Agreement IR as proof that every financially material contract condition was interpreted. The native compiler first creates an independent, source-grounded **Atomic Requirement Ledger**, then compiles those requirements into AIR.

## Why this exists

A single contract sentence can contain several independently testable conditions. For example, a sentence may contain a recontact exclusion, a human-completion exclusion, and a time window. A compiler that emits one generic rule for that sentence can look source-grounded while silently losing financial semantics.

The requirement ledger makes completeness explicit. Every material requirement has its own ID, exact source grounding, materiality, data dependencies, intended disposition, parameters, and AIR bindings.

## Two-pass compiler

```text
contract bytes
  -> immutable sentence-sized source spans
  -> independent atomic-requirement pass
  -> deterministic source binding of the requirement ledger
  -> AIR proposal pass using the ledger as authoritative input
  -> schema/semantic validation + bounded repair
  -> fail-closed rejection of malformed executable artifacts
  -> deterministic requirement-to-AIR assurance
  -> human approval
  -> deterministic reconciliation
```

The second pass may not silently add, remove, merge, or rewrite requirements from the first pass. Requirement IDs are carried by norms, settlement policies, and proof requirements.

## Data dependency boundary

Each requirement declares the runtime data class needed to evaluate it:

- `claim` — normalized invoice/claim fields such as billed amount or service date;
- `invoice` — invoice-level values;
- `contract_constant` — approved contract parameters such as a rate or window;
- `batch_claims` — deterministic comparisons across invoice claims, such as uniqueness;
- `customer_evidence` — downstream operational evidence;
- `external_document` — a referenced document not present in the bundle;
- `human_attestation` — a fact that cannot safely be automated.

The lowerer independently derives the data classes actually consumed by each executable condition. A direct claim/batch condition must not be made indeterminate by an unrelated external proof requirement. Conversely, a condition that consumes customer evidence must have a proof plan.

## Blocking assurance diagnostics

The deterministic assurance layer blocks AIR approval for conditions including:

- `ATOMIC_REQUIREMENT_UNMAPPED`
- `ATOMIC_REQUIREMENTS_COLLAPSED`
- `MATERIAL_CLAUSE_WITHOUT_ATOMIC_REQUIREMENT`
- `MATERIAL_REQUIREMENT_UNRESOLVED`
- `ORPHAN_EXECUTABLE_SEMANTICS`
- `REQUIREMENT_SOURCE_BINDING_MISMATCH`
- `REQUIREMENT_DATA_DEPENDENCY_MISMATCH`
- `DIRECT_DATA_REQUIREMENT_HAS_EXTERNAL_PROOF`
- `EVIDENCE_REQUIREMENT_MISSING_PROOF`
- `NONEXECUTABLE_REQUIREMENT_HAS_EXECUTABLE_BINDING`
- `UNSAFE_REQUIREMENT_AUTOMATION`

Material `unresolved_dependency` requirements are not approvable until the missing contract data is supplied; merely labeling a missing rate or referenced document as unresolved cannot authorize money.

These checks do not claim that software can prove legal interpretation correctness. They prove narrower properties that can be checked mechanically: source grounding, mapping completeness, atomicity of executable bindings, and consistency between declared evidence needs and runtime inputs.

## Qualification v3

Qualification no longer treats "some rule points at the same clause" as a successful match. Reviewed gold is measured at several layers:

- source recall;
- atomic-requirement recall;
- semantic fidelity;
- numeric-parameter fidelity;
- automation fidelity;
- exact financial-scenario accuracy and money conservation.

`found` remains in reports for compatibility, but now means a complete semantic match rather than source-clause overlap.
