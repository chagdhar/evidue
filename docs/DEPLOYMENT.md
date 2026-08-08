# Product Deployment

## Required configuration

- `EVIDUE_WORKSPACE_TOKENS` (recommended) or `EVIDUE_PILOT_TOKEN`.
- persistent writable storage for `data/` or `EVIDUE_PILOT_DB_DIR`.
- one server-owned contract-compiler provider for arbitrary customer contracts.

Customers do not supply provider credentials.

### Gemini primary example

```bash
export EVIDUE_WORKSPACE_TOKENS='{"acme":"'"$(openssl rand -hex 32)"'"}'
export EVIDUE_LLM_PRIMARY=gemini
export GEMINI_API_KEY='...'
export GEMINI_MODEL='...'
./scripts/dev.sh
```

### OpenAI primary example

```bash
export EVIDUE_LLM_PRIMARY=openai
export OPENAI_API_KEY='...'
export OPENAI_MODEL='...'
```

An optional `EVIDUE_LLM_FALLBACK` may name a second server-configured provider. Transient provider failures are retried with bounded backoff before production fallback. Controlled qualification pins a provider/model and disables fallback.

For contracts that warrant independent model assurance, optionally configure:

```bash
export EVIDUE_LLM_ASSURANCE_PROVIDER=openai
export EVIDUE_LLM_ASSURANCE_MODEL='...'
```

This second compilation is a safety check, not a vote. Material semantic disagreement or an
unavailable explicitly-required assurance provider blocks approval and requires human review.

Open `/pilot` and enter the matching workspace access key. The product configuration surface returns only secret-free inference readiness metadata and never provider keys.

## Container

The Dockerfile builds the React frontend and installs the frozen Python runtime. It serves the built frontend and FastAPI application from one container. Persistent customer state must be mounted to `/app/data` or redirected with the database environment variables.

## Production notes

For a controlled beta, one database file per workspace provides a strong simple isolation boundary. For multi-instance production, replace SQLite with a managed database and explicit tenant-keyed rows or schemas; do not share a local SQLite volume across concurrent replicas.

Do not deploy arbitrary-contract compilation without server-side provider credentials. Never expose model keys to the browser. Reconciliation of an already-approved AIR does not require provider access.
