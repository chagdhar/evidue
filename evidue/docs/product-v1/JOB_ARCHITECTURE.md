# Job Architecture Target

Long-running ingestion, compiler, evidence sync, reconciliation and export operations should move behind persisted jobs before large production datasets.

Initial implementation should use PostgreSQL-backed jobs with states `queued`, `running`, `completed`, `failed`, `cancelled`; attempts and error summaries must be persisted. No Kafka or distributed queue is required for v1.

Synchronous execution remains acceptable for the controlled pilot while the domain API is stabilized.
