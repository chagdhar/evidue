# Evidue setup

These steps assume Manjaro Linux, fish shell, Git, Docker, Node.js, npm, Python
3.13, and `uv` are available.

## Recommended installation

From the repository root:

```fish
./scripts/setup-demo.sh
./scripts/dev.sh
```

`setup-demo.sh` is retained as the existing bootstrap command for compatibility;
it seeds the deterministic synthetic fixture used by `/try` and local tests. It
does not create a separate product surface.

Optional live contract compilation uses Evidue-owned backend credentials:

```fish
cp .env.example .env
# Configure EVIDUE_LLM_PRIMARY plus the matching provider key/model only in .env.
# Customers never enter provider API keys in the product UI.
```

Open:

```text
http://localhost:5173/try
```

For the protected product, open:

```text
http://localhost:5173/workspace
```

The setup script deletes only disposable local fixture state, installs
dependencies, regenerates production-shaped synthetic source exports, and runs
the fast validation suite.

## Customer-facing surfaces

```text
/             Landing page
/try          Public no-signup proof
/contact      Talk to us / customer discovery
/workspace    Protected Evidue product
```

There is no separate public demo application. The useful inspection depth now
lives inline in `/try`: contract authority, representative claim audit,
evidence provenance, raw source records/hashes, proof receipt, reproducibility
metadata, and vendor-ready dispute summary.

## Manual setup

```fish
rm -f data/evidue.db data/*.sqlite data/*.sqlite3
./scripts/bootstrap.sh
./scripts/seed-demo.sh headline
./scripts/dev-check.sh fast
./scripts/dev.sh
```

`seed-demo.sh` is internal fixture tooling; it does not expose a `/demo` route.

## Full validation before deployment or recording

Stop development servers with `Ctrl+C`, then run:

```fish
./scripts/dev-check.sh full

docker build -t evidue .
docker run --rm -p 8000:8000 evidue
```

Open the production build at:

```text
http://localhost:8000/try
http://localhost:8000/workspace
```

## Optional live contract compilation

The public proof is repeatable without network access because a controlled
recorded proposal is included. For arbitrary contracts, configure a
server-owned provider before `./scripts/dev.sh`:

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

An optional `EVIDUE_LLM_FALLBACK` can be configured for production
availability. Qualification runs pin a provider and do not silently fail over.
Never commit a real key.

## Verification kernel

```fish
./scripts/evidue-proof.sh core
```

The command creates `artifacts/validation/latest.json` and `latest.md`. Run
`./scripts/evidue-proof.sh full` after a complete dependency bootstrap for the
broader repository/frontend gate.
