# Decision Ledger V2 — Release Notes

## Scope

Frontend-only product/design release. Backend contract compilation, approval persistence, evidence normalization, deterministic reconciliation, settlement authority, exports, and API schemas are unchanged.

## Customer-facing changes

- Landing page now presents Evidue as a financial investigation: vendor claim, substantiated amount, unsupported amount, review exposure, authority, proof, and action.
- Added a shared four-stage control grammar: Interpret → Authorize → Verify → Act.
- Added a reusable claim-level Decision Ledger showing vendor claim, governing authority, customer proof, factual determination, financial impact, and commercial action.
- `/try` now separates the human rule-approval interaction from the claim-verification interaction.
- Protected pilot uses the same Decision Ledger in Review, using persisted `contract_clauses` and `evidence` from the determination record.
- Verification and invoice-record surfaces now use the same financial equation used by the public experience.
- Workspace overview, authentication, contact, and legacy demo help surfaces now share the same control grammar.
- Theme radius and visual semantics were tightened around warm paper, deep ink/navy, teal authority, red contradiction, and amber review states.

## Trust boundary

The public demo's UI separates approval and verification so the authority boundary is legible. The existing backend endpoint continues to persist human approval and run reconciliation atomically when verification is executed. No LLM adjudication path was introduced.

## Validation performed in the artifact build environment

- TypeScript/TSX syntax transpile across `frontend/src`: PASS.
- CSS parse: PASS.
- Repository hygiene: PASS.
- Public privacy check: PASS.
- Demo branding check: PASS.

Dependency-backed lint, Vitest, Vite build, backend pytest, and Playwright must be run in the normal Evidue checkout with dependencies installed via `./scripts/dev-check.sh full`.
