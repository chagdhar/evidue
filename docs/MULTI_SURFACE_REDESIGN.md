# Multi-Surface Product Redesign

The demonstration is now presented as a financial-control product rather than a single reconciliation report.

## Routes

- `/demo` — finance control overview and recurring invoice context
- `/demo/invoices` — invoice operations list
- `/demo/invoices/current` — full working June 2026 reconciliation
- `/demo/contracts/current` — approved contract clause-to-rule mappings
- `/demo/disputes/current` — dispute package and customer handoff
- `/demo/data-sources` — synthetic fixture provenance and ingestion model
- `/demo/lab` — edge-case engineering scenarios

## Truthfulness boundaries

- Only the June 2026 invoice is a fully interactive, persisted reconciliation.
- May and April rows are explicitly labelled illustrative synthetic history.
- Data-source cards say `Fixture loaded`, not `Connected`.
- No UI claims that Evidue sends, negotiates, or settles disputes.
- Finance or procurement retains final payment authority.
- Headline invoice values continue to come from the API.

## Recording path

Overview → June invoice → Run reconciliation → Review example dispute → Download dispute package.
