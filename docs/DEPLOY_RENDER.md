# Deploy Evidue to Render for $0

This repository is deployed as one Docker web service. FastAPI serves both the API and the compiled Vite frontend.

## Before deploying

1. Ensure `uv run ruff check backend` passes.
2. Ensure `npm --prefix frontend run build` passes.
3. Push the repository to a private or public GitHub repository.
4. Never commit `.env` or `GEMINI_API_KEY`.

## Deploy

1. Sign in to Render.
2. Select **New > Blueprint**.
3. Connect the GitHub repository containing this `render.yaml`.
4. Confirm the `evidue-demo` service uses the **Free** instance type.
5. Deploy.
6. When the deployment is live, open `/api/health`, then `/demo/contracts/current`.

## Optional live Gemini compilation

In Render, open the service and go to **Environment**. Add `GEMINI_API_KEY` as a secret, then redeploy. Do not use a key that has ever been pasted into chat, committed, or published.

Without a key, the demo still uses the validated recorded Gemini proposal for the bundled contract. Invoice adjudication remains deterministic in either mode.

## Free-tier behavior

The SQLite database is intentionally disposable. The app rebuilds and seeds it when a fresh instance starts. A free Render service can lose local files on restart or idle spin-down, so do not use this deployment for real customer data.

Before sending the application or joining an interview, visit the URL once and confirm these pages:

- `/api/health`
- `/demo/contracts/current`
- `/demo/invoices/current`
