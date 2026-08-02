# Evidue Repository Instructions

## Product

Evidue independently reconciles outcome-priced AI-agent vendor invoices
against contractual billing rules and customer-owned operational evidence.

The YC demo must prove one complete workflow:

contract
→ executable billing rules
→ vendor claims
→ operational evidence
→ deterministic determinations
→ corrected payable amount
→ dispute package

## Core result

The deterministic synthetic demonstration must calculate:

- 10,000 claimed outcomes
- $15,000 submitted invoice
- 8,320 payable outcomes
- 1,680 disputed outcomes
- $12,480 corrected payable amount
- $2,520 recommended deduction

Dispute categories:

- 720 same-intent recontacts
- 360 human completions or corrections
- 300 failed downstream actions
- 180 duplicate charges
- 120 account or action mismatches

## Financial correctness

- No language model decides whether money is payable.
- Use Python Decimal for all monetary calculations.
- Never use float for money.
- Every amount must derive from stored determinations.
- Every dispute must reference a contract rule and evidence.
- UI, API, CSV, JSON, and tests must agree exactly.
- Never hardcode headline totals in frontend components or HTTP routes.

## Synthetic data

Always display:

"Synthetic demonstration data"

Also display:

"Operationally realistic data generated deterministically. No real customer
or vendor data is shown."

Use fictional parties:

- Customer: Acme Commerce
- Vendor: Nova Support AI

Do not use real vendor logos or imply that real vendor data is shown.

## Technology

Use:

- Python 3.13
- uv
- FastAPI
- SQLAlchemy 2.x
- SQLite
- Pydantic
- React
- TypeScript
- Vite
- Material UI
- React Router
- Pytest
- Ruff
- ESLint
- Vitest
- Playwright
- Docker

The user's interactive shell is fish.

Repository scripts may use Bash when they begin with:

#!/usr/bin/env bash

The user must be able to invoke every script directly from fish.

## Architecture

Keep these concerns separate:

- domain entities and deterministic rules
- fixture generation
- persistence
- HTTP API
- frontend presentation
- exports

Preferred structure:

- backend/app/domain/
- backend/app/fixtures/
- backend/app/db/
- backend/app/api/
- backend/tests/
- frontend/src/
- frontend/tests/
- e2e/
- scripts/
- docs/

## Scope restrictions

Do not add:

- authentication
- registration
- multi-tenancy
- billing
- an external LLM dependency
- PDF parsing
- OCR
- real Sierra, Fin, Zendesk, or Salesforce integrations
- microservices
- Redis
- background queues
- Kubernetes
- chat interfaces
- generic contract management
- unrelated analytics

## Required scripts

The final repository must contain:

- ./scripts/bootstrap.sh
- ./scripts/dev.sh
- ./scripts/seed-demo.sh
- ./scripts/demo-reset.sh
- ./scripts/dev-check.sh fast
- ./scripts/dev-check.sh full

Use uv-run commands so the user does not need to activate a Python virtual
environment manually.

## Workflow

Before coding:

1. Inspect the environment.
2. Freeze the product specification in docs/PRODUCT_SPEC.md.
3. Create docs/IMPLEMENTATION_PLAN.md.
4. Create docs/STATUS.md.
5. Commit those documents.

During implementation:

1. Complete one milestone at a time.
2. Add tests with every milestone.
3. Run validation after every milestone.
4. Fix failures before continuing.
5. Update docs/STATUS.md continuously.
6. Commit every completed milestone.
7. Never amend or rewrite commits.
8. Never weaken tests to make them pass.
9. Never declare success without running the stated commands.

## Completion

The application is complete only when:

- a fresh checkout bootstraps successfully
- the deterministic seed produces the exact required records
- the reconciliation calculates the exact required counts and amounts
- OUT-004821 demonstrates a failed refund with operational evidence
- needs-review behavior is tested
- frontend totals come from the backend
- exports match the UI and API
- all tests pass
- production builds pass
- the Docker image builds and runs
- ./scripts/dev-check.sh full passes

Final principle:

One invoice enters. One defensible payable amount leaves.
## Design governance

Before changing product UI, read:

- docs/BRAND_GUIDELINES.md
- docs/DESIGN_SYSTEM.md
- docs/UX_REDESIGN_SPEC.md
- docs/MOBBIN_REFERENCE_BOARD.md
- docs/DESIGN_IMPLEMENTATION_PLAN.md
- docs/DESIGN_QA_CHECKLIST.md

Design invariants:

- The public product tells one buyer-side financial-control story.
- Lead with the payable decision, not the model or a generic dashboard.
- Use one primary action and one dominant work surface per page.
- Do not add decorative AI gradients, glow, glass, sparkles, or chat interfaces.
- Avoid nested cards and card-per-row layouts.
- Use semantic green, red, and amber only for payable, disputed, and review states.
- Use tables for cross-reference, lists for small explanatory sets, and drawers for record detail.
- Keep synthetic-data and LLM/deterministic trust-boundary disclosures accurate.
- Do not expose experimental routes as equal primary navigation.
- Do not implement a broad redesign in one task; follow the milestones in docs/DESIGN_IMPLEMENTATION_PLAN.md.
