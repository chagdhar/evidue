# Migration Plan from Qualified Pilot

1. Freeze/tag the qualified compiler and qualification benchmark.
2. Add product tables without changing AIR/runtime semantics.
3. Auto-link existing contracts and invoices into vendor engagements.
4. Add reconciliation fingerprints to new runs.
5. Materialize review cases/statements for historical runs through idempotent bootstrap.
6. Move operators from the linear PilotApp flow into Finance Operations after reconciliation.
7. Validate review/approval/dispute E2E flows.
8. Introduce PostgreSQL/Alembic after the domain model is stable.

No historical machine determination is rewritten during migration.
