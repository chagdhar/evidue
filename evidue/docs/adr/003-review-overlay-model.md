# ADR 003: Human review is an append-only overlay

**Status:** Accepted

`needs_review` creates a review case. Finance decisions are stored separately and never update `PilotDeterminationRow.status`. This preserves the difference between machine truth and human authority and keeps the audit trail reconstructable.
