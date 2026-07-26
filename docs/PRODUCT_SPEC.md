# Evidue YC demonstration specification

Evidue reconciles the June 1–30, 2026 outcome-priced invoice from Nova
Support AI for Acme Commerce. It deterministically evaluates each claimed
outcome against contractual evidence rules; it does not use an LLM to make a
payment decision.

## Immutable demonstration result

The deterministic synthetic fixture produces 10,000 claimed outcomes at
$1.50 each ($15,000.00 submitted). Of those, 8,320 are payable ($12,480.00)
and 1,680 are disputed ($2,520.00 deduction): 720 recontacts, 360 human
completions/corrections, 300 failed downstream actions, 180 duplicates, and
120 account/action mismatches. Categories are mutually exclusive. OUT-004821
is a failed refund and is disputed.

## Rules and states

An outcome is payable only when it is in period, identifiable, has matching
account/action evidence, no duplicate in its 24-hour attribution window, no
same-intent recontact within seven calendar days, no material human completion
within 24 hours, and any promised downstream action succeeds within two hours.
Incomplete or contradictory evidence produces `needs_review`, never an
automatic deduction. The headline fixture has none; a separate fixture proves
that state.

## Product surface

FastAPI exposes the documented health, demo, contract, invoice,
reconciliation, paginated outcomes, detail, and persisted export endpoints.
The React `/demo` route shows the pre-run invoice, rules and evidence sources;
then invokes the real backend engine and presents backend-derived totals,
filters, evidence, and downloads. All screens and exports disclose: “Synthetic
demonstration data” and “Operationally realistic data generated
deterministically. No real customer or vendor data is shown.”

## Technical and financial constraints

The monorepo uses FastAPI, SQLAlchemy/SQLite, Pydantic, React/TypeScript/Vite,
Material UI, pytest, Ruff, ESLint, Vitest, Playwright, and Docker. Monetary
arithmetic uses `Decimal` and decimal-string JSON fields; totals are derived
from persisted determinations, never route or UI constants. The final
validation uses uv-managed CPython 3.13.14.
