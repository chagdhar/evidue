# Evidue Product v1 — Implemented Increment

This increment productizes the qualified agreement and verification kernel without changing its authority boundary. The compiler, Atomic Requirement Ledger, approved AIR, evidence/fact runtime, and deterministic determinations remain the source of machine financial truth. Human finance operations are modeled as explicit overlays and approvals around those immutable outputs.

## Delivered

- First-class product organization, vendor, and vendor-engagement records.
- Contract and invoice links from the existing pilot substrate into recurring vendor engagements.
- Deterministic reconciliation input-manifest and calculation fingerprints.
- Operational review cases generated from `needs_review` determinations.
- Append-only review decisions (`payable`, `disputed`, `escalated`) that never rewrite the original machine determination.
- Reconciliation statements that separate machine amounts, review overlays, open exposure, and final recommended payable/disputed amounts.
- Finance approval gate that blocks approval while unresolved review exposure remains.
- Immutable approval records tied to reconciliation and calculation hashes.
- Stateful vendor dispute cases created only after finance approval.
- Dispute items sourced from both machine-confirmed disputes and review-resolved disputes.
- Printable HTML and downloadable PDF vendor-dispute packages.
- Finance-first web workspace at `/pilot/finance` with Overview, Vendors, Review queue, Settlement approval, and Disputes surfaces.
- Protected `/api/pilot/product/*` API for product workflows.
- Product architecture, domain, API, data, security, audit, connector, jobs, migration, and release design documents plus ADRs.
- End-to-end product smoke coverage for review -> approval -> dispute.

## Intentionally preserved

The existing qualified kernel remains isolated from product workflow code. In particular:

- An LLM can propose agreement structure but does not adjudicate invoice lines.
- Only approved AIR can carry financial authority.
- Deterministic determinations are immutable historical facts.
- Review decisions are overlays; they do not mutate the kernel result.
- Disputes can only be generated from an approved settlement.

## Validation performed

- All 21 backend `test_*.py` files pass when run against isolated test databases.
- Pytest collection reports 288 tests; existing suites may contain intentional skips.
- `backend/tests/test_upload.py`: 40 passed after the finance-product hooks and dispute edge-case hardening.
- Python backend compile check passes.
- Product smoke workflow passes through review, finance approval, dispute creation, state transition, PDF generation, and audit events.
- Demo branding check and Google Apps Script syntax check pass.
- Generated dispute PDF was rendered and visually inspected successfully.
- Frontend source received TypeScript syntax/static checking, but the complete frontend npm test/build gate could not be executed in the build sandbox because its package mirror could not provide `yocto-queue`. Run the repository's normal frontend/full gate in an environment with npm registry access before release.

## Next infrastructure migration

The product domain is deliberately established before infrastructure expansion. The next production-platform increment should migrate the system of record to PostgreSQL/Alembic, introduce organization membership/RBAC, add durable background jobs, and implement the connector SDK plus evidence-source health/completeness. These changes should consume the domain model delivered here rather than change the qualified kernel boundary.
