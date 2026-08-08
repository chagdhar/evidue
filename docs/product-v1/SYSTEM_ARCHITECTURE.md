# System Architecture

## Boundary

```text
Agreement documents
  -> compiler proposal
  -> atomic requirement ledger / AIR
  -> compiler assurance + human approval
  -> verification plan
  -> evidence + identity resolution
  -> deterministic facts / verification kernel
  -> immutable determinations
  -> finance product layer
      -> review overlay
      -> settlement statement
      -> finance approval
      -> vendor dispute
```

## Modules

- `app.agreements`: contract semantics, AIR, assurance, qualification and runtime.
- `app.upload`: authenticated real-data ingestion, matching, facts and reconciliation persistence.
- `app.product`: recurring commercial hierarchy and finance operations.
- `frontend/src/PilotApp.tsx`: ingestion/verification workbench.
- `frontend/src/FinanceWorkspace.tsx`: finance operations workbench.

## Dependency rule

The product layer may depend on qualified kernel records. The kernel must not depend on finance UI concepts. The only current bridge from the kernel into the product layer is a post-persist hook that creates/link product records and statements; it does not participate in determination logic.
