# Deploy Evidue's public technical preview to Cloud Run

Evidue is one Docker service: FastAPI serves the API and compiled Vite frontend.
The existing Dockerfile is Cloud Run compatible: it binds to Cloud Run's `$PORT`
and exposes `/api/health`. The public service is intentionally disposable:
`EVIDUE_PUBLIC_DEMO=true` reseeds its deterministic SQLite fixture at startup.

The public deployment does **not** receive `GEMINI_API_KEY`. It replays the
checked-in, schema-validated proposal and exposes only safe deterministic
validation and evaluation actions. Live Gemini compilation remains a private or
local workflow; do not put that credential in the public Cloud Run service.

## First manual deployment (fish)

```fish
set PROJECT_ID your-gcp-project-id
set BILLING_ACCOUNT 000000-000000-000000
set REGION us-central1
set SERVICE evidue-demo
set REPOSITORY evidue

gcloud auth login
gcloud projects create $PROJECT_ID --name="Evidue Demo"
gcloud billing projects link $PROJECT_ID --billing-account=$BILLING_ACCOUNT
gcloud config set project $PROJECT_ID
gcloud services enable run.googleapis.com artifactregistry.googleapis.com iamcredentials.googleapis.com firestore.googleapis.com
gcloud artifacts repositories create $REPOSITORY --repository-format=docker --location=$REGION --description="Evidue Cloud Run images"

gcloud iam service-accounts create evidue-runtime --display-name="Evidue Cloud Run runtime"
set RUNTIME_SERVICE_ACCOUNT evidue-runtime@$PROJECT_ID.iam.gserviceaccount.com
gcloud firestore databases create --database='(default)' --location=$REGION --type=firestore-native --delete-protection
gcloud projects add-iam-policy-binding $PROJECT_ID --member="serviceAccount:$RUNTIME_SERVICE_ACCOUNT" --role="roles/datastore.user"
set IMAGE $REGION-docker.pkg.dev/$PROJECT_ID/$REPOSITORY/$SERVICE:manual
gcloud auth configure-docker $REGION-docker.pkg.dev
docker build --tag $IMAGE .
docker push $IMAGE

gcloud run deploy $SERVICE \
  --image $IMAGE \
  --region $REGION \
  --allow-unauthenticated \
  --min-instances 1 \
  --max-instances 3 \
  --cpu 1 \
  --memory 1Gi \
  --concurrency 40 \
  --timeout 60 \
  --cpu-boost \
  --port 8080 \
  --service-account $RUNTIME_SERVICE_ACCOUNT \
  --set-env-vars EVIDUE_PUBLIC_DEMO=true,EVIDUE_DB_PATH=/app/data/evidue.db,EVIDUE_FIRESTORE_PROJECT_ID=$PROJECT_ID \
  --startup-probe httpGet.path=/api/health,httpGet.port=8080,initialDelaySeconds=0,timeoutSeconds=5,periodSeconds=10,failureThreshold=10
```

Keep `--min-instances 1` for a launch/demo window. Afterward, return to
scale-to-zero with `gcloud run services update $SERVICE --region $REGION
--min-instances 0`.

Verify the deployed service:

```fish
set SERVICE_URL (gcloud run services describe $SERVICE --region $REGION --format='value(status.url)')
curl --fail $SERVICE_URL/api/health
curl --fail $SERVICE_URL/api/reconciliations/current
echo $SERVICE_URL/demo
```

## Beta waitlist and feedback

The public forms write to two private Firestore collections using the Cloud Run
runtime service identity:

- `beta_waitlist`: one deduplicated document per normalized email address.
- `preview_feedback`: feedback text and an optional reply email.

There is no public endpoint for reading either collection. View them in the
Firestore Data tab in Google Cloud Console, or list beta signup emails from a
fish shell using your own IAM credentials:

```fish
./scripts/list-beta-signups.sh $PROJECT_ID
```

The script requires `gcloud`, `curl`, and `jq`. Grant human operators only the
Firestore read access they need. The Cloud Run runtime uses `roles/datastore.user`
to create documents without service-account keys. Firestore creation and REST
document writes follow the official [database management](https://cloud.google.com/firestore/docs/manage-databases)
and [createDocument](https://cloud.google.com/firestore/docs/reference/rest/v1/projects.databases.documents/createDocument)
interfaces.

## Optional private Gemini secret

Only a private, non-public service that intentionally enables live compilation
needs this secret. It is not a prerequisite for the public demo:

```fish
set GEMINI_SECRET evidue-gemini-api-key
gcloud services enable secretmanager.googleapis.com
gcloud secrets create $GEMINI_SECRET --replication-policy=automatic
gcloud secrets versions add $GEMINI_SECRET --data-file=-
```

Do not add `--set-secrets GEMINI_API_KEY=...` to the public demo deployment.

## GitHub Actions deployment

`.github/workflows/deploy-cloud-run.yml` runs formatting, linting, focused
backend tests, frontend lint/tests/build, then deploys every push to `main`.
It uses Workload Identity Federation (WIF), avoiding a long-lived service
account key. The public workflow does not read or require `GEMINI_API_KEY`.

After the manual setup, create a deployer and WIF provider (replace the GitHub
organization and repository):

```fish
set GITHUB_ORG your-github-org
set GITHUB_REPO evidue
set PROJECT_NUMBER (gcloud projects describe $PROJECT_ID --format='value(projectNumber)')
set DEPLOYER_SERVICE_ACCOUNT evidue-github-deployer@$PROJECT_ID.iam.gserviceaccount.com

gcloud iam service-accounts create evidue-github-deployer --display-name="Evidue GitHub Actions deployer"
gcloud projects add-iam-policy-binding $PROJECT_ID --member="serviceAccount:$DEPLOYER_SERVICE_ACCOUNT" --role="roles/run.admin"
gcloud projects add-iam-policy-binding $PROJECT_ID --member="serviceAccount:$DEPLOYER_SERVICE_ACCOUNT" --role="roles/artifactregistry.writer"
gcloud iam service-accounts add-iam-policy-binding $RUNTIME_SERVICE_ACCOUNT --member="serviceAccount:$DEPLOYER_SERVICE_ACCOUNT" --role="roles/iam.serviceAccountUser"
gcloud iam workload-identity-pools create github --location=global --display-name="GitHub Actions"
gcloud iam workload-identity-pools providers create-oidc github --location=global --workload-identity-pool=github --issuer-uri="https://token.actions.githubusercontent.com" --attribute-mapping="google.subject=assertion.sub,attribute.repository=assertion.repository,attribute.ref=assertion.ref" --attribute-condition="assertion.repository=='$GITHUB_ORG/$GITHUB_REPO' && assertion.ref=='refs/heads/main'"
gcloud iam service-accounts add-iam-policy-binding $DEPLOYER_SERVICE_ACCOUNT --role="roles/iam.workloadIdentityUser" --member="principalSet://iam.googleapis.com/projects/$PROJECT_NUMBER/locations/global/workloadIdentityPools/github/attribute.repository/$GITHUB_ORG/$GITHUB_REPO"
```

Add these GitHub repository secrets: `GCP_PROJECT_ID`,
`GCP_WORKLOAD_IDENTITY_PROVIDER` (the provider resource name), and
`GCP_DEPLOYER_SERVICE_ACCOUNT`. Configure the optional GitHub `production`
environment if deployment approvals are desired.

Set the following GitHub Actions variables when needed:

- `CLOUD_RUN_MIN_INSTANCES`: use `1` during a launch window and `0` afterward.
- `VITE_POSTHOG_KEY` and `VITE_POSTHOG_HOST`: optional anonymous product analytics.
  They are Docker build arguments because Vite embeds `VITE_*` values at build
  time. Leave both unset to disable analytics. If enabled, set Cloud Run's
  `POSTHOG_HOST` to the same HTTPS host so its CSP permits that exact origin.
