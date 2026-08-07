# Evidue

Evidue independently reconciles outcome-priced AI-agent vendor invoices against
contractual billing rules and customer-owned operational evidence.

This repository contains both the protected product workflow (`/pilot`) and the
synthetic public narrative demo (`/demo`). The product path accepts operator-
provided agreements, invoices, and customer-side evidence; the demo path uses
fictional Acme Commerce / Nova Support AI data only.

## Run the product locally

From a fish shell:

```fish
./scripts/bootstrap.sh
cp .env.example .env
set token (openssl rand -hex 32)
sed -i "s/^EVIDUE_PILOT_TOKEN=.*/EVIDUE_PILOT_TOKEN=$token/" .env
./scripts/dev.sh
```

Open <http://localhost:5173/pilot>, enter the generated workspace access key,
and choose **Try sample workspace** or **Use my own data**. For arbitrary
customer contracts, also set `GEMINI_API_KEY` in `.env`; reconciliation itself
does not require model access after an AIR version is approved.

The normal-user workflow is:

```text
Contract → Rules → Invoice → Evidence → Reconcile → Export
```

Supported agreement inputs are pasted text, TXT/Markdown, DOCX, and text-based
PDF. Invoice CSVs include a header-preview/mapping step, so customers do not
have to rename their source columns before upload. Evidence accepts CSV, JSON,
and JSONL. Finance exports include a corrected invoice CSV, dispute CSV,
summary/evidence JSON, and a standalone HTML review report.

See [docs/PRODUCT.md](docs/PRODUCT.md),
[docs/DESIGN_SYSTEM.md](docs/DESIGN_SYSTEM.md),
[docs/NORMAL_USER_ACCEPTANCE.md](docs/NORMAL_USER_ACCEPTANCE.md), and
[docs/IMPLEMENTATION_MATRIX.md](docs/IMPLEMENTATION_MATRIX.md).

## Run the synthetic public demo

```fish
./scripts/setup-demo.sh
./scripts/dev.sh
```

The demo setup rebuilds the disposable synthetic database, installs dependencies,
seeds the headline fixture, and runs the fast validation suite. See
[SETUP.md](SETUP.md) for manual and Docker instructions.

Open <http://localhost:5173/demo>. The backend API is available at
<http://localhost:8000/api/health>.

The golden path starts with a submitted $15,000 invoice. Click **Run
reconciliation** to invoke the backend engine. It evaluates all 10,000 claims,
persists the determinations, and returns a $12,480 corrected payable amount with
a $2,520 recommended deduction.

## Contract-to-rules workflow

The demo no longer treats Python constants as the source of truth for billing terms.
It implements the complete control boundary Evidue needs in production:

1. A Gemini compiler converts the natural-language contract into a constrained JSON rule proposal.
2. Pydantic rejects unknown operations, malformed windows, duplicate priorities, and invalid output.
3. The proposal remains `pending_approval` until a human approves an immutable version.
4. Reconciliation loads that approved version from SQLite and runs a generic deterministic interpreter.
5. The LLM is never called while deciding whether an invoice line is payable, disputed, or needs review.

The repository includes a validated recorded proposal so the technical preview works offline. To make a live Gemini
call, export `GEMINI_API_KEY` before starting the backend. `GEMINI_MODEL` is optional. No API key is checked
into this repository.

In the UI, open **Contract compiler**, click **Compile contract**, inspect the proposed operations, approve the
new version, and then run reconciliation. See [docs/CONTRACT_COMPILER.md](docs/CONTRACT_COMPILER.md).

## Contract-to-rules demo

Open `/demo/contracts/current` before running the invoice. Click **Compile contract**:

1. Gemini converts the natural-language order form into a constrained JSON rule proposal.
2. Pydantic validates the proposal against seven supported deterministic operators.
3. The proposal remains inactive until **Approve rule version** is clicked.
4. Reconciliation executes only the approved immutable version; the LLM never adjudicates a charge.

Set `GEMINI_API_KEY` in a local `.env` file for a live call. With no key, the same screen replays a checked-in, schema-validated Gemini response so the technical preview is reliable offline. See [docs/LLM_RULE_COMPILER.md](docs/LLM_RULE_COMPILER.md).

Before reconciliation, the demo now shows the production-shaped evidence path:
eight vendor and customer sources, aggregate source-record volumes, 9,975 direct
matches, 25 verified secondary-key matches, raw payload hashes, normalized
records, and source authority. Representative source exports are checked into
`demo-data/`; see [docs/REAL_DATA_INGESTION.md](docs/REAL_DATA_INGESTION.md).

## Validate

```fish
./scripts/dev-check.sh fast
./scripts/dev-check.sh full
./scripts/product-smoke.sh
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
[docs/DEMO_SCRIPT.md](docs/DEMO_SCRIPT.md) for the demo narration.

## Hosted deployment

Temporary beta-validation deployment: Railway. This branch uses no
Firestore or Google Cloud credentials; see [docs/DEPLOY_RAILWAY.md](docs/DEPLOY_RAILWAY.md).

Longer-term container deployment reference: Google Cloud Run. See
[docs/DEPLOY_CLOUD_RUN.md](docs/DEPLOY_CLOUD_RUN.md); it is not used by the
Railway deployment.

## Product surfaces

- `/demo` — finance control overview
- `/demo/invoices` — recurring invoice operations
- `/demo/invoices/current` — complete working June reconciliation
- `/demo/contracts/current` — contract clause-to-rule control center
- `/demo/disputes/current` — dispute package and financial handoff
- `/demo/data-sources` — production-shaped collection, matching, and raw-record provenance
- `/demo/vendor-preflight` — vendor-side invoice preflight
- `/demo/outcome-ledger` — shared outcome receipt model
- `/demo/lab` — technical edge-case scenarios

Only the June 2026 invoice is a fully interactive reconciliation. Historical invoice rows are explicitly labelled illustrative synthetic history; connector statuses are explicitly labelled local fixtures rather than live integrations.

## Product architecture

The demo presents Evidue as the financial control layer for outcome-priced AI agents:

- **Evidue Prove** (`/demo/vendor-preflight`) helps agent vendors preflight proposed invoice claims and find revenue at risk before billing.
- **Outcome Ledger** (`/demo/outcome-ledger`) shows the versioned proof envelope connecting agent execution, contract rules, and operational evidence.
- **Evidue** (`/demo/invoices/current`) independently calculates what the customer should pay.

The vendor workspace cannot modify customer-approved rules, customer-private evidence, or the customer's final payment decision.


## UI template

The interface uses a structural adaptation of Material UI's official open-source Dashboard template. See `docs/UI_TEMPLATE.md` for the source, adopted components, and Evidue-specific changes.

See `docs/FINAL_REPAIR_STATUS.md` for the final ingestion-demo repair and validation record.

## Protected product API

The real-data pilot is deliberately separate from the synthetic demo:

- demo data uses `data/evidue.db`;
- pilot data uses `data/evidue-pilot.db` by default;
- every `/api/pilot/*` endpoint requires a bearer token;
- pilot reconciliation is scoped to one invoice and one approved contract compilation;
- raw uploads, normalized records, identity decisions, and every reconciliation run are retained.

For one workspace, configure a long random token:

```fish
set -x EVIDUE_PILOT_TOKEN (openssl rand -hex 32)
```

Call pilot endpoints with:

```text
Authorization: Bearer <EVIDUE_PILOT_TOKEN>
```

For multiple controlled beta workspaces, prefer:

```fish
set -x EVIDUE_WORKSPACE_TOKENS '{"acme":"<long token>","globex":"<long token>"}'
```

Each workspace key selects a separate server-side database; one workspace cannot
retrieve another workspace's pilot/product records.

The API sequence is:

1. `POST /api/pilot/contract` or `/api/pilot/contract/text`
2. `POST /api/pilot/contracts/{contract_id}/compile-native`
3. Review conformance/assurance, then `POST /api/pilot/air-versions/{id}/approve`
4. `POST /api/pilot/invoice`
5. `POST /api/pilot/evidence`
6. `POST /api/pilot/match`
7. Review suggested/unresolved matches and confirm only defensible links.
8. `POST /api/pilot/reconcile`
9. Download the corrected invoice, review report, disputes CSV, summary, or evidence package.

Custom contracts require `GEMINI_API_KEY`; the recorded compiler proposal is accepted only for the bundled demo contract. `pypdf` is a declared runtime dependency for text-based PDF extraction; DOCX parsing uses the standard library and does not require Microsoft Office.

Each reconciliation run is append-only. Use the comparison endpoint to show what changed after new evidence, and record the customer's review with `/api/pilot/reconciliations/{run_id}/customer-review`. This keeps engine output separate from customer acceptance evidence instead of overwriting determinations.

### Product frontend

Open `/pilot` to use the protected workflow without raw curl commands. The access key is stored in browser `sessionStorage` only and sent as a bearer header. The default UI is written for finance/operators: guided contract review, invoice mapping, evidence completeness, identity review, deterministic reconciliation, line-level contract/evidence provenance, and finance exports. AIR hashes, proof planning, derived facts, and audit history live under **Advanced details**.

The compiler now treats the fixed contract rate as executable policy through `claim_amount_equals`. It also blocks approval when a material clause is ambiguous or unsupported rather than silently omitting it.


## Generalized agreement runtime

See `docs/AGREEMENT_RUNTIME.md` for native Agreement IR compilation, proof planning, fact derivation, and dual-run migration semantics.
