# Evidue

Evidue independently reconciles outcome-priced AI-agent vendor invoices against
contractual billing rules and customer-owned operational evidence.

This repository contains the protected product workflow (`/workspace`), a no-signup public
product trial (`/try`), and the deeper synthetic reference workspace (`/demo`). The
product path accepts operator-provided agreements, invoices, and customer-side evidence;
the public surfaces use fictional Acme Commerce / Nova Support AI data only.

## Run the product locally

From a fish shell:

```fish
./scripts/bootstrap.sh
cp .env.example .env
set token (openssl rand -hex 32)
sed -i "s/^EVIDUE_PILOT_TOKEN=.*/EVIDUE_PILOT_TOKEN=$token/" .env
./scripts/dev.sh
```

Open <http://localhost:5173/workspace>, enter the generated access key, and choose
**Try sample workspace** or **Use my own data**. After reconciliation, open
<http://localhost:5173/workspace/operations> for recurring vendor operations, exception review,
settlement approval, reproducibility fingerprints, and stateful vendor disputes.
`/workspace/settings` contains workspace defaults, preferred evidence systems, integration
readiness, and the protected reset control. Secrets remain server-side and are never
exposed by that page. For arbitrary
customer contracts, configure an Evidue-owned backend compiler provider (for example Gemini
or OpenAI) in the server environment. Customers never provide an LLM key; reconciliation
itself does not require model access after an AIR version is approved.

The normal-user workflow is:

```text
Vendor → Agreement → Approved AIR → Invoice → Evidence → Reconcile
       → Review exceptions → Approve payable → Vendor dispute
```

Supported agreement inputs are pasted text, TXT/Markdown, DOCX, and text-based
PDF. A reconciliation can include multiple governing documents such as a master
agreement, Order Form, SLA, additional terms, and amendments with explicit precedence
and effective dates. If the governing document set changes after rule approval, Evidue
invalidates the active rule version until the bundle is re-analyzed and re-approved. The
current pilot deliberately fails closed on a governing-document change inside one configured
reconciliation period instead of silently applying one policy across the boundary.

Invoice CSVs include mapping plus finance control totals before import, so customers do not
have to rename their source columns and can verify line count/billed total first. Evidence
accepts CSV, JSON, and JSONL and is guided by the approved contract's proof requirements.
Finance operations preserve machine determinations and record human review as an append-only
overlay. Approval is blocked until review exposure is dispositioned. Approved settlements can
open stateful dispute cases and export a real PDF vendor dispute package. Reconciliation runs
persist input-manifest and deterministic calculation hashes so identical inputs are
reproducible.

The current Product v1 source of truth is [docs/product-v1/PRODUCT_REQUIREMENTS.md](docs/product-v1/PRODUCT_REQUIREMENTS.md)
and [docs/product-v1/SYSTEM_ARCHITECTURE.md](docs/product-v1/SYSTEM_ARCHITECTURE.md). See also [docs/PRODUCT.md](docs/PRODUCT.md),
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

Open <http://localhost:5173/try> for the public no-signup product trial. It walks a
visitor through contract analysis, explicit human approval, and a 100-claim in-memory
deterministic reconciliation before showing the conversation CTA. Open
<http://localhost:5173/demo> for the deeper reference workspace. The backend API is
available at <http://localhost:8000/api/health>.

The `/try` flow never accepts customer data and never mutates `/workspace` or the authoritative
demo reconciliation. If a server-side Gemini key is configured, one live compiler run is
allowed per network per seven days; later runs transparently replay the validated recorded
model proposal while continuing to execute the real deterministic reconciliation engine.
See [docs/PUBLIC_TRY_DEMO.md](docs/PUBLIC_TRY_DEMO.md).

The golden path starts with a submitted $15,000 invoice. Click **Run
reconciliation** to invoke the backend engine. It evaluates all 10,000 claims,
persists the determinations, and returns a $12,480 corrected payable amount with
a $2,520 recommended deduction.

## Contract-to-rules workflow

The demo no longer treats Python constants as the source of truth for billing terms.
It implements the complete control boundary Evidue needs in production:

1. A server-owned, provider-independent interpretation pass decomposes material source language into an atomic requirement ledger.
2. The model cites deterministic source-span IDs; Evidue binds every requirement back to original contract bytes and hashes.
3. A second compiler pass maps those authoritative requirements to constrained AIR norms, settlement policies, and proof requirements without silently merging or dropping them.
4. Pydantic plus deterministic requirement/binding assurance rejects malformed, ungrounded, collapsed, unmapped, or data-source-incompatible semantics.
5. The proposal remains `pending_approval` until a human approves an immutable AIR version.
6. Reconciliation loads that approved version and runs the deterministic interpreter; no LLM decides line status or payable dollars.

The repository includes validated recorded proposals so technical previews and the core proof suite work offline. Live compilation uses server-side provider credentials configured by the Evidue operator, never by the customer.

In the UI, open **Contract compiler**, click **Compile contract**, inspect the proposed operations, approve the
new version, and then run reconciliation. See [docs/CONTRACT_COMPILER.md](docs/CONTRACT_COMPILER.md).

## Contract-to-rules demo

Open `/demo/contracts/current` before running the invoice. Click **Compile contract**:

1. Gemini converts the natural-language order form into a constrained JSON rule proposal.
2. Pydantic validates the proposal against seven supported deterministic operators.
3. The proposal remains inactive until **Approve rule version** is clicked.
4. Reconciliation executes only the approved immutable version; the LLM never adjudicates a charge.

For local developer testing, the Evidue operator may configure a server-side provider credential in `.env`; customers are never asked to supply an LLM key. With no provider credential, the same demo screen replays a checked-in, schema-validated response so the technical preview remains reliable offline. See [docs/LLM_RULE_COMPILER.md](docs/LLM_RULE_COMPILER.md).

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

- `/workspace` — protected contract/invoice/evidence reconciliation workbench
- `/workspace/operations` — protected review, settlement approval, trust, and vendor-dispute operations
- `/workspace/settings` — protected workspace configuration

Legacy `/pilot`, `/pilot/finance`, and `/pilot/config` UI routes redirect to the canonical `/workspace` surfaces. The backend API remains `/api/pilot/*` for compatibility.
- `/try` — no-signup, synthetic, human-approved public reconciliation trial
- `/demo` — deeper synthetic finance-control reference workspace
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

### Server-owned compiler providers

The protected product does **not** use BYOK. Configure provider credentials in the Evidue backend/deployment environment. For example:

```bash
export EVIDUE_LLM_PRIMARY=gemini
export GEMINI_API_KEY='...'
export GEMINI_MODEL='...'
# Optional production fallback:
export EVIDUE_LLM_FALLBACK=openai
export OPENAI_API_KEY='...'
export OPENAI_MODEL='...'
```

The browser only receives secret-free provider readiness metadata. Controlled qualification pins one provider/model and disables fallback so repeated runs remain interpretable.

For high-assurance agreements, `EVIDUE_LLM_ASSURANCE_PROVIDER` can request an independent second
compile. Material normalized-semantic disagreement blocks approval and goes to human review;
models never vote on the rule that determines money.


The real-data pilot is deliberately separate from the synthetic demo:

- demo data uses `data/evidue.db`;
- pilot data uses `data/evidue-pilot.db` by default;
- every `/api/pilot/*` endpoint requires a bearer token;
- the qualified kernel reconciles one invoice against one approved AIR version per run;
- the product layer manages multiple vendor engagements, invoices, reconciliation statements,
  review cases, approvals, and disputes across runs;
- raw uploads, normalized records, identity decisions, machine determinations, human review
  overlays, approvals, and every reconciliation run are retained.

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

Custom contracts require a server-configured native compiler provider in live mode; customers are never asked for provider credentials. The recorded compiler proposal is accepted only for controlled/demo fixtures. `pypdf` is a declared runtime dependency for text-based PDF extraction; DOCX parsing uses the standard library and does not require Microsoft Office.

Each reconciliation run is append-only. Use the comparison endpoint to show what changed after new evidence, and record the customer's review with `/api/pilot/reconciliations/{run_id}/customer-review`. This keeps engine output separate from customer acceptance evidence instead of overwriting determinations.

### Product frontend

Open `/workspace` to use the protected workflow without raw curl commands. The access key is stored in browser `sessionStorage` only and sent as a bearer header. The default UI is written for finance/operators: guided multi-document contract review, deterministic plain-English contract rules, invoice control totals, a contract-driven evidence checklist, deterministic reconciliation, actionable line-level explanations, rerun deltas, and vendor-facing finance exports. AIR hashes, proof planning, derived facts, and audit history live under **Advanced details**. Workspace defaults and integration readiness live at `/workspace/settings`; that page never reads server secrets.
A pending AIR can also be replayed against an existing invoice through the
financial-impact API so Finance can see the exact dollar effect of a contract/rule change before
approving it; the result is a simulation and does not replace the approved AIR.

For low-friction pilot validation, an approved AIR can also replay every accepted historical
invoice already uploaded for that contract through
`GET /api/pilot/contracts/{contract_id}/historical-replay`. Historical replay is deterministic,
invokes no LLM, creates no reconciliation runs, and reports aggregate billed/payable/disputed/
needs-review totals with money-conservation checks. It is explicitly analysis, not a payable
instruction and not a claim of recovered savings.

The compiler now treats the fixed contract rate as executable policy through `claim_amount_equals`. It also blocks approval when a material clause is ambiguous or unsupported rather than silently omitting it.


## Real-contract compiler qualification

The normal test suite proves deterministic behavior after an AIR exists. Real-contract
qualification separately tests whether an unfamiliar commercial agreement is interpreted
correctly before approval. The harness supports multi-document packs, reviewer-controlled
gold financial terms, repeated live-model runs, material contract mutations, and optional
reviewed synthetic claim/evidence scenarios that validate the complete path from real
contract semantics to deterministic dollars.

A run without reviewed, exhaustive gold can produce a structural/review report but is
**never reported as qualified**. Likewise, provisional engineering labels cannot satisfy
the release qualification gate. See [docs/CONTRACT_QUALIFICATION.md](docs/CONTRACT_QUALIFICATION.md).

Public source definitions are catalogued under `qualification/public_sources.json`. Download
them locally, validate/review the gold independently, then pin a configured provider for live qualification.

```bash
python scripts/fetch_qualification_sources.py --pack sec-demandtec-target-2010
PYTHONPATH=backend uv run python scripts/qualify_contract.py \
  --pack qualification/downloaded/sec-demandtec-target-2010 \
  --mode live --provider gemini --runs 1 \
  --output /tmp/evidue-contract-qualification.json --exit-zero-on-review
```

For normal development, use the one-command gates:

```bash
./scripts/check-fast.sh       # bootstrap Python quality tools + offline verification kernel
./scripts/check-all.sh        # bootstrap everything + lint + backend + frontend + E2E
./scripts/fix-and-check.sh     # safe Python fixes, then the complete offline repository gate
./scripts/check-live.sh --provider gemini --model "$GEMINI_MODEL"
./scripts/check-release.sh --provider gemini --model "$GEMINI_MODEL"
```

`check-all.sh` is deliberately offline with respect to LLM providers; `fix-and-check.sh` first applies safe Python formatting/lint fixes and then runs that same complete offline gate. `check-release.sh` adds pinned live-provider qualification. The wrappers fail fast on syntax/hygiene/Ruff errors before expensive tests, and long backend/browser gates stream progress instead of appearing hung. Both generate `artifacts/validation/latest.json` and `latest.md`. See [docs/CONTRACT_QUALIFICATION.md](docs/CONTRACT_QUALIFICATION.md), [docs/ATOMIC_REQUIREMENT_LEDGER.md](docs/ATOMIC_REQUIREMENT_LEDGER.md), and [docs/LEAP_REPORT.md](docs/LEAP_REPORT.md).


## Generalized agreement runtime

See `docs/AGREEMENT_RUNTIME.md` for native Agreement IR compilation, proof planning, fact derivation, and dual-run migration semantics.
