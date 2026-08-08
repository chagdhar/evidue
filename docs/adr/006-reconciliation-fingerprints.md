# ADR 006: Persist deterministic reconciliation fingerprints

**Status:** Accepted

Each run persists an input-manifest hash and calculation hash. The settlement layer adds a hash incorporating human review. Reruns with identical deterministic inputs must produce identical kernel hashes even when run IDs differ.
