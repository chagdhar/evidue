# Product-Complete Branch Validation — 2026-08-07

## Scope

This release completes the agreed controlled-beta product path:

```text
workspace → agreement → AI proposal → compiler assurance → human approval
→ invoice mapping → customer evidence → identity review → deterministic AIR reconciliation
→ exception review → corrected invoice / review artifacts
```

The financial authority is the approved AIR plus normalized customer evidence. No model call occurs while adjudicating invoice lines.

## Implemented release gates

- first-class atomic predicates and proof references;
- exact source-span/hash grounding and material-coverage approval gates;
- deterministic compiler assurance and mutation/execution probes;
- immutable AIR lifecycle with active/superseded versions;
- generic AIR adjudication with deterministic settlement;
- conservative absence proof and automatic evidence capability planning;
- paste/TXT/Markdown/DOCX/text-PDF agreement ingestion;
- arbitrary invoice CSV preview and mapping;
- CSV/JSON/JSONL evidence ingestion, authoritative matching, manual identity confirmation;
- line-level clause + evidence provenance;
- append-only reconciliation reruns;
- corrected-invoice CSV, dispute CSV, summary/evidence JSON, and HTML review report;
- workspace-scoped databases, access-key authentication, and audit history;
- first-run sample workspace and confirmed workspace reset;
- finance/operator `/pilot` workflow with compiler internals moved under Advanced.

## Validation performed in the build environment

- Backend tests: **189 / 189 passed**, run module-by-module across all eight backend test modules.
- Product smoke: passed with 3 sample lines → 1 payable, 1 disputed, 1 needs review; billed `$4.50`, payable `$1.50`, disputed `$1.50`, needs review `$1.50`.
- Product smoke asserts `financial_authority = approved_air` and `llm_required_for_reconciliation = false`.
- Python changed-file syntax/compile validation: passed.
- `pyproject.toml` and `uv.lock` TOML parse: passed.
- `git diff --check`: passed.
- Updated product TypeScript/TSX and Playwright files parse/transpile successfully with the globally available TypeScript compiler.

## Environment-limited checks

The current execution environment forces npm through an internal package mirror. That mirror returns a missing-package error for `yocto-queue@0.1.0`, while direct access to `registry.npmjs.org` is unavailable. Therefore a fresh frontend dependency install, Vitest/build, and Playwright browser run could not be executed here. The Playwright product scenario has been updated to the new first-time-user/sample-workspace flow and should be run with:

```bash
./scripts/dev-check.sh full
```

on a registry-capable machine before hosted deployment.

Ruff is part of the repository dev dependency group, but this same offline resolver cannot materialize it because the uv cache lacks the project's FastAPI dependency. Python compilation, backend tests, and `git diff --check` passed; run the normal `dev-check` gate after dependency installation to execute Ruff as well.

## Controlled-beta boundary

This branch is usable as an operator-assisted product. It intentionally does **not** claim enterprise managed identity, PostgreSQL/managed multi-tenancy, background job infrastructure, or live SaaS connector breadth. Those are post-core deployment/scale milestones documented in `NEXT_BUILD.md`; they do not change the contract-authority or deterministic-reconciliation architecture.
