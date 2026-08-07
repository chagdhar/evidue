# RFC 005 — Migration, Efficiency, and Generality Test Strategy

Status: Design baseline; core implemented in `product-complete`

## Goal

Replace the legacy-domain-dependent reconciliation path with the verified contract runtime without destabilizing the current pilot or YC demo.

## Migration rule

The legacy engine remains financial authority until the new runtime proves line-level equivalence on the existing corpus and contract-general correctness on a cross-domain corpus.

## Branch sequence

### Branch A — `contract-graph-v1`

Implement:

- first-class predicates;
- graph normalization/hashing;
- clause-version and definition/reference resolution;
- AgreementIR aggregate adapter.

No financial behavior change.

### Branch B — `compiler-assurance-v1`

Implement:

- deterministic static assurance;
- coverage gate;
- semantic critique;
- canonical round-trip rendering;
- metamorphic mutation tests;
- execution probes;
- assurance persistence and approval gate.

No runtime authority change.

### Branch C — `verification-runtime-v1`

Implement:

- atomic proof requirements;
- capability query planner;
- verification-plan executor;
- normalized observations;
- fact cache/invalidation;
- conflict policy;
- reviewed effective facts.

Use existing uploaded evidence only. Do not build new connectors yet.

### Branch D — `settlement-runtime-v1`

Implement:

- generic `CommercialClaim`;
- legal/norm evaluator over facts;
- settlement DAG;
- clause-to-dollar provenance;
- shadow dual-run against legacy.

### Branch E — `contract-generality-corpus`

Run end-to-end contracts across multiple domains.

## Cross-domain corpus

Minimum families:

1. AI outcome pricing
2. uptime/SLA credits
3. qualified meeting / lead generation
4. logistics delivery penalties
5. milestone acceptance/payment
6. usage-based pricing
7. BPO response-time/quality SLA
8. revenue share

Each fixture contains:

```text
agreement bundle
expected effective clauses
expected semantic graph
expected assurance report
source capabilities
synthetic evidence
expected facts
expected norm results
expected settlement
```

## Generality acceptance rule

Adding contract family N+1 must not require:

- vendor-name branches;
- contract-category branches;
- new settlement functions specific to that contract;
- new evidence semantics tied to a product name.

A new primitive is allowed only when it is demonstrably universal and comes with cross-domain tests.

## Metamorphic test corpus

Every fixture should generate mutations:

- amounts;
- thresholds;
- durations;
- dates;
- exceptions;
- negation;
- conjunction/disjunction;
- parties;
- rate-table rows.

Assertions:

- corresponding semantic nodes change;
- unrelated nodes remain stable;
- assurance detects omitted/changed meaning;
- execution probes update accordingly.

## Property tests

Core runtime properties:

- deterministic: same inputs -> same hashes/results;
- monotonic where applicable: adding confirming evidence cannot turn TRUE into UNKNOWN;
- missing evidence never equals FALSE unless absence is provable;
- conflicting authoritative evidence never auto-resolves silently;
- money conservation invariant holds;
- historical approved versions are immutable;
- reruns are append-only.

## Performance design

Do not optimize with new infrastructure first.

Use:

- content-addressed compilation/assurance cache;
- per-predicate fact cache;
- incremental invalidation;
- verification query pushdown;
- batch claim evaluation;
- compiled settlement DAGs;
- deterministic normalized hashes.

Avoid for now:

- graph database;
- Redis;
- queues;
- microservices;
- Kafka;
- vector database for deterministic facts.

## Performance targets for pilot

Suggested initial gates:

- 10k claims reconciliation under 30s locally after evidence ingestion;
- no full contract recompilation when evidence changes;
- no semantic LLM call for deterministic predicates;
- semantic calls batched/cached by evidence hash and predicate schema;
- rerun after a small evidence delta recalculates only affected claims/facts.

## Cutover gates

AIR/verified runtime can become financial authority only after:

1. existing 10k demo exact line-level equivalence;
2. zero unexplained money mismatches;
3. all needs-review/contradictory fixtures match intended semantics;
4. cross-domain corpus passes;
5. compiler assurance blocks seeded semantic defects;
6. every final dollar has clause-to-evidence provenance;
7. full Ruff/ESLint/Vitest/Playwright/build suite passes.

## UI gates

Do UI work after backend semantics stabilize.

Priority surfaces:

1. compiler assurance report;
2. unverifiable-contract coverage report;
3. proof-plan coverage;
4. clause-to-dollar trace;
5. dual-run mismatches.

Avoid a large general dashboard redesign before these are working.
