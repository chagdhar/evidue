# Evidue demonstration specification

Evidue reconciles the June 1–30, 2026 outcome-priced invoice from Nova
Support AI for Acme Commerce. It deterministically evaluates each claimed
outcome against contractual evidence rules; it does not use an LLM to make a
payment decision.

## Public proof result

`/try` is the canonical public proof. It uses a bounded 100-claim synthetic sample: $150.00 billed, $124.50 substantiated, and $25.50 identified for dispute in the recorded baseline. The values are produced by the deterministic engine after explicit rule approval; the frontend does not hardcode the adjudication result.

After the result, `/try` can inspect representative findings inline with contract authority, customer-side evidence, source-record provenance, outcome receipt metadata, reproducibility details, and a vendor-ready dispute summary.

## Deterministic fixture catalog

The repository keeps focused synthetic fixture scenarios for automated testing and developer qualification. They are not exposed as a separate customer-facing frontend route:

- `headline`: 10,000 claims; 8,320 payable; 1,680 disputed; $15,000.00
  submitted; $12,480.00 payable; $2,520.00 deduction; $0.00 review.
- `evidence_review`: two claims, one payable and one with contradictory directly
  matched downstream evidence; $3.00 submitted; $1.50 payable; $0.00
  deduction; $1.50 held for review.
- `recovery`: a failed first downstream action followed within 24 hours by an
  otherwise-valid claim for the same customer and intent; $3.00 submitted;
  first claim disputed R3; second claim payable; $1.50 deduction.
- `duplicate_window`: three otherwise-payable claims for the same customer and
  normalized intent within 24 hours; $4.50 submitted; earliest claim payable;
  later two disputed R4; $3.00 deduction.

Scenario metadata contains only names, explanations, and the highlighted
outcome ID. Financial values always come from persisted determinations, never
from scenario display metadata.

## Rules and states

An outcome is provisionally payable only when it is in period, identifiable,
has matching account/action evidence, has no same-intent recontact within seven
calendar days, has no material human completion within 24 hours, and any
promised downstream action succeeds within two hours. R4 duplicate attribution
then applies only among these otherwise-payable claims. For each customer and
normalized intent, the earliest provisional claim in a 24-hour window remains
payable and later provisional claims are disputed; close time and then outcome
ID determine the winner. A disputed or needs-review claim can never be the
duplicate winner. Incomplete or contradictory evidence produces
`needs_review`, never an automatic deduction. The headline fixture has none; a
separate fixture proves that state.

## Product surface

- `/` — positioning and financial example
- `/try` — no-signup public proof and inline inspection
- `/contact` — customer discovery / sales
- `/workspace/*` — protected customer product

The retired standalone public demo shell has no frontend route. The public proof does not expose a duplicate invoice list, scenario lab, vendor-preflight product, or separate contract/evidence pages; their useful proof elements are progressively disclosed inside `/try`.

## Technical and financial constraints

The monorepo uses FastAPI, SQLAlchemy/SQLite, Pydantic, React/TypeScript/Vite,
Material UI, pytest, Ruff, ESLint, Vitest, Playwright, and Docker. Monetary
arithmetic uses `Decimal` and decimal-string JSON fields; totals are derived
from persisted determinations, never route or UI constants. The final
validation uses uv-managed CPython 3.13.14.

## Two-sided expansion: Evidue Prove and Evidue

Evidue now presents two strictly separated product surfaces built on a shared outcome ledger.

### Evidue Prove — vendor preflight

Before invoicing, an AI-agent vendor can run the same deterministic rules against its proposed outcome claims to identify:

- unsupported claims that should not be invoiced;
- missing downstream evidence;
- premature agent closure;
- duplicate attribution;
- account and action mismatches; and
- revenue at risk by rule, workflow, and outcome.

This surface answers: **Can the vendor defend this charge?**

It may help a vendor improve evidence or remove unsupported claims, but it cannot access customer-private evidence, change customer-approved contract rules, or control the customer's payment recommendation.

### Evidue — customer reconciliation

The customer workspace remains the authoritative financial control. It independently joins vendor claims to the customer's contract and systems of record, then classifies each charge as payable, disputed, or needs review.

This surface answers: **Should the customer pay this charge?**

### Shared outcome ledger

Each claimed outcome is represented by a versioned proof envelope containing stable identifiers, agent/workflow version, claimed action, timestamps, evidence references, contract-rule version, and source provenance. An outcome receipt supports a claim; it never self-declares the charge payable.
