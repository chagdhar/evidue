# Evidue

Evidue independently reconciles outcome-priced AI-agent vendor invoices against
contractual billing rules and customer-owned operational evidence.

This repository contains a deterministic product demonstration for fictional parties
Acme Commerce and Nova Support AI. It generates operationally realistic
synthetic data; no real customer or vendor data is included.

## Run locally

From a fish shell:

```fish
./scripts/setup-demo.sh
./scripts/dev.sh
```

The setup command rebuilds the disposable demo database, installs dependencies,
seeds the headline fixture, and runs the fast validation suite. See
[SETUP.md](SETUP.md) for manual and Docker instructions.

Open <http://localhost:5173/demo>. The backend API is available at
<http://localhost:8000/api/health>.

The golden path starts with a submitted $15,000 invoice. Click **Run
reconciliation** to invoke the backend engine. It evaluates all 10,000 claims,
persists the determinations, and returns a $12,480 corrected payable amount with
a $2,520 recommended deduction.

Before reconciliation, the demo now shows the production-shaped evidence path:
eight vendor and customer sources, aggregate source-record volumes, 9,975 direct
matches, 25 verified secondary-key matches, raw payload hashes, normalized
records, and source authority. Representative source exports are checked into
`demo-data/`; see [docs/REAL_DATA_INGESTION.md](docs/REAL_DATA_INGESTION.md).

## Validate

```fish
./scripts/dev-check.sh fast
./scripts/dev-check.sh full
```

`fast` runs backend lint/tests, frontend lint/tests, type checking, and the
production frontend build. `full` additionally runs the Playwright golden path
against live development servers.

## Production container

```fish
docker build -t evidue-demo .
docker run --rm -p 8000:8000 evidue-demo
```

Open <http://localhost:8000/demo>.

See [docs/HANDOFF.md](docs/HANDOFF.md) for fresh-checkout instructions and
[docs/DEMO_SCRIPT.md](docs/DEMO_SCRIPT.md) for the demo narration.

## Product surfaces

- `/demo` — finance control overview
- `/demo/invoices` — recurring invoice operations
- `/demo/invoices/current` — complete working June reconciliation
- `/demo/contracts/current` — contract clause-to-rule control center
- `/demo/disputes/current` — dispute package and financial handoff
- `/demo/data-sources` — production-shaped collection, matching, and raw-record provenance
- `/demo/vendor-preflight` — vendor-side invoice preflight
- `/demo/outcome-ledger` — shared outcome receipt model
- `/demo/lab` — technical edge-case scenarios

Only the June 2026 invoice is a fully interactive reconciliation. Historical invoice rows are explicitly labelled illustrative synthetic history; connector statuses are explicitly labelled local fixtures rather than live integrations.

## Product architecture

The demo presents Evidue as the financial control layer for outcome-priced AI agents:

- **Evidue Prove** (`/demo/vendor-preflight`) helps agent vendors preflight proposed invoice claims and find revenue at risk before billing.
- **Outcome Ledger** (`/demo/outcome-ledger`) shows the versioned proof envelope connecting agent execution, contract rules, and operational evidence.
- **Evidue** (`/demo/invoices/current`) independently calculates what the customer should pay.

The vendor workspace cannot modify customer-approved rules, customer-private evidence, or the customer's final payment decision.


## UI template

The interface uses a structural adaptation of Material UI's official open-source Dashboard template. See `docs/UI_TEMPLATE.md` for the source, adopted components, and Evidue-specific changes.

See `docs/FINAL_REPAIR_STATUS.md` for the final ingestion-demo repair and validation record.
