# Agreement IR (AIR) Specification

AIR is the approved, deterministic representation of commercial agreement semantics used by Evidue.

## Core nodes

- `SourceClause`: exact source text, document ID, materiality, source span, and text hash.
- `Norm`: typed obligation/prohibition/eligibility semantics with a constrained expression and explicit consequence.
- `AtomicPredicate`: immutable source-bound boolean expression used by proof planning and fact derivation; carries a canonical hash.
- `ProofRequirement`: declares the external facts/capabilities required to evaluate a norm. Claim-only conditions should not create external proof requirements.
- `SettlementPolicy`: source-bound amount logic for the final payable amount.
- `ClauseCoverage`: records whether every material clause is represented and how it is automated.
- `CompilerDiagnostic`: explicit warnings/blockers; unsupported material language blocks approval.

## Invariants

- Unknown expression operators are schema-invalid.
- IDs and references must resolve.
- Proof requirements must resolve to predicates attached to the same norm.
- Material clauses require exact source grounding.
- Settlement policies require source-clause provenance.
- Canonical predicate hashes must match the persisted expression.
- Approved AIR payloads are immutable and hash-checked on approval and use.

## Lifecycle

The API exposes a derived lifecycle:

- `validation_failed` — mechanical assurance did not pass.
- `ready_for_review` — conformance/assurance gates pass; human approval is still required.
- `active` — approved and not superseded.
- `superseded` — a newer approved AIR is active.

The database stores immutable versions; lifecycle is derived from approval/supersession and persisted assurance state.
