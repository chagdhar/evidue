# Evidue Product v1 Requirements

## Product outcome

Evidue is the independent financial control layer for outcome-priced AI vendor invoices. A finance operator must be able to move from governing agreement and vendor invoice to an approved payable amount and evidence-backed vendor dispute without allowing a language model to adjudicate money.

## Primary workflow

1. Establish an organization and vendor engagement.
2. Ingest the governing agreement bundle.
3. Compile the agreement into atomic requirements/AIR.
4. Pass compiler assurance and obtain human approval of the AIR version.
5. Ingest an invoice and customer-owned evidence.
6. Resolve identity ambiguity and evidence readiness.
7. Execute deterministic reconciliation.
8. Route `needs_review` determinations into an operational review queue.
9. Record append-only human review decisions without mutating machine determinations.
10. Produce a reconciliation statement.
11. Require all review exposure to be dispositioned before finance approval.
12. Record an immutable approved payable amount and calculation fingerprint.
13. Open and progress a stateful vendor dispute from the approved disputed amount.
14. Preserve audit history and reproducibility fingerprints.

## Non-negotiable invariants

- The LLM may propose contract structure; it never decides whether an invoice line is payable.
- An unapproved or stale AIR cannot be used as financial authority.
- Machine determinations are immutable after a run.
- Human review is an overlay, not an edit to machine output.
- Approval is impossible while unresolved review exposure remains.
- A vendor dispute is derived from an approved settlement, never directly from an unapproved run.
- Same deterministic inputs must yield the same kernel calculation hash.
- Every money decision must be traceable to agreement version, evidence/input manifest, kernel output, review overlay, and actor.

## Product surfaces

- Finance Operations overview
- Vendor engagements
- Invoice/billing-period history
- Review queue
- Settlement approval
- Vendor disputes
- Agreement/AIR workbench
- Evidence/identity workbench
- Audit and trust trail

## Current v1 implementation boundary

The qualified compiler/verification kernel remains in `app.agreements` and `app.upload`. The finance product layer is in `app.product` and references immutable kernel records. Workspace SQLite isolation remains supported for controlled pilots; PostgreSQL/Alembic is the next infrastructure migration, not a prerequisite for the domain model.
