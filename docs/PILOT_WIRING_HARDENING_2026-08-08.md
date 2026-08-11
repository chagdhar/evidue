# Pilot Wiring Hardening — 2026-08-08

## Scope

This pass fixes operator-facing controls that could appear complete, disabled, or clickable without a valid workflow transition. It does not change the Atomic Requirement Ledger, AIR compiler, deterministic verification kernel, or financial calculation semantics.

## Fixed state-machine defects

1. **Export stage reachability** — a completed reconciliation with no `needs_review` determinations now advances the recommended workflow stage to `export`, and the workflow rail records the export stage as available/completed once a reconciliation exists.
2. **Manual navigation freeze** — clicking a workflow stage still lets the operator inspect it, but a later backend state transition resets that override and resumes automatic guidance.
3. **False evidence readiness** — a missing verification plan is now explicitly *not ready*. An empty persisted plan remains valid when the approved AIR genuinely has zero external proof requirements.
4. **Verification-plan lifecycle** — successful invoice import now creates the automatic verification plan immediately. If the plan is absent because of a partial/network failure, the Evidence screen exposes **Build verification plan** as a recovery action.

## Fixed dead/opaque controls

- Invoice import explains whether it is waiting for column mapping, control-total calculation, or operator confirmation.
- Reconciliation explains when unmatched evidence is blocking execution.
- Identity review raises visible errors for missing invoice state, missing event IDs, and zero candidate matches.
- **Confirm match** cannot submit without a selected invoice line and audit rationale.
- Finance dispute PDF downloads report failures through the normal workspace error banner.
- Public read-only demo reconciliation is actually disabled and explains why.

## Regression tests

`frontend/src/PilotApp.test.tsx` now covers:

- missing verification plan does not imply evidence readiness;
- all required proof-plan items must be ready;
- a review-free reconciliation recommends export;
- `needs_review` keeps the operator in Decision;
- manual stage navigation remains stable until backend progress changes the recommendation, at which point guidance resumes.

## Local release gate

Run from the repository root:

```bash
./scripts/check-all.sh
```

or the existing full development gate:

```bash
./scripts/dev-check.sh full
```

The handoff sandbox could not obtain all dependencies from its internal npm/Python mirrors, so it did not claim a full-suite pass. Modified TSX files were syntax-parsed successfully with TypeScript and the Python tree passed `compileall` before caches were removed.
