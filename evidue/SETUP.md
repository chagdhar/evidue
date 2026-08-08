# Evidue demo setup

These steps assume Manjaro Linux, fish shell, Git, Docker, Node.js, npm, Python
3.13, and `uv` are available.

## Recommended installation

From the repository root:

```fish
./scripts/setup-demo.sh
./scripts/dev.sh
```

Optional live contract compilation uses Evidue-owned backend credentials:

```fish
cp .env.example .env
# Configure EVIDUE_LLM_PRIMARY plus the matching provider key/model only in .env.
# Customers never enter provider API keys in the product UI.
```

Open:

```text
http://localhost:5173/demo
```

The setup script deletes only the disposable local demo database at
`data/evidue.db`, installs dependencies, seeds the headline fixture, and runs the
fast validation suite. Rebuilding the database prevents stale schemas from an
older archive from causing errors such as `no such table: contract_clauses`.

## Manual setup

```fish
rm -f data/evidue.db data/*.sqlite data/*.sqlite3
./scripts/bootstrap.sh
./scripts/seed-demo.sh headline
./scripts/dev-check.sh fast
./scripts/dev.sh
```

## Full validation before recording

Stop the development servers with `Ctrl+C`, then run:

```fish
./scripts/dev-check.sh full

docker build -t evidue-demo .
docker run --rm -p 8000:8000 evidue-demo
```

Open the production build at:

```text
http://localhost:8000/demo
```

## Demo routes

- `/demo` — product overview
- `/demo/vendor-preflight` — Evidue Prove vendor preflight
- `/demo/outcome-ledger` — outcome receipt and neutrality model
- `/demo/invoices/current` — Evidue Verify working reconciliation
- `/demo/contracts/current` — clause-to-rule mappings
- `/demo/disputes/current` — dispute package
- `/demo/data-sources` — production-shaped collection, matching, and raw-record provenance
- `/demo/lab` — technical edge cases

## Reset the demo

```fish
./scripts/demo-reset.sh headline
```

A reset returns the June invoice to the unreconciled state.


## Optional live contract compilation

The demo/core proof is repeatable without network access because controlled recorded proposals are included. For arbitrary contracts, configure a server-owned provider before `./scripts/dev.sh`:

```fish
set -x EVIDUE_LLM_PRIMARY gemini
set -x GEMINI_API_KEY 'your-server-key'
set -x GEMINI_MODEL 'your-enabled-model'
```

Or use OpenAI:

```fish
set -x EVIDUE_LLM_PRIMARY openai
set -x OPENAI_API_KEY 'your-server-key'
set -x OPENAI_MODEL 'your-enabled-model'
```

An optional `EVIDUE_LLM_FALLBACK` can be configured for production availability. Qualification runs pin a provider and do not silently fail over. Never commit a real key.

## Verification kernel

```fish
./scripts/evidue-proof.sh core
```

The command creates `artifacts/validation/latest.json` and `latest.md`. Run `./scripts/evidue-proof.sh full` after a complete dependency bootstrap for the broader repository/frontend gate.
