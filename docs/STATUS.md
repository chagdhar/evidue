# Status

## Complete

The working demonstration now covers both financial reconciliation and the production-shaped evidence path that precedes it.

Delivered:

- deterministic contract-rule engine and reproducible 10,000-claim headline fixture;
- exact headline result of $15,000 submitted, $12,480 confirmed payable, and $2,520 confirmed deductions;
- mutually exclusive payable, disputed, and needs-review financial buckets;
- persisted contracts, rules, invoices, claims, conversations, source records, connectors, ingestion batches, operational events, evidence matches, reconciliations, determinations, and evidence references;
- eight vendor/customer source types and 50,302 aggregate source-shaped records;
- 20,301 normalized operational events;
- 9,975 direct outcome-ID matches and 25 verified secondary-key matches;
- representative raw payload inspection with normalized records, hashes, schemas, source authority, match method, confidence, and rationale;
- explicit separation between collection, raw preservation, normalization, identity matching, and contract determination;
- customer evidence-readiness experience before reconciliation;
- production collection plan covering exports, read-only warehouse views/APIs, SFTP/object storage, webhooks, and incremental sync;
- vendor/customer neutrality and access-control boundaries;
- server-side filtering and pagination, evidence detail, and record-derived CSV/JSON exports;
- Evidue Prove, Outcome Ledger, Evidue, contract controls, dispute operations, data-source inspection, and technical scenario lab;
- deterministic edge-case scenarios for contradictory evidence, failed-action recovery, and duplicate attribution;
- fish-compatible setup, development, reset, and validation scripts;
- production Docker image serving React through FastAPI.
- Cloud Run deployment configuration using public scale-to-zero service settings,
  Artifact Registry images, Secret Manager binding for Gemini, and GitHub
  Actions Workload Identity Federation.
- HN-ready landing and Decision surfaces with API-derived financial messaging, a compact accounting bridge, and a featured evidence-backed dispute;
- read-only downloads for the synthetic contract, invoice, operational events, approved rule proposal, and reconciliation package;
- launch trust content covering the LLM boundary, rule-compilation metadata, current limitations, and a real invoice-review contact path;
- reordered outcome inspection with claim, contract obligation, deterministic rule inputs, timeline, provenance, and audit metadata.

## Current validation

- `./scripts/dev-check.sh full`: passed on 2026-08-02.
- Backend: 61 tests passed.
- Frontend: ESLint passed; 23 Vitest tests passed; production build passed.
- Browser: all 5 Playwright journeys passed.
- Docker: image built, health endpoint passed, and the in-container headline reconciliation reproduced 10,000 claimed, 8,320 payable, 1,680 disputed, $12,480 payable, and a $2,520 deduction.
- Cloud Run deployment configuration: GitHub Actions YAML parsed; the Docker image built and returned a healthy `/api/health` response with `PORT=8080`.

Run `./scripts/dev-check.sh full` after dependency installation to execute the repository's frontend lint, unit tests, production build, and live Playwright paths on the target machine.

## Data-retention disclosure

The demo computes the complete aggregate ingestion batch but persists representative raw payloads to keep reset time and repository size practical. It retains exact connector counts and provenance for normalized events. Production would retain all permitted raw records according to customer policy.
