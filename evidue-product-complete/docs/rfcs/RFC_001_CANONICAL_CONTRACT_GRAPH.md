# RFC 001 — Canonical Contract Graph

Status: Design baseline; core implemented in `product-complete`
Target branch: `product-complete`

## Decision

Evidue will persist one canonical, typed contract graph as the source of truth for an approved agreement version. Legal evaluation, proof planning, and settlement execution will be compiled views over that graph rather than independent persisted IRs.

This replaces the temptation to maintain separate Document IR, Legal IR, Proof IR, and Settlement IR copies that can drift.

## Why

The current repository already has `AgreementIR`, clauses, norms, proof requirements, settlement policies, agreement bundles, and native compilation. The missing problem is not another representation. It is a stronger normalized semantic core that:

- preserves exact source provenance;
- represents amendments and references without flattening documents;
- makes every contractual condition an atomic predicate;
- lets proof requirements reference those predicates directly;
- lets settlement rules reference norm results rather than vendor concepts;
- can be hashed, versioned, diffed, assured, and executed deterministically.

## Canonical node types

The graph should use typed relational records, not a graph database.

### Source nodes

- `AgreementBundle`
- `AgreementDocument`
- `ClauseVersion`
- `Definition`
- `PartyRole`

### Semantic nodes

- `Norm`
- `Predicate`
- `TemporalConstraint`
- `Exception`
- `Remedy`
- `SettlementRule`
- `ProofRequirement`

### Relation edges

- `CONTAINS`
- `DEFINES`
- `REFERENCES`
- `AMENDS`
- `SUPERSEDES`
- `INCORPORATES`
- `PRECEDES`
- `TRIGGERS`
- `REQUIRES`
- `EXCEPTS`
- `REMEDIES`
- `PRICES`
- `PROVES`

All edges must be typed and source-bound.

## Source provenance

Every semantic node must trace to one or more exact source spans:

```text
Document ID
Clause ID
start offset
end offset
exact text
SHA-256 hash
```

A semantic node without source provenance is non-approvable unless it is an explicitly generated structural node whose parents are source-bound.

## Clause versioning

Do not overwrite clause text when an amendment changes it.

Represent:

```text
ClauseVersion C-4.2-v1
  effective: 2026-01-01 .. 2026-06-30

ClauseVersion C-4.2-v2
  effective: 2026-07-01 .. open
  amended_by: Amendment-2 §1
```

Compilation for a billing period resolves the effective clause version set deterministically.

## Definitions

Definitions are first-class nodes.

A use of a defined term must resolve to exactly one effective definition or compilation is blocked.

```text
Qualified Outcome
  defined_by -> Exhibit A §2
  used_by    -> SOW §4
  used_by    -> Pricing §3
```

## Atomic predicates

Every factual condition must lower to a typed predicate with a stable ID/hash.

Example contract language:

> A meeting is billable when the prospect attends within 30 days of qualification and has not previously attended a meeting for the campaign.

Lower to:

```text
P1 prospect_is_qualified
P2 meeting_attended
P3 attendance_within_30_days_of_qualification
P4 no_prior_qualifying_meeting
```

Norm condition:

```text
P1 AND P2 AND P3 AND P4
```

Proof requirements point to `P1`–`P4`, never to the whole norm expression.

## Predicate type system

Predicates must be typed over a small universal ontology:

### Values

- string
- boolean
- integer
- decimal
- money
- datetime
- duration
- identifier
- enum
- set/list

### Subjects

- claim
- party
- entity
- event
- state
- artifact
- period

### Core predicate families

- field presence/equality/membership
- numeric comparison
- event occurrence
- authoritative event absence
- state equality/transition
- temporal ordering/window
- count/aggregation
- identity equivalence
- uniqueness/duplicate
- semantic assertion

Adding a new contract must not require a vendor-specific predicate family.

## Derived execution views

The canonical graph compiles into three in-memory/versioned plans:

### Legal plan

- applicable norms
- trigger graph
- conditions
- exceptions
- remedies

### Verification plan

- atomic predicate IDs
- acceptable evidence capabilities
- selected sources
- identity joins
- absence semantics
- conflict policy

### Settlement plan

- eligible units
- rates
- quantities
- credits
- caps/floors
- adjustments

These are derived from one approved graph version and can be regenerated deterministically.

## Hashing and immutability

An approved contract graph version gets:

```text
bundle_hash
source_graph_hash
semantic_graph_hash
compiler_version
schema_version
assurance_run_id
approved_at
approved_by
```

Approved graph payloads are immutable.

## Migration from current AgreementIR

Do not delete current models initially.

1. Introduce `Predicate` as a first-class persisted object.
2. Make `ProofRequirement.predicate_id` resolve to an actual predicate.
3. Normalize `Norm.trigger`, `Norm.condition`, and exceptions into predicate references.
4. Keep `AgreementIR` as an aggregate API representation assembled from graph records.
5. Remove duplicated nested expression payloads only after dual-run equivalence passes.

## Non-goals

- graph database;
- generic CLM;
- contract authoring;
- replacing SQLAlchemy;
- vendor-specific node types.

## Acceptance gates

- every material clause resolves to source-bound graph nodes;
- every proof requirement references one atomic predicate;
- no unresolved effective definition/reference exists in an approvable graph;
- recompiling the same source produces the same normalized graph hash;
- changing one source constant changes only dependent graph nodes unless semantics require otherwise.
