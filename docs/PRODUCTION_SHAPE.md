# Production shape

The demo deliberately implements no live integrations. A production Evidue
deployment would retain the same deterministic domain engine while replacing
fixture generation with ingestion adapters.

## Ingestion

Vendor claims would arrive from vendor APIs and signed exports. Customer-owned
evidence would arrive from Salesforce, Zendesk, payment processors, billing
systems, and product databases. Sources could use authenticated webhooks for
near-real-time events or scheduled, checkpointed imports for systems that expose
only batch APIs.

Adapters would store immutable source records before normalization. Each
normalized event would preserve source system, source record ID, source
timestamp, ingestion timestamp, customer/outcome association, and the values
used by a rule. Corrections would create new versions rather than overwriting
the evidence used by a prior determination.

## Incomplete and contradictory evidence

An absence of reliable evidence is not proof that a vendor outcome failed.
Incomplete, unavailable, late, or contradictory inputs would produce
`needs_review`. Operations users could inspect the missing requirements, request
additional evidence, and rerun only the affected determinations.

## Challenges and reruns

A vendor could challenge a proposed deduction and submit additional source
evidence. Evidue would append that evidence, record who submitted it, and rerun
the same versioned deterministic rule. Both the former and superseding
determination would remain auditable.

## Payment authority

Evidue recommends a corrected payable amount. The customer retains authority
over its final payment decision, exception policy, and approval workflow. No
language model or vendor assertion can directly mark money payable.
