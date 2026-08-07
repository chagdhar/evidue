# Pilot operator frontend

## Goal

`/pilot` is a protected operator workspace for processing one real invoice. It is deliberately separate from `/demo`, which remains a synthetic, repeatable presentation.

## Workflow

1. Enter the pilot token. It is stored in `sessionStorage`, never in a URL.
2. Resume the active pilot state from `/api/pilot/status`.
3. Upload a contract and explicit billing metadata.
4. Compile a proposed rule program in recorded, live, or automatic mode.
5. Review machine-readable compiler diagnostics and clause coverage.
6. Approve only an approval-ready immutable rule version.
7. Upload the vendor invoice CSV and inspect accepted/rejected rows.
8. Upload customer evidence and optional identity mappings.
9. Run matching. Exact and explicit identity-map matches are accepted; heuristic matches remain review-only.
10. Confirm suggested matches with an operator rationale.
11. Run deterministic reconciliation and inspect financial totals and line-level determinations.
12. Download summary, evidence, and dispute exports.
13. Rerun after additional evidence and compare append-only runs.
14. Record customer validation separately from engine output.

## State and recovery

The frontend treats the backend as the source of truth. Refreshing the page reloads the active contract, invoice, matching counts, and latest reconciliation. Upload receipts remain visible during the current browser session, while persisted upload history is available in pilot status.

## Security boundary

The initial pilot uses a single operator token. This is not the final multi-user authentication model. The token is sent only in the `Authorization: Bearer` header. It is not logged, added to links, or stored in `localStorage`.

## Non-goals

The pilot does not add vendor accounts, generalized integrations, automated payments, or multi-tenant self-service onboarding.
