# Connector Architecture Target

The current evaluation path deliberately accepts CSV/JSON/JSONL exports. Production connectors should normalize into the existing raw-record/event model rather than changing the verification kernel.

Each connector must implement conceptual operations: authenticate, test connection, discover schema, backfill, incremental sync, normalize, and health.

Each source must report coverage boundaries and completeness because absence-of-event proofs are unsafe without knowing whether the relevant window is fully observed.

Reference implementation order: generic file, generic REST, read-only Postgres, Zendesk, Stripe.
