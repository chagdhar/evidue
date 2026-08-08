# Evidence Model

## Ingestion layers

Each permitted source record is retained as:

1. raw payload + payload hash,
2. normalized record,
3. normalized operational event,
4. identity-match state,
5. optional deterministic fact,
6. determination evidence reference.

Supported operator file formats are CSV, JSON, and JSONL.

## Identity policy

- Direct outcome identifiers and explicit identity maps are authoritative.
- Heuristic/composite candidates are suggestions only.
- Suggested or unresolved evidence cannot affect money until manually confirmed.
- Manual confirmations record the actor, timestamp, rationale, event, and claim.

## Capability planning

Evidue infers evidence-source capabilities conservatively from normalized observed event types. An imported source can prove absence only when the operator explicitly declares that upload complete for the relevant period. A sparse upload cannot masquerade as complete system history.

## Deterministic facts

Proof requirements reference first-class atomic predicates. Fact derivation evaluates the referenced predicate against the evidence boundary, records evidence IDs, predicate/hash, authority, evaluator version, and input hash, and can be reviewed without changing the underlying evidence.

## Provenance

Every financial determination retains the decisive evidence event references. Review/export surfaces reconstruct an evidence timeline and contract-source mapping from persisted records rather than recomputing a narrative with an LLM.
