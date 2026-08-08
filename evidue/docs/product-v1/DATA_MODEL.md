# Data Model and Migration Direction

## Current persistence

Controlled pilots retain workspace-isolated SQLite databases. Product v1 adds `product_*` tables on the same SQLAlchemy metadata and keeps explicit links to `pilot_*` kernel objects.

## Reconciliation fingerprints

`pilot_reconciliation_runs` now stores:

- `input_manifest_hash`: canonical hash of approved AIR, agreement source bundle, verification plan, raw record hashes, identity mappings, manual matches, reviewed facts, and evaluator versions.
- `calculation_hash`: canonical hash of the input manifest plus sorted deterministic determinations and dollar outputs.

`product_reconciliation_statements.calculation_hash` additionally binds the kernel calculation hash to append-only finance review decisions and final recommended amounts.

## PostgreSQL migration target

The schema is intentionally portable SQLAlchemy. Before multi-user production rollout:

1. Introduce PostgreSQL as the system of record.
2. Add Alembic and a baseline migration covering pilot and product tables.
3. Add `organization_id` as an explicit tenancy key to customer-owned tables.
4. Backfill organization/vendor engagement links.
5. Enforce unique and foreign-key constraints under PostgreSQL.
6. Keep SQLite only for disposable demo/test fixtures.
