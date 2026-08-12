# Real-data ingestion model

## Product principle

Real customer data does not arrive as one clean table keyed by an Evidue outcome ID. A vendor invoice, support audit log, payment event, product-state record, billing history, and contract may all use different identifiers and arrive at different times.

Evidue therefore separates the workflow into five auditable stages:

1. **Collect** vendor claims, customer-owned operational records, identity mappings, and contract documents through read-only channels.
2. **Preserve raw** source payloads with immutable source IDs, receipt times, schema versions, and content hashes.
3. **Normalize** source-specific fields into canonical claims, conversations, operational events, identities, and approved contract rules.
4. **Match evidence** using direct outcome IDs when available and verified secondary keys when systems use different identifiers.
5. **Evaluate** deterministic contract rules only after evidence attribution is complete.

The synthetic demo follows this path. It does not seed only finished payable decisions.

## Demonstration batch

The headline fixture generates:

- 10,000 vendor claims;
- eight distinct collection sources;
- 50,302 source-shaped records represented by exact connector metrics;
- 20,301 normalized operational events;
- 9,975 direct outcome-ID matches;
- 25 verified secondary-key matches;
- zero unresolved identity reviews in the clean recording fixture;
- seven customer-approved contract rules;
- representative raw payloads retained for inspection in the UI and repository.

The complete aggregate batch is deterministic. To keep a fresh checkout compact and fast, the demo stores representative original payloads while retaining exact counts, schema versions, hashes, and provenance for the full normalized event set. Production would retain every permitted raw record under the customer's access and retention policy.

## What the source data looks like

### Vendor claim manifest

The vendor declares what it wants to bill:

```csv
vendor_claim_id,conversation_id,outcome_type,claimed_completed_at,billed_amount
CLM-04821,CONV-04821,refund_completed,2026-06-18T14:21:00Z,1.50
```

This is a claim, not proof of payability.

### Customer payment event

The customer-owned payment system records operational truth:

```json
{
  "refund_attempt_id": "RFND-04821-A",
  "customer_account_id": "ACCT-04821",
  "amount": "49.00",
  "result": "rejected",
  "occurred_at": "2026-06-18T14:39:00Z"
}
```

### Identity mapping

When one system lacks the outcome ID, Evidue uses approved identifiers rather than guessing:

```csv
conversation_id,support_customer_id,customer_account_id
CONV-09976,CUST-09976,ACCT-09976
```

The resulting evidence match records the method, confidence, reason, and source records used.

## Canonical internal record

After normalization and attribution, a source event becomes a stable Evidue evidence record:

```json
{
  "source_system": "payment_processor",
  "source_record_id": "RFND-04821-A",
  "event_type": "downstream_failed",
  "occurred_at": "2026-06-18T14:39:00Z",
  "matched_outcome_id": "OUT-004821",
  "match_method": "direct_outcome_id",
  "match_confidence": 1.0,
  "schema_version": "payment-event.v1",
  "payload_hash": "sha256:..."
}
```

The raw record remains available for reproduction and dispute evidence. Normalization never overwrites the original.

## Production collection methods

### Phase 1 — exports

The fastest first-customer deployment uses customer-approved files:

- vendor claim-manifest CSV;
- vendor execution JSONL;
- support event export;
- payment event export;
- product-operation export;
- billing or attribution ledger;
- restricted customer/account identity map;
- contract and order-form documents.

This proves financial value before a lengthy integration project.

### Phase 2 — read-only connections

Recurring files can then be replaced with:

- vendor invoice or claim API;
- support-platform OAuth API;
- payment-processor read API and webhooks;
- approved Snowflake, BigQuery, or Redshift views;
- SFTP or object-storage drops;
- read-only finance and product-data views.

For larger customers, warehouse views are often preferable to broad access across many production applications. The customer exposes only approved columns.

### Phase 3 — incremental sync

For recurring invoice cycles and late-arriving evidence, Evidue can use:

- scheduled connector polling;
- webhooks;
- event streams;
- change-data capture;
- incremental object-store files.

Reconciliation can remain batch-oriented even when collection is incremental.

## Matching hierarchy

Evidue should use deterministic matching in descending order of authority:

1. vendor claim ID or shared outcome ID;
2. conversation ID plus customer/account mapping;
3. transaction or action ID plus account and amount;
4. approved composite key plus a bounded time window;
5. unresolved identity review.

A secondary match must expose the keys used and why the match is accepted. Low-confidence or contradictory matches go to `needs_review`; they do not become confirmed deductions.

## Trust boundary

- Vendor systems declare the proposed bill and may provide supporting execution evidence.
- Customer-owned systems establish support, payment, product, and billing truth.
- Customer-approved contract rules define billability.
- Evidue applies deterministic rules and records evidence provenance.
- Finance retains the final payment decision.

Vendor evidence cannot overwrite customer evidence, edit customer rules, inspect private customer records, or declare a charge payable.

## Public proof and product surfaces

`/try` demonstrates the ingestion trust boundary at the claim level. After reconciliation, a visitor can inspect the decisive customer-controlled evidence, connector/source identity, match status and confidence, raw-record hash, schema version, and the representative raw payload inline.

`/workspace` exposes production/pilot evidence readiness at invoice scale and retains the full source/evidence lifecycle for authorized operators. The old standalone public data-source browser has been removed to avoid creating a third product surface.

## Repository fixtures

Representative source exports are stored under `demo-data/`. Regenerate them with:

```bash
python scripts/generate-source-fixtures.py
```

The generated files are synthetic and deterministic. They are designed to demonstrate real source-system shapes and trust boundaries, not to claim compatibility with a specific customer's undocumented schema.
