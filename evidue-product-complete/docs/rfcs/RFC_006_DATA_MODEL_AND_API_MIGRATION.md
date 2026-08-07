# RFC 006 — Data Model and API Migration

Status: Design baseline; core implemented in `product-complete`
Purpose: map the verified-runtime design onto the current repository without a rewrite.

## Current persisted primitives

The repository already persists:

- agreement bundles/documents/relations;
- AIR versions;
- evidence source descriptors;
- verification plans;
- facts;
- provenance edges;
- reconciliation runs and determinations.

The next migration should extend these tables rather than duplicate them.

## Data model changes

### 1. Atomic predicate table

Add:

```text
pilot_predicates
```

Suggested columns:

```text
id                  PK
contract_id         FK
air_version_id      FK
predicate_hash      indexed
predicate_type      indexed
subject_type
value_type
predicate_json      JSON
source_clause_ids   JSON
created_at
```

Constraint:

```text
UNIQUE(air_version_id, predicate_hash)
```

### 2. Proof requirement migration

Current proof requirements live inside `air_json`.

Add persisted projection:

```text
pilot_proof_requirements
```

Columns:

```text
id
air_version_id
norm_id
predicate_id         FK -> pilot_predicates
proof_json
created_at
```

Every proof requirement must resolve to one atomic predicate row.

### 3. Assurance persistence

Add:

```text
pilot_assurance_runs
pilot_assurance_findings
pilot_assurance_probe_results
pilot_assurance_mutation_results
```

`pilot_air_versions` gains:

```text
assurance_run_id
semantic_graph_hash
approval_gate_version
```

Approval verifies the referenced assurance run and graph hash.

### 4. Observation persistence

Current raw records/events remain authoritative ingestion records.

Add a canonical normalized projection:

```text
pilot_observations
```

Columns:

```text
id
invoice_id
source_id
raw_record_id nullable
observation_type
entity_type
entity_id nullable
event_type nullable
occurred_at nullable
payload_json
observation_hash
normalizer_version
created_at
```

Do not copy raw payload bytes into this table.

### 5. Fact extensions

Current `pilot_facts` should gain:

```text
predicate_id
verification_plan_id
source_snapshot_hash
derivation_version
effective_truth
review_policy
```

Change the logical cache key to:

```text
(predicate_id, claim_id, verification_plan_id, source_snapshot_hash, derivation_version)
```

### 6. Settlement trace

Add:

```text
pilot_settlement_traces
pilot_settlement_trace_nodes
```

Each reconciliation determination references one trace root.

Trace nodes contain:

```text
expression_node_id
operation
input_json
output_decimal
currency nullable
source_clause_ids
norm_result_ids
fact_ids
created_at
```

## Avoid new databases

Do not add Neo4j or another graph store. Typed relation rows and JSON payloads are enough for the pilot and preserve the existing SQLite/Postgres migration path.

## API evolution

### Compilation assurance

```text
POST /api/pilot/air-versions/{id}/assure
GET  /api/pilot/air-versions/{id}/assurance
GET  /api/pilot/air-versions/{id}/assurance/findings
```

AIR approval becomes:

```text
POST /api/pilot/air-versions/{id}/approve
```

with requirements:

```text
matching graph hash
passing assurance run
no blocking findings
```

### Verification execution

```text
POST /api/pilot/verification-plans/{id}/execute
GET  /api/pilot/claims/{claim_id}/facts
GET  /api/pilot/facts/{fact_id}
POST /api/pilot/facts/{fact_id}/review
```

### Provenance

```text
GET /api/pilot/claims/{claim_id}/trace
GET /api/pilot/reconciliations/{run_id}/trace-summary
```

### Contract graph inspection

```text
GET /api/pilot/air-versions/{id}/graph
GET /api/pilot/air-versions/{id}/predicates
GET /api/pilot/air-versions/{id}/definitions
```

## Service boundaries

Suggested modules:

```text
backend/app/agreements/graph.py
backend/app/agreements/assurance.py
backend/app/agreements/verification.py
backend/app/agreements/observations.py
backend/app/agreements/fact_runtime.py
backend/app/agreements/settlement.py
backend/app/agreements/provenance.py
```

Do not grow `router.py` into the business-logic layer. Router handlers should authenticate, validate transport payloads, call services, and serialize results.

## Compatibility adapters

Keep:

```text
legacy.py
```

only as a migration adapter.

The new runtime modules must not import private legacy engine helpers.

## Migration sequence

1. create tables/projections without changing old behavior;
2. backfill predicate/proof projections when a new AIR version is created;
3. run assurance on new versions only;
4. execute verification plans in shadow mode;
5. produce settlement traces in shadow mode;
6. compare against legacy determinations;
7. cut over only after acceptance gates in RFC 005.

## Rollback strategy

All new runtime output is append-only/shadow until cutover.

Rollback is therefore:

```text
disable verified runtime flags
continue legacy reconciliation
```

No destructive migration should be required for the first implementation.
