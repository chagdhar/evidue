# Security and Data Boundaries

## Authentication

All `/api/pilot/*` routes require a workspace access key. Configure either:

```text
EVIDUE_WORKSPACE_TOKENS={"customer-a":"<long random token>","customer-b":"<long random token>"}
```

or the legacy single-workspace `EVIDUE_PILOT_TOKEN`.

Tokens must be at least 24 characters and are compared using constant-time comparison. The browser keeps the access key in `sessionStorage` rather than persistent local storage.

## Workspace isolation

Each workspace resolves to a separate database file. The authenticated request sets a request-local workspace context before any pilot database session is created. Tests verify that data seeded with one workspace key is invisible to a different workspace key.

## Upload controls

- filenames are basename-normalized,
- uploads are limited to 50 MB,
- accepted contract/evidence/invoice formats are explicit,
- row parsing is fail-soft with retained rejection reasons,
- raw and normalized payloads are hashed,
- unknown/unsupported contract semantics block AIR approval rather than falling through.

## Financial-control boundary

- LLM use is limited to contract interpretation and optional semantic fact extraction.
- Reconciliation is deterministic and remains functional with model access disabled.
- Missing evidence is not treated as evidence of breach.
- Heuristic identity matching is non-authoritative until confirmed.
- Approved AIR and reconciliation history are append-only/immutable by policy.

## Current beta boundary

This repository uses access-key authentication and file-based workspace databases, suitable for controlled beta/pilot use. A broader SaaS deployment should move identity to an external IdP and persistence to a managed multi-tenant database while preserving the same server-side tenant filters and immutable/audit semantics.
