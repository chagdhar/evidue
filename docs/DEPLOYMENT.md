# Product Deployment

## Required configuration

- `EVIDUE_WORKSPACE_TOKENS` (recommended) or `EVIDUE_PILOT_TOKEN`.
- `GEMINI_API_KEY` for compiling arbitrary customer contracts.
- `GEMINI_MODEL` optional model override.
- persistent writable storage for `data/` or `EVIDUE_PILOT_DB_DIR`.

Example:

```bash
export EVIDUE_WORKSPACE_TOKENS='{"acme":"'"$(openssl rand -hex 32)"'"}'
export GEMINI_API_KEY='...'
./scripts/dev.sh
```

Open `/pilot` and enter the matching workspace key.

## Container

The Dockerfile builds the React frontend and installs the frozen Python runtime. It serves the built frontend and FastAPI application from one container. Persistent customer state must be mounted to `/app/data` or redirected with the database environment variables.

## Production notes

For a controlled beta, one database file per workspace provides a strong simple isolation boundary. For multi-instance production, replace SQLite with a managed database and explicit tenant-keyed rows or schemas; do not share a local SQLite volume across concurrent replicas.

Do not deploy arbitrary-contract compilation without a server-side model key. Do not expose model keys to the browser.
