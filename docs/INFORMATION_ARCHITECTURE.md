# Information Architecture

## Workspace hierarchy

```text
Workspace
├── Contracts
│   ├── Source agreement bundle
│   └── Immutable AIR versions
├── Invoices
│   └── Normalized claims
├── Evidence uploads
│   ├── Raw records
│   ├── Normalized events
│   └── Identity decisions
├── Verification plans
├── Derived facts
├── Reconciliation runs
│   ├── Determinations
│   ├── Evidence references
│   └── Exports
└── Audit log
```

## Primary user workflow

The `/workspace` UI deliberately presents six concepts only: **Contract → Rules → Invoice → Evidence → Reconcile → Export**. Advanced details expose hashes, AIR IDs, compiler assurance, verification plans, derived facts, and audit events without making them prerequisites for routine use.

## Server-side isolation

`EVIDUE_WORKSPACE_TOKENS` maps a workspace identifier to an access key. The authenticated request stores that workspace in a request-local context. The database session factory resolves the context to an isolated SQLite database. The legacy `EVIDUE_PILOT_TOKEN` remains a single-workspace compatibility path.
