# Security Model

## Current pilot boundary

Workspace access tokens select request-local workspace context and separate workspace SQLite databases. Product endpoints use the same authorization dependency; there is no unauthenticated product-data path.

## Financial authority separation

- Agreement approval authorizes a rule version.
- Reconciliation is deterministic and cannot invoke the compiler model as adjudicator.
- Review decisions require rationale and actor.
- Finance approval is a separate authority event and is blocked by unresolved review exposure.
- Approved settlements reject subsequent review mutation.

## Production hardening backlog

PostgreSQL tenancy, organization membership, RBAC (`Admin`, `Finance Approver`, `Analyst`, `Reviewer`, `Viewer`), managed secret storage, session auth, audit export, connector credential encryption, rate limits, and SSO can be added without changing the financial domain invariants.
