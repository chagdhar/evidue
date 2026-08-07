# Evidue production-shaped demo inputs

These are compact, inspectable examples of the source records represented by the deterministic 10,000-claim batch. They are synthetic, but deliberately retain the field shapes and trust boundaries expected in production.

## Files

- `vendor/june-claim-manifest.csv` — line-level claims supporting the submitted invoice.
- `vendor/agent-execution-log.jsonl` — vendor execution receipts and attempted actions.
- `customer/support-events.jsonl` — customer-owned conversation and human-intervention records.
- `customer/payment-events.jsonl` — customer-owned payment processor outcomes.
- `customer/product-events.jsonl` — customer-owned downstream state changes.
- `customer/billing-ledger.csv` — prior attribution and duplicate evidence.
- `customer/customer-account-map.csv` — approved cross-system identity mappings.
- `contract/order-form-extract.json` — signed-term metadata and approved rule IDs.
- `manifest.json` — aggregate batch and evidence-readiness metrics.

The application reset pipeline generates the complete synthetic batch from these source shapes, preserves hashes and provenance for every normalized event, and stores representative raw payloads for inspection.

## Production collection

1. **Initial deployment:** customer-provided CSV/JSONL exports and contract uploads.
2. **Recurring operation:** read-only warehouse views, APIs, SFTP, and object storage.
3. **Incremental evidence:** webhooks, scheduled polling, or change-data capture where needed.

Vendor-controlled claims and execution evidence remain separate from customer-owned support, payment, product, billing, identity, and contract data. Vendor records support a claim but never determine payability.
