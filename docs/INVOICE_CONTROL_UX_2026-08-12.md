# Evidue invoice-control UX

## Product object

The primary finance object is the vendor invoice. The authenticated workspace is organized around the work finance must complete on that invoice rather than around internal compiler/runtime concepts.

## Information architecture

- `/workspace` — finance-control overview: spend under review, unsupported exposure, attention count, and recent invoice queue.
- `/workspace/invoices` — searchable, filterable, paginated invoice register.
- `/workspace/invoices/current` — active invoice case: Contract → Invoice → Evidence → Verification → Review → Commercial action.
- `/workspace/invoices/:invoiceId` — persistent historical invoice record with summary, review, commercial action, and audit disclosure.
- `/workspace/review` — unresolved manual decisions, approval work, vendor action, and ready-to-settle queues.
- `/workspace/vendors` — vendor-level spend, exception, contract, and open-review history.
- `/workspace/settings` — finance defaults and evidence-system preferences.

Legacy `/pilot/*` and `/workspace/operations` routes remain redirects only.

## Decision hierarchy

Every invoice case must answer, in this order:

1. What did the vendor bill?
2. What contract interpretation was approved?
3. Is the required customer-controlled evidence ready?
4. What did deterministic verification establish?
5. Which dollars are substantiated, contradicted, or insufficiently evidenced?
6. What commercial action does the contract permit?

Factual determination and commercial action are separate concepts. A contradicted claim does not automatically imply a particular remedy.

## Trust boundary

- AI proposes contract rules.
- A human explicitly reviews and approves the interpretation.
- Approved rules and customer evidence are inputs to deterministic financial verification.
- Technical provenance is available through progressive disclosure but does not compete with the finance decision.

## Visual system

The workspace uses restrained AP/vendor-control conventions: solid surfaces, 8px geometry, minimal shadows, table-first density, a single blue accent, and semantic color only for financial state. Decorative gradients, glow effects, oversized cards, and internal AI/compiler terminology are excluded from primary finance surfaces.

## Behavioral principles

Ethical activation cues are limited to useful operational signals: completion progress, unresolved-dollar visibility, evidence consequences, explicit approval boundaries, and a recommended next action. No fake urgency, scarcity, social proof, or gamified completion is used.

## Public validation

`/try` mirrors the same contract → approval → deterministic verification → result boundary with synthetic data. `/contact` begins with a single intent choice and reveals only relevant questions. Product feedback can be anonymous; billing conversations collect the four qualification signals needed to test Evidue's ICP.
