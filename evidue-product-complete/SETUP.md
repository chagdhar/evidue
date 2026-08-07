# Evidue demo setup

These steps assume Manjaro Linux, fish shell, Git, Docker, Node.js, npm, Python
3.13, and `uv` are available.

## Recommended installation

From the repository root:

```fish
./scripts/setup-demo.sh
./scripts/dev.sh
```

Optional live contract compilation:

```fish
cp .env.example .env
# Add GEMINI_API_KEY only in your local .env file.
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


## Optional live Gemini compilation

The demo is fully repeatable without network access because it includes a validated recorded rule proposal.
For the live contract-compilation path, set environment variables before `./scripts/dev.sh`:

```bash
export GEMINI_API_KEY="your-key"
export GEMINI_MODEL="gemini-2.5-flash-lite"  # optional override
```

Then use **Compile contract** in the contract compiler section. `auto` mode calls Gemini when a key exists and
falls back to the recorded proposal if the live call fails. Explicit `live` API mode returns an error instead of
falling back. Never commit a real key.
