# Implementation plan

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
