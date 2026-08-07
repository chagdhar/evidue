# RFC 004 — Settlement Runtime and Clause-to-Dollar Provenance

Status: Design baseline; core implemented in `product-complete`
Depends on: RFC 001, RFC 003

## Decision

Obligation evaluation and financial settlement are separate deterministic stages.

The legal runtime determines contractual status. The settlement runtime calculates financial consequences from those statuses.

## Obligation result

Each norm evaluation returns:

```text
SATISFIED
VIOLATED
INDETERMINATE
NOT_APPLICABLE
```

with:

- decisive predicate IDs;
- decisive fact IDs;
- source clause IDs;
- reason code;
- runtime version.

## Settlement algebra

The settlement engine supports a small typed algebra:

- `CONSTANT`
- `FIELD`
- `ADD`
- `SUBTRACT`
- `MULTIPLY`
- `DIVIDE`
- `COUNT`
- `SUM`
- `RATE_TABLE`
- `TIERED_RATE`
- `PERCENTAGE`
- `MIN`
- `MAX`
- `CAP`
- `FLOOR`
- `PRORATE`
- `ROUND`
- `IF_STATUS`

Money operations use `Decimal` only.

Unknown/indeterminate eligibility cannot silently become zero or payable. It produces a review bucket according to approved settlement policy.

## Settlement DAG

Compile settlement policy into a DAG rather than evaluating a free-form expression recursively every time.

Benefits:

- type checking once at approval;
- reusable subexpressions;
- deterministic hashing;
- incremental recomputation;
- transparent trace steps.

## Settlement trace

Every calculation emits nodes:

```text
submitted amount
eligible quantity
contract rate
exclusion adjustment
service credit
minimum commitment adjustment
cap/floor
payable amount
```

Each trace node includes:

```text
expression_node_id
input values
output value
source_clause_ids
norm_result_ids
fact_ids
runtime_version
```

## Financial invariant

For invoice reconciliation:

```text
submitted = payable + disputed + needs_review
```

This must be asserted at line, invoice, export, and comparison boundaries.

## Clause-to-dollar trace

Target API:

```text
GET /api/pilot/claims/{claim_id}/trace
```

Response hierarchy:

```text
CommercialClaim
  -> source invoice line
  -> applicable clauses
  -> norms
  -> proof requirements
  -> facts
  -> evidence
  -> obligation determinations
  -> settlement trace
  -> final bucket and amount
```

This should become the primary audit surface in the pilot UI.

## Example

```text
OUT-004821 — $1.50

Clause §4.2
  "No qualifying recontact within 7 days"

Predicate P17
  no_same_intent_recontact_within_7d

Fact F91
  FALSE
  evidence: conversation reopened after 2d

Norm N4
  VIOLATED

Settlement S2
  eligible = false

Result
  disputed: $1.50
```

## Aggregation

Invoice-level settlement is an aggregation of immutable claim-level settlement lines.

Do not recalculate historical lines when a new AIR version is approved. A rerun creates new lines linked to the new AIR/fact snapshot.

## Acceptance gates

- every cent in a final settlement line has a trace path to clause + fact/evidence;
- line amounts sum exactly to invoice totals;
- no float enters money calculations;
- indeterminate facts cannot silently become disputed or payable;
- settlement DAG hash is stable for the same approved contract graph.
