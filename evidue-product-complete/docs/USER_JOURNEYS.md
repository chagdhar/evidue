# User Journeys

## First-time evaluator

1. Open `/pilot` and enter a workspace access key.
2. Choose **Try sample workspace**.
3. See one payable, one disputed, and one needs-review line.
4. Open the line decisions to inspect contract clauses and evidence timelines.
5. Download the corrected invoice or review report.

Success criterion: the user can understand Evidue's value without knowing AIR, JSON schemas, or internal rule IDs.

## Finance/AP operator with real files

1. Upload or paste an agreement and enter the commercial period/parties.
2. Analyze the contract, read the source-to-rule mapping, and approve the proposed AIR only after review.
3. Choose an invoice CSV. Evidue previews headers and proposes field mappings; the operator corrects any missing mappings before import.
4. Import customer-side evidence. The operator explicitly states whether an export fully covers the relevant period.
5. Review unresolved identity links; only authoritative or manually confirmed links can influence reconciliation.
6. Run deterministic reconciliation.
7. For disputes or needs-review items, inspect why, contract source, and evidence timeline.
8. Add better evidence and rerun if necessary; the prior run remains intact.
9. Export finance-ready artifacts.

## Contract reviewer

1. Open the Rules step.
2. Review every material source clause and its executable norm/proof/settlement representation.
3. Inspect compiler assurance and conformance in Advanced details when needed.
4. Approve the immutable version. A later approval supersedes but never mutates the old version.

## Evidence operator

1. Upload operational evidence from a named source system.
2. Mark completeness only when the export truly covers the contractual observation period.
3. Run matching and resolve non-authoritative suggestions.
4. Review the generated verification plan. Missing capabilities remain visible and cause `needs_review` rather than an automatic dispute.
