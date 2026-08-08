# ADR 008: Use persisted jobs before distributed infrastructure

**Status:** Planned

Ingestion, sync, compile, reconciliation and export operations will use a Postgres-backed job table/worker model first. Kafka/Celery-class infrastructure is not justified until throughput demands it.
