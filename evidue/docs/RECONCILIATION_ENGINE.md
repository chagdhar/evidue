# Reconciliation Engine

## Authority boundary

`backend/app/agreements/adjudication.py` is the product financial-authority path. It consumes only:

```text
approved AIR + normalized invoice claim + accepted evidence
```

It does not call an LLM and it does not branch on demo/legacy rule IDs. The legacy deterministic engine is retained only for optional migration comparison when `EVIDUE_AGREEMENT_RUNTIME_DUAL_RUN=true`.

## Per-claim evaluation

1. Attribute accepted evidence to the claim.
2. If attribution is conflicting or still requires human confirmation, return `needs_review`.
3. Evaluate applicable AIR norms using the constrained expression runtime.
4. An indeterminate norm follows its explicit AIR indeterminate consequence, normally `needs_review`.
5. A violated norm applies its approved consequence.
6. If norms pass, calculate the payable amount from the approved settlement policy.
7. Apply batch-level `unique_by` norms generically from their parameters.
8. Persist the determination, exact AIR version, engine/runtime versions, amount breakdown, and decisive evidence references.

## Amount invariant

For each line:

```text
billed = payable + disputed + needs_review
```

`needs_review` is held out of both confirmed payable and recommended deduction until evidence is sufficient.

## Versioning

Each run is append-only and records `supersedes_run_id`. Historical results remain tied to the AIR version and verification plan used at that time.
