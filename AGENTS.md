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

Evidue is a contract-verification and settlement-reconciliation product, not a
contract lifecycle management (CLM) system.

Allowed generalized scope:

- agreement-bundle ingestion and effective-document resolution
- contract-to-obligation / Agreement IR compilation
- human approval of immutable compiled agreement versions
- proof requirements and evidence-capability planning
- evidence and work reconstruction
- deterministic and narrowly model-assisted fact extraction
- deterministic obligation evaluation and settlement reconciliation
- operator authentication required for the secure pilot
- PDF text extraction required for contract/evidence ingestion

Do not add:

- public user registration or broad multi-tenant account management
- product billing or automated payments
- contract authoring, negotiation, e-signatures, renewals, or generic legal storage
- OCR unless text extraction genuinely cannot read a required pilot document
- vendor-specific reconciliation branches for Sierra, Fin, Zendesk, Salesforce, etc.
- microservices, Redis, background queues, or Kubernetes
- chat interfaces
- unrelated analytics

External LLM use is allowed only behind the compiler / semantic-fact boundaries.
An LLM must never adjudicate invoice lines or calculate the payable amount.

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
## Product design

Before modifying the frontend, read:

- docs/BRAND_GUIDELINES.md
- docs/DESIGN_SYSTEM.md
- docs/UX_REDESIGN_SPEC.md
- docs/MOBBIN_REFERENCE_BOARD.md

The product must look like an audit-grade financial control workspace.
Do not add generic AI gradients, sparkle motifs, excessive cards, glass effects,
or decorative charts. Preserve the primary workflow:

Decision → Findings → Contract rules → Evidence

## Contract compiler safety boundary

The contract compiler is a two-pass interpretation system:

1. source-grounded Atomic Contract Requirement Ledger;
2. AIR proposal constrained by that ledger;
3. deterministic lowering, coverage/data-dependency assurance, human approval;
4. deterministic adjudication and settlement.

Rules for compiler work:

- One atomic requirement represents one independently testable contractual proposition.
- Do not collapse several `and` / `or` / `unless` / `except` branches into one generic norm when they can independently change money.
- Every executable norm and settlement policy must bind to its atomic requirement.
- Claim/invoice/batch data must be evaluated directly and must not become indeterminate because unrelated external evidence is absent.
- Customer-evidence conditions require proof requirements.
- Missing, collapsed, source-mismatched, or unsafe material requirement bindings must block AIR approval.
- Invalid model artifacts are discarded fail-closed after bounded repair; never invent replacement executable semantics.
- Qualification must distinguish source coverage from atomic-requirement coverage and full semantic fidelity.

See `docs/ATOMIC_REQUIREMENT_LEDGER.md` and `docs/CONTRACT_QUALIFICATION.md` before changing compiler semantics.

## Handoff quality gate

Do not hand a user a repository and ask them to clean up formatter, linter, or routine test failures.
Before any code handoff, the implementing agent must run the repository wrappers and fix failures itself.

Normal commands:

- `./scripts/check-fast.sh` — bootstrap Python quality tools and run the offline verification kernel.
- `./scripts/check-all.sh` — bootstrap all dependencies and run Ruff, the complete backend suite, frontend lint/tests/build, and Playwright E2E.
- `./scripts/fix-and-check.sh` — apply only Ruff's safe mechanical fixes, format, lint, and rerun the offline kernel.
- `./scripts/check-live.sh ...` — pinned live-provider qualification only.
- `./scripts/check-release.sh ...` — complete offline gate plus pinned live-provider qualification.

`full` must never call an LLM provider. Live-provider availability must not be confused with deterministic product correctness. Never use Ruff `--unsafe-fixes` as a blanket cleanup step. If a check cannot be executed because the execution environment cannot obtain dependencies, report that limitation explicitly rather than claiming it passed.
