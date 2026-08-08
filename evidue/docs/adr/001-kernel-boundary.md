# ADR 001: Preserve the qualified kernel boundary

**Status:** Accepted

The AIR/compiler/verification kernel remains independent from finance workflow entities. Product code consumes immutable determination records and may not alter the evaluator to accommodate UI workflow. This preserves qualification guarantees and makes product evolution less likely to corrupt financial semantics.
