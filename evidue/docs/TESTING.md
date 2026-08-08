# Testing

## Fast validation

```bash
./scripts/dev-check.sh fast
```

This is the release gate for formatting/lint, backend tests, frontend lint/tests/type checking, and production build.

## Full validation

```bash
./scripts/dev-check.sh full
```

Adds Playwright browser tests against live backend/frontend servers.

## Product smoke

```bash
./scripts/product-smoke.sh
```

Runs the protected product path in a temporary database and asserts that the sample workspace produces one payable, one disputed, and one needs-review determination plus finance exports.

## Architectural invariants covered by tests

- native AIR source binding and conformance,
- compiler assurance blocks ungrounded or malformed versions,
- approved AIR immutability and supersession,
- no LLM call during reconciliation,
- generic AIR adjudication rather than legacy rule-ID authority,
- append-only reconciliation runs,
- raw/normalized evidence provenance,
- identity-match authority rules,
- arbitrary invoice-column mapping,
- pasted and DOCX contract ingestion,
- sample onboarding,
- workspace database isolation,
- corrected invoice and review-report exports.

A frontend build cannot be considered validated if dependency installation failed. CI/fresh-checkout environments must run `npm ci` successfully before reporting the product release gate green.
