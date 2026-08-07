# Next Build — Product Expansion

The verified contract runtime described by the original design overlay is now implemented in the product branch. This file records the next **post-product-core** work rather than unfinished runtime architecture.

## Completed in this branch

- first-class atomic predicates and immutable AIR versions;
- deterministic compiler assurance gates;
- source-bound contract provenance;
- automatic evidence capability planning;
- four-valued fact derivation and review boundary;
- generic AIR adjudication with deterministic settlement;
- clause/evidence-to-dollar provenance;
- workspace-scoped storage and audit history;
- product onboarding, invoice mapping, evidence import, review, and finance exports.

## Next strategic milestones

These are scale/integration improvements, not prerequisites for using the current beta product:

1. **Live read-only connectors** — Zendesk, Intercom, Salesforce, Stripe, and customer data warehouses, mapped into the existing normalized evidence model.
2. **Managed identity and tenancy** — replace access-key workspaces with organization membership, SSO/OIDC, roles, invitations, and a managed database.
3. **Async large-file execution** — background jobs, progress reporting, cancellation, and resumable imports for production-volume reconciliations.
4. **Approval workflows** — configurable finance/legal approvers, comments, and separation-of-duties policies around AIR activation and reconciliation sign-off.
5. **Operational observability** — metrics, tracing, alerting, retention controls, and managed backups.

## Product-core invariant

None of these milestones may move financial authority into an LLM. Contract interpretation remains proposal-only; approved AIR plus customer evidence remain the deterministic source of financial decisions.
