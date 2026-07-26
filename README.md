# Evidue

Evidue independently reconciles outcome-priced AI-agent vendor invoices against
contractual billing rules and customer-owned operational evidence.

This repository contains a deterministic YC demonstration for fictional parties
Acme Commerce and Nova Support AI. It generates operationally realistic
synthetic data; no real customer or vendor data is included.

## Run locally

From a fish shell:

```fish
./scripts/bootstrap.sh
./scripts/seed-demo.sh
./scripts/dev.sh
```

Open <http://localhost:5173/demo>. The backend API is available at
<http://localhost:8000/api/health>.

The golden path starts with a submitted $15,000 invoice. Click **Run
reconciliation** to invoke the backend engine. It evaluates all 10,000 claims,
persists the determinations, and returns a $12,480 corrected payable amount with
a $2,520 recommended deduction.

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
[docs/DEMO_SCRIPT.md](docs/DEMO_SCRIPT.md) for the YC narration.
