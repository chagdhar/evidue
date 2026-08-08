# Evidue Verification-Kernel Leap — 2026-08-08

## What changed

This pass turns the previous qualification scaffolding into a coherent verification kernel rather than adding another UI layer.

### 1. Repaired the source-of-truth boundary

The SEC downloader had stored gzip transport bytes as `.html`. The fetcher and document loader now decode transport encoding safely, detect gzip magic bytes, reject obvious block/error artifacts, and record raw/decoded hashes. The existing SEC file was repaired to actual HTML and its manifest/gold rebuilt from the real decoded agreement.

### 2. Added provider-independent native contract compilation

`backend/app/agreements/providers.py` supplies structured provider adapters, retries, production fallback, pinned qualification, secret-free status/provenance, and server-owned credential behavior. `native_compiler.py`, the pilot native compile path, and qualification live runs use this layer.

### 3. Strengthened qualification into a safety gate

Gold can express critical financial materiality, forbidden numeric interpretations, redacted values that must remain unknown, terms that must remain non-executable, expected diagnostics, semantic section deltas, and exact-dollar scenarios. Hard failures cannot be hidden by aggregate scores.

### 4. Added a controlled end-to-end financial truth pack

`qualification/fixtures/outcome-pricing-e2e` supplies source contract text, a deterministic source-bound native proposal, exhaustive reviewed controlled gold, eight financial scenarios, and three live mutation cases. Offline qualification currently produces exact totals of $12.50 billed / $1.50 payable / $8.00 disputed / $3.00 needs review with conservation passing.

### 5. Added deterministic decision trace graphs

Each product reconciliation detail now includes a `trace` graph connecting the financial decision to the invoice claim, approved rule/policy, original source clauses/hashes, proof requirements, and evidence events. An untraceable disputed decision is explicitly incomplete.

### 6. Added evidence-readiness summaries

Verification plans now expose a finance-friendly readiness view: percentage, ready/partial/unavailable counts, missing fact types/capabilities, and blocking proof requirements.

### 7. Added independent compiler disagreement gates

An optional second provider/model can independently compile the same immutable source packet.
Evidue compares normalized contractual semantics; material disagreement becomes a blocking
human-review diagnostic instead of being resolved by model voting.

### 8. Added pre-approval financial impact simulation

A candidate AIR can be replayed against an existing invoice/evidence set before approval. The
product reports exact line changes and payable/disputed/needs-review deltas while preserving the
approved baseline AIR as the only financial authority. This gives contract amendments a measurable
financial impact surface without invoking an LLM during adjudication.

### 9. Added non-persistent historical invoice replay

Finance can replay every accepted historical invoice for a contract through one human-approved
AIR without creating reconciliation runs or invoking an LLM. The replay reports per-invoice and
aggregate exact Decimal totals, explicit not-ready invoices, and conservation checks. This creates
a low-friction pilot path from historical exports to an independently calculated payable picture
without mislabeling identified disputes as recovered savings.

### 10. Added one-command proof output

`./scripts/evidue-proof.sh core` runs the offline verification kernel and writes machine/human-readable validation artifacts. `live` adds pinned provider qualification. `full` adds the broader repository/frontend gates in a fully bootstrapped checkout.

## Important correction

Do not cite the earlier SEC Gemini smoke run as real-contract evidence. It used a transport-compressed artifact before the ingestion defect was discovered. A new live run is required against the repaired decoded document.

## Next highest-value milestone

Run a pinned live provider over:

1. the repaired DemandTec/Target SEC pack; and
2. the controlled outcome-pricing pack with 3 runs + metamorphic mutations.

Then have an independent reviewer audit the SEC gold. After that, expand the corpus with another executed SaaS agreement and current public outcome-priced AI commercial terms, preserving the distinction between executed agreements, public commercial terms, and synthetic controlled fixtures.

## Validation performed in this build environment

Measured on 2026-08-08 in the packaged inspection environment:

- `./scripts/evidue-proof.sh core`: **PASS**
- verification-kernel selection: **71 passed**
- controlled contract-to-dollar qualification: **PASS**
  - billed: **$12.50**
  - payable: **$1.50**
  - disputed: **$8.00**
  - needs review: **$3.00**
  - money conservation: **PASS**
- product smoke: **PASS** (`financial_authority=approved_air`, `llm_required_for_reconciliation=false`)
- all **248 collected backend tests** were exercised successfully across segmented pytest runs; a single monolithic invocation exceeded the inspection-container timeout, so the claim is based on the complete segmented file set rather than one uninterrupted command.
- Ruff was not available in this offline container, so Ruff formatting/lint is **NOT MEASURED here** and must be rerun in the user's bootstrapped checkout.
- frontend dependencies were not present in this archive, so frontend lint/tests/build are **NOT MEASURED here** and must be rerun after `npm ci`/the normal setup.
- repaired SEC live-provider qualification is **NOT MEASURED here** because no provider secret is supplied to the inspection environment.

These limitations are intentional non-claims, not hidden passes.
