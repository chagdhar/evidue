# Production shape

Production ingestion would import vendor APIs/exports and customer Salesforce,
Zendesk, payment, billing and product-system data through webhooks and scheduled
imports. Immutable provenance records retain source IDs and normalized values.
Incomplete or contradictory evidence enters needs-review; vendors can challenge
deductions and submit additional evidence, then determinations rerun
deterministically. The customer, not Evidue, retains final payment authority.
