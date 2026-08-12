# Evidue Decision Ledger Design V2

## Governing principle

The invoice is the object. The financial decision is the outcome. Every other interface element exists to justify that decision.

Evidue uses one repeated semantic grammar across marketing, the public demo, and the customer workspace:

1. **Claim** — what the vendor says happened.
2. **Authority** — what the human-approved contract requires.
3. **Proof** — what customer-controlled systems show.
4. **Determination** — substantiated, contradicted, or insufficient evidence.
5. **Financial impact** — the dollar consequence of that factual state.
6. **Commercial action** — what finance may do next under its own authority.

## Visual language

- Deep ink/navy for control framing and case identity.
- Warm paper for working surfaces and source evidence.
- Teal for human-approved authority and substantiated states.
- Rust/red only for contradicted financial exposure.
- Amber only for insufficient evidence / review states.
- Thin ledger rules, tabular numerals, compact uppercase provenance labels.
- Almost no shadows and no gradients, glow, glass, or abstract AI imagery.
- Containers are semantic: source documents, authority blocks, decision ledgers, and actions do not share one generic card treatment.

## Experience rules

- Lead with `Vendor billed → Substantiated → Unsupported → Review` before mechanism details.
- The landing page demonstrates a full claim ledger, not a feature grid.
- `/try` separates **Approve rules** from **Verify claims** so authority is learned before calculation.
- The protected product keeps invoice identity and financial exposure persistent while the user moves through Contract, Invoice, Evidence, Verification, Review, and Action.
- Review explicitly separates `WHAT HAPPENED` from `WHAT FINANCE CAN DO`.
- Technical hashes, compiler detail, and audit metadata remain progressive disclosure.
- Missing evidence never silently becomes payable or disputed.

## Implementation constraints

This release is a frontend composition/refactor. It does not alter the contract compiler, evidence normalizer, deterministic adjudication kernel, settlement policy, or backend financial authority model.
