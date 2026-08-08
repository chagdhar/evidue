# ADR 007: PostgreSQL is the production system-of-record target

**Status:** Accepted, migration pending

Workspace-isolated SQLite remains useful for controlled pilots and tests. Production multitenancy will move to PostgreSQL with Alembic after the product-domain model is stable, avoiding a simultaneous workflow and infrastructure rewrite.
