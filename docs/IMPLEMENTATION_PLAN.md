# Implementation plan

## Synthetic scenario expansion

1. Add a fixture-owned scenario catalog with the exact results frozen in
   `PRODUCT_SPEC.md`.
2. Persist the active scenario and expose catalog/status metadata through typed
   API responses.
3. Make reset, reconciliation, invoice totals, outcomes, evidence, and exports
   operate on the selected scenario without special-case financial logic.
4. Keep `/demo` fixed to the headline invoice and add the API-backed scenario
   selector to `/demo/lab`; selection returns to an honest pre-reconciliation
   state.
5. Adapt the decision flow for dispute-free review scenarios and highlight each
   scenario's example outcome.
6. Add domain/API/frontend/Playwright regressions, then run full, Docker, and
   isolated-checkout validation.

## 0. Specification and architecture

Objective: freeze product behavior and system boundaries. Files: `docs/`.
Work: specification, architecture, status and plans. Acceptance: exact rules,
totals, provenance, disclosure and runtime assumption documented. Tests:
documentation review. Validation: `git diff --check`. Risk: ambiguous runtime
version. Completion commit: `docs: freeze product specification`.

## 1. Repository foundation

Objective: create runnable Python/frontend project foundation. Files:
`pyproject.toml`, `backend/`, `frontend/`, `scripts/`, Docker files. Work:
tooling/configuration. Acceptance: bootstrap and static checks run. Tests:
smoke health. Validation: Ruff, pytest, npm checks. Risk: dependency/network
availability. Completion commit: `build: establish project foundation`.

## 2. Deterministic domain engine

Objective: model clauses, claims, evidence and pure evaluation. Files:
`backend/app/domain`, `backend/app/fixtures`, `backend/tests`. Work: fixture
generation and rule engine. Acceptance: exact totals/categories and review
fixture. Tests: every contractual rule, provenance, determinism. Validation:
pytest and Ruff. Risk: category overlap. Completion commit: `feat: add deterministic reconciliation engine`.

## 3. Persistence and API

Objective: persist seed and determinations and expose API/exports. Files:
`backend/app/db`, `backend/app/api`, tests. Work: SQLite repository and
endpoints. Acceptance: pagination/filter/order/detail/export consistency.
Tests: API suite. Validation: pytest/Ruff. Risk: totals diverging from records.
Completion commit: `feat: add reconciliation API and exports`.

## 4. Frontend demonstration

Objective: implement direct `/demo` golden path. Files: `frontend/src`, tests.
Work: backend-driven UI, filter/detail/download states. Acceptance: disclosure,
run flow, values and failed-refund timeline visible. Tests: Vitest. Validation:
ESLint, Vitest, build. Risk: stale frontend state. Completion commit: `feat: build YC demo interface`.

## 5. Exports, Playwright, scripts, and Docker

Objective: package reproducible local and production demo. Files: `e2e`,
`scripts`, Docker, docs. Work: checks, E2E and container asset serving.
Acceptance: full checks and image workflow. Tests: Playwright. Validation:
scripts/Docker. Risk: browser/container availability. Completion commit: `build: package demonstration`.

## 6. Adversarial review and hardening

Objective: detect financial, attribution, determinism and UX faults. Files:
all relevant tests/docs. Acceptance: findings fixed with regression tests.
Validation: full check. Risk: hidden coupling. Completion commit: `test: harden reconciliation behavior`.

## 7. Clean-checkout verification

Objective: verify a fresh clone independently. Files: `docs/FINAL_VALIDATION.md`.
Acceptance: bootstrap, checks, image/container and clean-checkout evidence
recorded truthfully. Validation: documented commands. Risk: network/Docker
availability. Completion commit: `docs: record final validation`.

## Completion record

- Milestone 0: `082e5e0`
- Milestones 1–5 prototype checkpoint: `04e4abb`
- Corrective deterministic-rule checkpoint: `5920ba9`
- Persisted domain, fixture, SQLAlchemy, API, and backend-test rebuild:
  `f7860da`
- Complete React workflow, Vitest, and Playwright golden path: `4ed9a4d`
- Production Docker and handoff documentation: `6aa05d1`
- Clean-checkout reproducibility fix: `5836117`
- Final validation record and generated-file cleanup: `523643e`
