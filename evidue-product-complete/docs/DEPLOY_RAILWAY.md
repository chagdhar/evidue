# Deploy the temporary Railway beta demo

This branch deploys the disposable synthetic Evidue demo to Railway. It uses no
Google Cloud account, Firestore, Cloud Run, persistent volume, or Gemini key.
Contact responses can be stored in a private Google Sheet through the optional
Apps Script integration.

## Git preparation

```bash
git switch railway-beta-demo
git status
git push -u origin railway-beta-demo
```

## Railway setup

1. Create or sign in to Railway.
2. Create a new project and choose **Deploy from GitHub repo**.
3. Select this Evidue repository and the `railway-beta-demo` branch.
4. Confirm Railway detects the root `Dockerfile`.
5. Add the required service variables:

```text
EVIDUE_PUBLIC_DEMO=true
EVIDUE_DB_PATH=/app/data/evidue.db
```

Configure the recommended beta application separately:

```text
EVIDUE_BETA_FORM_URL=https://tally.so/r/FORM_ID
```

The native product-feedback form is optional. Configure both values or neither:

```text
EVIDUE_CONTACT_SHEET_WEBHOOK_URL=https://script.google.com/macros/s/DEPLOYMENT_ID/exec
EVIDUE_CONTACT_SHEET_SECRET=GENERATED_64_CHARACTER_HEX_SECRET
```

`EVIDUE_BETA_FORM_URL` must be your actual HTTPS Tally URL; do not commit it.
Do not set `GEMINI_API_KEY`, Google Cloud credentials, Firestore variables, or
Cloud Run variables for this service.

Follow [`CONTACT_SHEET_SETUP.md`](CONTACT_SHEET_SETUP.md) to create the Sheet,
deploy the free Apps Script endpoint, and generate the shared secret. The two
contact-sheet variables are runtime secrets and must not be exposed as `VITE_`
variables.

The optional PostHog variables may be configured in Railway if desired. The
Docker build reads the two `VITE_` variables and the runtime CSP needs
`POSTHOG_HOST` too:

```text
VITE_POSTHOG_KEY=phc_...
VITE_POSTHOG_HOST=https://us.i.posthog.com
POSTHOG_HOST=https://us.i.posthog.com
```

The demo is fully functional without analytics.

## Service settings

- Root directory: repository root
- Builder: Dockerfile
- Health check: `/api/health`
- Restart policy: on failure, three retries
- Generate a public Railway domain after deployment

`railway.toml` contains the Dockerfile, health-check, and restart settings.
Railway injects `PORT`; the image defaults to `8080` locally.

## Verification

Set `SERVICE_URL` to the generated Railway HTTPS domain, without a trailing slash:

```bash
curl -fsS "$SERVICE_URL/api/health"
curl -fsS "$SERVICE_URL/api/demo/status"
curl -fsS "$SERVICE_URL/api/reconciliations/current"
curl -fsS "$SERVICE_URL/api/contracts/current"
curl -fsS "$SERVICE_URL/api/public-config"
curl -fsSI "$SERVICE_URL/contact"
curl -fsS -X POST "$SERVICE_URL/api/public-demo/rules/validate"
curl -fsS -X POST "$SERVICE_URL/api/public-demo/outcomes/OUT-004821/evaluate"
curl -fsS -X POST "$SERVICE_URL/api/public-demo/reconciliations/sample"
curl -fsS -o /dev/null -w '%{http_code}\n' "$SERVICE_URL/demo/invoices/current?outcome=OUT-004821"
```

Inspect the public configuration response and verify
`contact_form_configured` is `true` when the optional native feedback form is
intended to be live. Do not submit a real feedback row as part of every smoke
test; make any marked test submission an explicit manual check.

The reconciliation must report 10,000 submitted outcomes, 8,320 payable,
1,680 disputed, 0 needs review, $15,000 submitted, $12,480 payable, and a
$2,520 recommended deduction.

## Temporary deployment limitations

- SQLite is disposable; restart or redeploy recreates the public demo.
- Shared state remains read-only and public persistent mutations stay disabled.
- The deployment contains synthetic data only. Do not accept real customer
  invoices or contract uploads.
- Delete the Railway project after the trial or interview if it is no longer
  needed.

Google Cloud Run remains a longer-term container reference in
`docs/DEPLOY_CLOUD_RUN.md`; it is not used by this Railway branch.
