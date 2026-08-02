# Deploy Evidue to Google Cloud Run

Evidue is one Docker service: FastAPI serves both the API and the compiled Vite
frontend. The existing `Dockerfile` already works with Cloud Run without
modification: its command binds Uvicorn to Cloud Run's injected `$PORT`, and
`/api/health` is available for a Cloud Run startup probe.

This deployment is deliberately disposable. `EVIDUE_PUBLIC_DEMO=true` makes the
public workspace read-only, and the SQLite database at `/app/data/evidue.db` is
rebuilt from the deterministic fixture when an instance starts. Do not use this
service for customer data.

## Prerequisites

- Install and authenticate the [Google Cloud CLI](https://cloud.google.com/sdk/docs/install).
- Install Docker for the first local image build.
- Pick a globally unique project ID and a billing account.
- Keep `GEMINI_API_KEY` out of Git, shell history, and deployment manifests.

## First manual deployment

Run these commands from a fish shell after replacing the example values:

```fish
set -l PROJECT_ID your-gcp-project-id
set -l BILLING_ACCOUNT 000000-000000-000000
set -l REGION us-central1
set -l SERVICE evidue-demo
set -l REPOSITORY evidue
set -l GEMINI_SECRET evidue-gemini-api-key

gcloud auth login
gcloud projects create $PROJECT_ID --name="Evidue Demo"
gcloud billing projects link $PROJECT_ID --billing-account=$BILLING_ACCOUNT
gcloud config set project $PROJECT_ID
gcloud services enable run.googleapis.com artifactregistry.googleapis.com secretmanager.googleapis.com iamcredentials.googleapis.com
gcloud artifacts repositories create $REPOSITORY --repository-format=docker --location=$REGION --description="Evidue Cloud Run images"
```

Create the Secret Manager secret without placing its value in a command:

```fish
gcloud secrets create $GEMINI_SECRET --replication-policy=automatic
gcloud secrets versions add $GEMINI_SECRET --data-file=-
```

The second command reads the key from standard input. Paste the key, press
Enter, then press `Ctrl-D`. If you do not need live Gemini compilation, create
the secret with a deliberately empty-safe placeholder only after deciding how
you want to rotate it; the included recorded proposal works without a live key.

Create the dedicated Cloud Run runtime identity and permit it to read this one
secret:

```fish
set -l PROJECT_NUMBER (gcloud projects describe $PROJECT_ID --format='value(projectNumber)')
set -l RUNTIME_SERVICE_ACCOUNT evidue-runtime@$PROJECT_ID.iam.gserviceaccount.com

gcloud iam service-accounts create evidue-runtime --display-name="Evidue Cloud Run runtime"
gcloud secrets add-iam-policy-binding $GEMINI_SECRET \
  --member="serviceAccount:$RUNTIME_SERVICE_ACCOUNT" \
  --role="roles/secretmanager.secretAccessor"
```

Build, push, and deploy the existing Dockerfile:

```fish
set -l IMAGE $REGION-docker.pkg.dev/$PROJECT_ID/$REPOSITORY/$SERVICE:manual

gcloud auth configure-docker $REGION-docker.pkg.dev
docker build --tag $IMAGE .
docker push $IMAGE

gcloud run deploy $SERVICE \
  --image $IMAGE \
  --region $REGION \
  --allow-unauthenticated \
  --min-instances 0 \
  --port 8080 \
  --service-account $RUNTIME_SERVICE_ACCOUNT \
  --set-env-vars EVIDUE_PUBLIC_DEMO=true,EVIDUE_DB_PATH=/app/data/evidue.db \
  --set-secrets GEMINI_API_KEY=$GEMINI_SECRET:latest \
  --startup-probe httpGet.path=/api/health,httpGet.port=8080,initialDelaySeconds=0,timeoutSeconds=5,periodSeconds=10,failureThreshold=10
```

Cloud Run injects `PORT=8080`; the Dockerfile's `${PORT:-10000}` command uses it
automatically. The startup probe verifies `/api/health`, and
`--min-instances 0` allows the synthetic demo to scale to zero.

After the command returns, verify the public service:

```fish
set -l SERVICE_URL (gcloud run services describe $SERVICE --region $REGION --format='value(status.url)')
curl --fail $SERVICE_URL/api/health
echo $SERVICE_URL/demo
```

## GitHub Actions continuous deployment

`.github/workflows/deploy-cloud-run.yml` deploys on every push to `main`,
matching the previous commit-triggered deployment. It uses Workload Identity
Federation (WIF), rather than a long-lived Google service-account key. The
workflow builds and pushes to Artifact Registry, writes the GitHub
`GEMINI_API_KEY` secret as a new Secret Manager version, and binds Cloud Run to
that secret with `--set-secrets`.

Before enabling the workflow, create the image repository and runtime service
account from the manual setup above, then create a deployer identity and WIF
provider. Substitute your GitHub organization and repository:

```fish
set -l GITHUB_ORG your-github-org
set -l GITHUB_REPO evidue
set -l POOL_ID github
set -l PROVIDER_ID github
set -l DEPLOYER_SERVICE_ACCOUNT evidue-github-deployer@$PROJECT_ID.iam.gserviceaccount.com

gcloud iam service-accounts create evidue-github-deployer --display-name="Evidue GitHub Actions deployer"
gcloud projects add-iam-policy-binding $PROJECT_ID --member="serviceAccount:$DEPLOYER_SERVICE_ACCOUNT" --role="roles/run.admin"
gcloud projects add-iam-policy-binding $PROJECT_ID --member="serviceAccount:$DEPLOYER_SERVICE_ACCOUNT" --role="roles/artifactregistry.writer"
gcloud projects add-iam-policy-binding $PROJECT_ID --member="serviceAccount:$DEPLOYER_SERVICE_ACCOUNT" --role="roles/secretmanager.admin"
gcloud iam service-accounts add-iam-policy-binding $RUNTIME_SERVICE_ACCOUNT --member="serviceAccount:$DEPLOYER_SERVICE_ACCOUNT" --role="roles/iam.serviceAccountUser"

gcloud iam workload-identity-pools create $POOL_ID --location=global --display-name="GitHub Actions"
gcloud iam workload-identity-pools providers create-oidc $PROVIDER_ID \
  --location=global \
  --workload-identity-pool=$POOL_ID \
  --display-name="GitHub Actions provider" \
  --issuer-uri="https://token.actions.githubusercontent.com" \
  --attribute-mapping="google.subject=assertion.sub,attribute.repository=assertion.repository,attribute.ref=assertion.ref" \
  --attribute-condition="assertion.repository=='$GITHUB_ORG/$GITHUB_REPO' && assertion.ref=='refs/heads/main'"
gcloud iam service-accounts add-iam-policy-binding $DEPLOYER_SERVICE_ACCOUNT \
  --role="roles/iam.workloadIdentityUser" \
  --member="principalSet://iam.googleapis.com/projects/$PROJECT_NUMBER/locations/global/workloadIdentityPools/$POOL_ID/attribute.repository/$GITHUB_ORG/$GITHUB_REPO"
```

Add these GitHub Actions repository secrets:

- `GCP_PROJECT_ID`: the Google Cloud project ID.
- `GCP_WORKLOAD_IDENTITY_PROVIDER`: the full provider resource name from:

  ```fish
  gcloud iam workload-identity-pools providers describe $PROVIDER_ID --location=global --workload-identity-pool=$POOL_ID --format='value(name)'
  ```

- `GCP_DEPLOYER_SERVICE_ACCOUNT`: `$DEPLOYER_SERVICE_ACCOUNT`.
- `GEMINI_API_KEY`: the live Gemini key. It is only exposed to the workflow's
  Secret Manager step and is never passed to `gcloud run deploy` as plaintext.

The `production` environment in the workflow is optional but recommended so
GitHub can require review before deployment. If you use a different region,
service name, or Artifact Registry repository, change the three top-level
workflow environment values and use the same values in the setup commands.

## Operational notes

- Every new workflow run creates a Secret Manager version. Disable or destroy
  superseded versions according to your key-rotation policy.
- A secret passed as an environment variable is resolved when a Cloud Run
  instance starts. Redeploy after rotating it, as the workflow does.
- The service is intentionally public via `--allow-unauthenticated`; do not add
  customer data or credentials to its SQLite database.
