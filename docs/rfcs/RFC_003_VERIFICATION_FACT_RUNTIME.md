# RFC 003 — Verification Planner and Fact Runtime

Status: Design baseline; core implemented in `product-complete`
Depends on: RFC 001

## Decision

The universal runtime boundary is the atomic predicate/fact, not vendor events and not model judgments.

Contracts request facts. Evidence sources advertise capabilities. A verification planner selects how to prove each predicate. A fact runtime derives and caches four-valued facts with provenance.

## Runtime flow

```text
Atomic Predicate
      ↓
Proof Requirement
      ↓
Capability Planner
      ↓
Verification Plan Item
      ↓
Evidence Query / Existing Evidence
      ↓
Normalized Observations
      ↓
Fact Derivation
      ↓
TRUE / FALSE / UNKNOWN / CONFLICTING
```

## Capability model

A source capability must declare:

- source authority;
- entity type;
- available fields;
- event types;
- state transitions;
- identity keys;
- timestamp semantics;
- source timezone;
- freshness;
- retention;
- historical snapshot support;
- can prove occurrence;
- can prove absence;
- completeness guarantee;
- parser/adapter version.

The planner targets capabilities, not vendor names.

## Query planning

Each predicate should compile to a small evidence query plan.

Example:

```text
Predicate: no refund reversal within 7d
```

Plan:

```text
source capability: payment_state_transition
identity join: transaction_id
window: refund_settled .. +7d
required event: reversal
absence required: true
```

If the selected source cannot prove absence, the plan must not derive `FALSE` from missing rows.

## Evidence storage efficiency

Do not duplicate raw evidence into every graph representation.

Persist:

```text
EvidenceArtifact   immutable raw-reference + hash
Observation        normalized canonical event/state record
Fact               derived truth for predicate + subject + snapshot
ProvenanceEdge     links derivation chain
```

The Work Graph should initially be a derived view over canonical observations rather than a separately duplicated event store.

Only persist first-class work entities when they carry semantics not representable by observations.

## Canonical observation ontology

Use a small set:

- `communication`
- `tool_invocation`
- `state_snapshot`
- `state_transition`
- `external_event`
- `human_intervention`
- `reversal`
- `correction`
- `attestation`

Vendor adapters map source records into these observations.

## Fact cache key

Facts are content-addressed by:

```text
predicate_hash
subject_id
verification_plan_version
source_snapshot_hash
derivation_version
```

If none change, reuse the fact.

This avoids recomputing every predicate on every reconciliation run.

## Incremental invalidation

New evidence should invalidate only facts depending on that source snapshot/window.

Example:

```text
new conversation reopen event
```

should invalidate:

- recontact predicates for that conversation/claim;

but not:

- pricing definition facts;
- unrelated claims;
- contract compilation.

## Fact derivation types

### Deterministic

- field comparison;
- event occurrence;
- authoritative absence;
- state transition;
- temporal relation;
- identity match;
- count/aggregation;
- duplicate/uniqueness.

### Model-assisted

Only for semantic predicates such as:

- user explicitly requested human assistance;
- required disclosure present;
- same underlying issue;
- explicit rejection/acceptance.

The semantic extractor must return:

```text
truth
confidence
exact evidence citations
model version
prompt version
input hash
requires_review
```

It never receives or returns settlement decisions.

### Human-attested

Store original fact and reviewer decision separately.

## Effective fact policy

Never overwrite derived truth.

Persist:

```text
original_truth
reviewed_truth
effective_truth
review_policy
```

`effective_truth` is a deterministic projection of the review policy.

## Four-valued semantics

Facts use:

- `TRUE`
- `FALSE`
- `UNKNOWN`
- `CONFLICTING`

Absence rules:

```text
no matching evidence + authoritative complete source that can prove absence => FALSE
no matching evidence + incomplete/non-absence-capable source => UNKNOWN
contradictory authoritative evidence => CONFLICTING
```

## Conflict resolution

Do not globally choose “newest” or “customer source wins”.

Conflict policy is attached to the proof requirement and may consider:

- source authority;
- source independence;
- immutability;
- completeness;
- timestamp ordering;
- contract-defined hierarchy;
- human review requirement.

All conflicting evidence remains visible in provenance.

## API direction

Target APIs:

```text
POST /verification-plans/{id}/execute
GET  /claims/{claim_id}/facts
GET  /facts/{fact_id}
POST /facts/{fact_id}/review
GET  /claims/{claim_id}/evidence-trace
```

## Acceptance gates

- one norm with three atomic predicates produces three independent facts;
- missing data never becomes false unless absence is provable;
- semantic facts cannot directly alter money before review policy accepts them;
- a new evidence record invalidates only dependent facts;
- two different vendors can satisfy the same capability without evaluator code changes.
