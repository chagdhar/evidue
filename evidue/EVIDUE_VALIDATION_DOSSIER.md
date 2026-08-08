# Evidue Validation Dossier

This document records evidence that actually exists in this repository. It intentionally distinguishes deterministic product proof from live-model qualification and market validation.

## Current verified core proof

Run:

```bash
./scripts/evidue-proof.sh core
```

The proof runner generates `artifacts/validation/latest.json` and `latest.md` from the commands it actually executed.

In the repository state packaged on 2026-08-08, the offline/core proof executed successfully in the inspection environment:

- Python syntax compilation: PASS
- verification-kernel test group: PASS
- controlled contract-to-dollar qualification: PASS
- product smoke: PASS

The controlled synthetic outcome-pricing qualification produced:

| Metric | Measured result |
|---|---:|
| Gold status | human_reviewed controlled synthetic truth |
| Critical financial-term recall | 100.0% |
| Hard safety failures | 0 |
| Financial scenarios | 8 / 8 passed |
| Financial conservation | PASS |
| Billed | $12.50 |
| Payable | $1.50 |
| Disputed | $8.00 |
| Needs review | $3.00 |

The fixture is explicitly synthetic and exists to test exact behavior. These numbers are **not customer savings** and are not market validation.

## What the controlled proof establishes

The controlled pack exercises:

```text
contract source
  -> deterministic source-bound native proposal
  -> Agreement IR lowering
  -> independent gold scoring
  -> deterministic invoice/evidence adjudication
  -> exact Decimal financial totals
```

It also tests that reconciliation works without LLM credentials, that provider configuration cannot change results for an already-approved/fixed AIR, that financial conservation holds, and that disputed decisions can be traced back to approved rules and hashed contract source clauses.

## Real executed-contract status

The DemandTec / Target SEC-filed agreement is present under:

```text
qualification/downloaded/sec-demandtec-target-2010
```

A source-ingestion defect was discovered during this work: the earlier downloader requested gzip content but wrote the compressed transport bytes directly to a `.html` file. That means the earlier successful Gemini smoke run did **not** constitute a valid real-contract result and must not be cited.

The defect has been repaired:

- the fetcher requests identity encoding and still decodes gzip/deflate when received;
- document ingestion detects gzip magic bytes even if transport metadata is lost;
- invalid/block/error pages are rejected before compilation;
- the stored SEC artifact is now decoded HTML;
- the manifest records raw transport and decoded content SHA-256 hashes;
- a truthful provisional engineering gold was rebuilt from the decoded agreement;
- explicit redaction traps require `[***]` values to remain unknown/non-executable.

A **new live provider run against the repaired SEC document is NOT MEASURED in this packaged environment** because no provider credential is supplied here. The current SEC gold is `provisional_engineering_gold` and non-exhaustive, so even a successful run must remain `review_required` until independent review is completed.

## Provider independence

The native compiler uses a provider-independent structured-inference layer with current Gemini and OpenAI adapters, bounded retry for transient failures, optional production fallback, pinned-provider qualification, and secret-free provenance. Credentials are server-owned; the product does not require customers to provide an LLM key.

Provider adapters are unit-tested with mocked HTTP behavior. This package does not claim that both providers were live-network tested in the inspection environment.

## Independent compiler assurance and contract-change impact

The repository now contains a deterministic compiler-consensus gate. When a server operator
configures a second provider/model, both source-grounded candidates are compared by normalized
material semantics. Agreement produces no extra authority; material disagreement produces a
blocking diagnostic and requires human review. The unit suite tests both agreement and material
disagreement behavior without making live-provider quality claims.

The pilot also exposes a pre-approval financial-impact simulation for AIR changes. It replays the
same normalized invoice claims and accepted evidence through an approved baseline AIR and a
candidate AIR, then reports exact Decimal deltas and affected lines. The simulation cannot change
financial authority and performs no LLM call.

## Traceability and evidence readiness

Reconciliation details expose a deterministic decision trace graph linking financial decisions to claims, approved AIR rules, original source clauses/hashes, proof requirements, and persisted evidence events. Disputed decisions with missing contractual provenance are explicitly marked incomplete.

Verification-plan responses also expose a readiness summary showing which approved contractual proof requirements are ready, partial, or unavailable with the evidence sources currently supplied.

The pilot now also supports a non-persistent historical invoice replay over all accepted invoices
for a contract. It uses a human-approved, non-stale AIR; performs deterministic adjudication with
no LLM call; reports exact aggregate payable/disputed/needs-review totals; checks money
conservation; and leaves the reconciliation-run ledger unchanged. This is an analysis surface for
historical pilot validation, not evidence of vendor acceptance or recovered savings.

## Explicit non-claims

This dossier does not claim:

- legal review or legal correctness of the SEC engineering gold;
- production certification;
- customer adoption or willingness to pay;
- recovered savings;
- that public commercial terms are executed customer agreements;
- that semantic stability alone proves correctness;
- that every contract term is safely automatable.

The next external technical evidence required is a new pinned-provider live qualification against the repaired SEC pack plus live mutation runs against the controlled outcome-pricing pack.
