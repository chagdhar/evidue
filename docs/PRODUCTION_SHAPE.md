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

## Attribution boundary

Production adapters would not be trusted merely because they populated an event
type. The domain attribution boundary would continue to require customer and
outcome identity, plus account and action identity where the rule is sensitive
to them. Unrelated events remain inert; missing identifiers, duplicate source
records, and contradictory directly matched events remain explicit review
conditions. This prevents evidence from one customer, outcome, account, or
action from affecting another claim.

## Incomplete and contradictory evidence

An absence of reliable evidence is not proof that a vendor outcome failed.
Incomplete, unavailable, late, or contradictory inputs would produce
`needs_review`. Its billed amount would remain in a separate needs-review bucket,
not in the recommended deduction. Operations users could inspect the missing
requirements, request additional evidence, and rerun only the affected
determinations.

## Contextual duplicates and contractual deadlines

Duplicate detection would remain invoice-contextual: same customer, normalized
intent, and a 24-hour window. The deterministic winner is the earliest closed
claim, with outcome ID as a stable tie-breaker. Imported duplicate labels may
corroborate but never replace this comparison.

Contractual deadlines are derived from the applicable rule and stored claim
time. They may be shown as computed audit markers, but are not asserted to be
customer-owned source events.

## Challenges and reruns

A vendor could challenge a proposed deduction and submit additional source
evidence. Evidue would append that evidence, record who submitted it, and rerun
the same versioned deterministic rule. Both the former and superseding
determination would remain auditable.

## Payment authority

Evidue recommends a corrected payable amount. The customer retains authority
over its final payment decision, exception policy, and approval workflow. No
language model or vendor assertion can directly mark money payable.
