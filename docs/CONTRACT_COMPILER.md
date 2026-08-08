# Contract compiler and deterministic financial engine

## Core safety boundary

Evidue uses an LLM to **propose an interpretation of contract language**. The proposal cannot execute arbitrary code and cannot adjudicate invoice lines. A human-approved Agreement IR (AIR) is the only contractual authority consumed by the deterministic reconciliation engine.

```text
contract documents
  -> deterministic source spans
  -> structured LLM proposal
  -> Pydantic validation
  -> deterministic source binding
  -> AIR lowering + assurance
  -> human approval / immutable version
  -> deterministic reconciliation
```

The LLM is not called to decide payable/disputed/needs-review or to calculate final money after AIR approval.

## Provider architecture

Native contract compilation is provider-independent. Production chooses a server-configured primary provider and may use a server-configured fallback for transient availability failures. Current adapters include Gemini and OpenAI.

Customers never provide LLM credentials. Provider keys live only in server/deployment secrets.

Typical server configuration:

```bash
export EVIDUE_LLM_PRIMARY=gemini
export EVIDUE_LLM_FALLBACK=openai       # optional
export GEMINI_API_KEY='...'
export GEMINI_MODEL='...'
export OPENAI_API_KEY='...'             # only if OpenAI is configured
export OPENAI_MODEL='...'
```

The product configuration API exposes only secret-free readiness metadata such as provider, model, configured state, and `customer_key_required=false`.

## Availability behavior

The provider layer performs bounded retry with exponential backoff and jitter for transient HTTP/network failures such as 429/500/502/503/504. Non-retryable validation/bad-request failures fail immediately. Production may fall back to a second configured provider; controlled qualification pins one provider and disables fallback.

Provider failure never changes an already-approved AIR or the result of deterministic reconciliation.

## Independent compiler assurance

Production can optionally configure `EVIDUE_LLM_ASSURANCE_PROVIDER` (and an optional
`EVIDUE_LLM_ASSURANCE_MODEL`). The source packet is compiled independently, both candidates are
lowered, and Evidue compares normalized material semantics rather than generated prose or IDs.
If the compilers materially disagree, Evidue adds a blocking diagnostic and routes the candidate
to human review. It never lets models vote on the financial interpretation. If the explicitly
required assurance provider is unavailable, approval also fails closed.

This is an optional safety layer, not the source of financial authority; the approved AIR remains
the only input to deterministic adjudication.

## Contract-change financial impact

A pending AIR version can be replayed against an existing invoice and its already accepted
evidence before approval through:

```text
GET /api/pilot/air-versions/{candidate}/financial-impact?invoice_id=...
```

The response shows normalized semantic changes, exact payable/disputed/needs-review deltas, and
which invoice lines would change. It is explicitly marked `simulation_only=true`; the baseline
approved AIR remains financial authority until the candidate is human-approved. This turns an
amendment/rule change into a measurable finance control event without putting an LLM in the money
path.

## Historical invoice replay

An already-approved AIR can be replayed across all accepted historical invoices uploaded for the
same contract through:

```text
GET /api/pilot/contracts/{contract_id}/historical-replay
```

This is a non-persistent analysis path intended for low-friction pilots and retrospective vendor
invoice reviews. It uses the same deterministic adjudicator as normal reconciliation, performs no
LLM call, verifies money conservation per invoice and in aggregate, and refuses to run with a
stale or non-approved AIR. Invoices without accepted claims are reported as `not_ready` rather than
silently disappearing. The output is not a payable instruction and must not be presented as
recovered savings.

## Source provenance

Model-authored quotations are not trusted as source authority. Evidue deterministically segments original documents into immutable source spans. The model selects span IDs; Evidue validates that the spans exist, belong to the correct document, are ordered/consecutive where required, and then retrieves the original bytes itself.

Evidue calculates source offsets and SHA-256 hashes. It does not use fuzzy or semantic quote matching to manufacture provenance.

## Redacted contract parameters

Public filings often contain `[***]` or other redaction markers. Missing rates, windows, dates, percentages, thresholds, or other material parameters must remain unknown. The native prompt explicitly forbids guessing these values and the qualification system contains hard-fail checks for invented critical parameters.

## Human authority and stale AIR

A generated proposal remains non-authoritative until approved. AIR versions are immutable/versioned. If the governing contract bundle changes, the previously approved AIR becomes stale and reconciliation is blocked until the new governing documents are compiled and approved.

The pilot fails closed on a governing-document change inside one configured reconciliation period rather than silently blending two policies.

## Decision traceability

Reconciliation details now include a deterministic `trace` graph. For a disputed dollar the graph links, where applicable:

```text
financial decision
  -> invoice claim
  -> approved norm/settlement policy
  -> immutable contract source clause + hash
  -> proof requirement
  -> persisted evidence event(s)
```

A disputed decision without an approved rule or contract source is explicitly marked as an incomplete trace rather than silently presented as auditable.

## Verification readiness

Approved AIR proof requirements are compared with available evidence-source capabilities before reconciliation. Verification-plan responses include a finance-friendly readiness summary with:

- readiness percentage;
- ready / partial / unavailable requirement counts;
- missing fact types;
- missing capabilities such as identity or absence proof;
- blocking proof requirements.

This lets the operator see what the contract requires that the current evidence set cannot yet prove.

## Qualification

See `docs/CONTRACT_QUALIFICATION.md` for independent gold standards, hard safety gates, semantic stability, mutation tests, controlled exact-dollar scenarios, and real executed-contract qualification.
