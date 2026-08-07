# Product plan

This is the working plan for the `product` branch. It turns the YC demo
into a product that can run one real customer's invoice through the
existing deterministic engine.

The demo stays on `main`. Everything on `product` must work toward a
single goal: **one real invoice, reconciled against real evidence, with a
customer who confirms the output is valuable.**

## Implementation invariants

The demo and pilot share deterministic domain code only. They use separate
persistence, and every `/api/pilot/*` route is disabled until a strong
`EVIDUE_PILOT_TOKEN` is configured. Pilot uploads, contracts, invoices,
evidence, matches, and reconciliation runs must never be read by demo queries
or deleted by demo reset operations.

Real-data lineage is preserved as: raw source record → versioned normalization
→ accepted/manual match → deterministic determination. Heuristic composite
matches are suggestions only and cannot affect money until an operator
confirms them. Reconciliation runs are append-only.

---

## What we keep untouched

These parts of the demo are production-quality and do not need to be
rewritten:

**Domain engine** (`backend/app/domain/engine.py`, ~600 lines). Pure
Python, zero framework imports, deterministic, already handles all six
rule operations and the two-pass duplicate-attribution logic. It takes
`(OutcomeClaim, list[OperationalEvent])` pairs and returns
`OutcomeDetermination` objects. The engine does not know where the data
came from. This is the most valuable code in the repo.

**Domain models** (`backend/app/domain/models.py`). Frozen dataclasses:
`OutcomeClaim`, `OperationalEvent`, `EvidenceAttribution`,
`OutcomeDetermination`, `ExecutableRule`, `RuleProgram`. These are the
interface contract between ingestion and reconciliation. They do not
change.

**Contract compiler** (`backend/app/contracts/compiler.py`). Gemini
proposes structured JSON rules → Pydantic validates against an allowlist
of operations → human approves an immutable version → engine executes
it. This is the correct LLM boundary. It stays.

**Evidence attribution** (`attribute_evidence` in `engine.py`).
Classifies every event as `directly_matched`, `requires_review`,
`unrelated`, or `contradictory` before any rule runs. This already
anticipates messy real evidence (missing outcome IDs, duplicate source
records, conflicting terminal events). It stays.

**Money handling**. `Decimal` everywhere, `NUMERIC(12,2)` in the
database, fixed two-decimal string serialization, mutually exclusive
payable/disputed/needs_review buckets, the identity
`submitted = payable + disputed + review`. This stays.

**Test suite**. 61+ backend tests, Vitest, ESLint, Playwright golden
paths, `dev-check.sh`. The product branch adds tests; it does not
weaken the existing suite.

---

## What we are building toward

The first real customer workflow, end to end:

```
Contract PDF/text upload
→ LLM proposes rules (existing compiler)
→ Human approves immutable rule version (existing flow)
→ Vendor invoice CSV upload
→ Customer evidence CSV/JSON uploads (support, payment, identity map)
→ Parsing and normalization into OutcomeClaim + OperationalEvent
→ Identity matching (direct + secondary key + manual review queue)
→ Deterministic reconciliation (existing engine, unchanged)
→ Corrected payable amount
→ Line-level determinations with evidence
→ Dispute package export (CSV + JSON, existing export code)
```

Everything in that chain already exists except the upload→parse→normalize
step and the identity matching against messy real IDs.

---

## What we will not build (until a pilot succeeds)

These are technically credible ideas that do not improve validation
right now:

- Vendor self-service portal or vendor login
- Self-service tenant creation or onboarding wizard
- Multi-region deployment
- Generalized connector SDK or integration platform
- Mobile application
- Advanced analytics or custom report builder
- Configurable workflow builder
- Automated vendor payments
- Contract authoring (we compile, not write)
- Broad AI-agent observability or QA scoring
- Real-time streaming reconciliation
- Formal marketplace integrations
- SOC 2 certification (security hygiene yes; formal programme no)
- Automated billing or metering (instrument it; do not build a billing system)

---

## Validation gates

Work is gated by evidence, not calendar estimates. Each gate must pass
before the next stage of engineering begins.

### Gate A — Qualified design partner and sample data

**Required evidence:**

- 5+ qualified customer conversations completed (companies that pay
  outcome-priced AI agent invoices above $5k/month).
- 1 company willing to share an anonymized or real invoice.
- 1 company able to describe the contractual outcome definition.
- 1 company able to export relevant operational evidence (support
  tickets, payment events, or both).
- Written agreement to evaluate reconciliation output.
- Evidence that the recoverable amount or saved labour is commercially
  meaningful (not a $200/month vendor contract).

**No major architecture work before this gate passes.** Conversations
with prospects will reveal which evidence sources actually matter, which
systems they actually use, and what format their data actually arrives
in. Building connectors before knowing the answers means building the
wrong connectors.

### Gate B — One invoice imported and normalized

- Vendor invoice CSV parsed into `OutcomeClaim` rows.
- At least one customer evidence source parsed into
  `OperationalEvent` rows.
- Data is in the database and the existing `run_reconciliation` code
  path can consume it (it already converts DB rows → domain objects
  via `_domain_claim` and `_domain_event`).

### Gate C — ≥90% of claims matched or explicitly in review

- Direct outcome-ID matches work on the real data.
- Secondary-key matching handles the cases where systems use different
  IDs.
- Unmatched claims are surfaced in a review queue, not silently dropped.
- The match rate and unmatched financial value are visible.

### Gate D — Customer confirms determinations are materially correct

- The customer reviews the payable/disputed/needs_review breakdown.
- Disputed claims have evidence that the customer recognizes as real.
- The customer does not identify major false positives or false
  negatives (some disagreement is expected — that is what needs_review
  is for).

### Gate E — Second reconciliation or paid pilot

- Same customer provides a second invoice, or a second customer runs
  the workflow.
- This proves the product is not a one-off consulting engagement.

### Gate F — Production hardening

Only after Gate E:

- Postgres migration.
- Organization/tenant model.
- Authentication and authorization.
- Background jobs.
- Recurring ingestion.
- Monitoring and alerting.

---

## Stage 1 — Upload-based ingestion

This is the first real engineering work on the product branch. It
replaces the fixture generator (`backend/app/fixtures/demo.py`) with
file upload endpoints that produce the same domain objects the engine
already consumes.

### 1.1 Upload endpoints

New API routes under `/api/pilot/`:

```
POST /api/pilot/contract      — upload contract text or PDF
POST /api/pilot/invoice        — upload vendor invoice CSV
POST /api/pilot/evidence       — upload customer evidence CSV/JSON/JSONL
POST /api/pilot/identity-map   — upload identity mapping CSV
GET  /api/pilot/status         — ingestion status and match summary
```

These are operator-assisted, token-authenticated `multipart/form-data`
file uploads. They are not public endpoints, API integrations, or webhooks.

The demo routes (`/api/demo/*`) remain untouched. The product routes are a
parallel path backed by a separate pilot database. They share the domain engine
but not unscoped persisted data or the demo reconciliation function.

### 1.2 Parsers

Each upload type needs a parser that validates the file and produces
normalized rows. The parsers must handle:

**Invoice CSV parser.** Reads a vendor claim manifest. The demo fixture
`demo-data/vendor/june-claim-manifest.csv` shows the expected shape:
`outcome_id`, `customer_reference`, `account_reference`,
`claimed_outcome_type`, `claimed_completion_time`, `billed_amount`.
The real parser needs to handle column name variations (the first
design partner's column names will not match the demo's), missing
optional columns, and basic validation (required fields present, amounts
parseable, timestamps parseable).

The parser produces `OutcomeClaimRow` objects for the database.

**Evidence parser.** Reads customer operational evidence. The demo has
three shapes: support events (JSONL), payment events (JSONL), and
billing ledger (CSV). The real parser needs to:

- Accept CSV, JSON, and JSONL.
- Map source fields to the normalized `OperationalEvent` schema:
  `source_system`, `event_type`, `timestamp`, `customer_id`,
  `outcome_id` (if present), `values` (dict of contextual fields).
- Store the raw payload alongside the normalized record.
- Hash the payload for integrity.
- Not require the exact column names from the demo — use a configurable
  field mapping per source type.

The parser produces `OperationalEventRow` objects for the database.

**Identity map parser.** Reads a mapping CSV that connects IDs across
systems (e.g., `conversation_id` → `customer_id` → `account_id` →
`outcome_id`). The demo fixture `customer-account-map.csv` is the
reference shape.

**Contract parser.** Accepts plain text (the existing compiler already
handles this) or extracts text from a PDF. The extracted text goes
through the existing `compile_with_gemini` → Pydantic validation →
human approval flow.

### 1.3 Normalization rules

The gap between the demo and reality is that the demo uses a single
deterministic generator that produces perfectly clean, perfectly
matching data. Real data will have:

- Different column names per customer.
- Missing fields.
- Different timestamp formats.
- IDs that do not match across systems.
- Duplicate records.
- Records from irrelevant time periods.

The normalization layer sits between the parser and the database. It
must:

- Accept a source-type label (`zendesk_tickets`, `stripe_refunds`,
  `intercom_conversations`, `csv_generic`, etc.).
- Apply a field mapping for that source type.
- Convert timestamps to UTC ISO 8601.
- Normalize IDs (trim whitespace, case handling).
- Classify each record by event type based on the source-type rules.
- Reject records with missing required fields and log the rejection
  reason.
- Store both the raw and normalized form.

For the first pilot, the field mapping can be a Python dict in the
codebase, not a configurable UI. We will know the exact source system
after Gate A and can hardcode the mapping for that one system.

### 1.4 What changes in the database

The pilot has dedicated `PilotClaimRow`, `PilotEventRow`, and related
`pilot_*` tables in a separate database. Repository adapters convert these rows
to the same immutable domain objects consumed by the engine. The fixture
generator and demo tables are never used by the pilot path.

Pilot tables include:

```
UploadRow
  id: str
  upload_type: str (invoice | evidence | identity_map | contract)
  filename: str
  uploaded_at: datetime
  status: str (processing | complete | failed)
  rows_parsed: int
  rows_accepted: int
  rows_rejected: int
  error_summary: str | None
  source_type: str | None (zendesk_tickets, stripe_refunds, etc.)

UploadRejectionRow
  id: int
  upload_id: str (FK → UploadRow)
  row_number: int
  reason: str
  raw_data: JSON
```

This gives visibility into what was uploaded, what was accepted, and
what failed — which matters when someone's first CSV has 200 rows that
do not parse.

### 1.5 The upload does not replace reset

The demo uses `reset()` to regenerate the entire database from fixtures.
The product path never calls reset. It appends uploaded data to the
existing tables. A "clear and re-upload" action is explicit and
separate.

The existing `run_reconciliation()` function in `repository.py` already
reads all `OutcomeClaimRow` and `OperationalEventRow` from the database,
converts them to domain objects, and passes them to `reconcile()`. It
does not care whether those rows came from a fixture generator or a
file upload. This is why the product path works without changing the
engine.

---

## Stage 2 — Identity matching on real data

This is the hardest part of the product. The demo has a 99.75% direct
match rate by construction. Real data will not.

### 2.1 The matching pipeline

After upload and normalization, each `OperationalEventRow` needs to be
associated with an `OutcomeClaim`. The existing `EvidenceMatchRow` table
already has the right schema: `raw_record_id`, `outcome_id`, `status`,
`match_method`, `confidence`, `reason`.

The matching pipeline runs in this order:

1. **Direct outcome ID match.** If the event has an `outcome_id` that
   matches a claim's `outcome_id`, it is a direct match with confidence
   1.0. This is what the demo does for 9,975 of 10,000 records.

2. **Secondary key match via identity map.** If the event has a
   `conversation_id` or `customer_id` + `account_id` combination that
   appears in the uploaded identity map, resolve to `outcome_id` through
   the map. Confidence depends on the key quality (conversation_id is
   stronger than customer_id alone).

3. **Composite key match.** If the event has `customer_id` +
   `timestamp within window` + `action type` that uniquely identifies a
   claim, match with lower confidence and record the rationale.

4. **Unresolved.** Events that do not match any claim go into a review
   queue. They are not silently discarded.

The matching pipeline writes `EvidenceMatchRow` records. After matching,
the reconciliation path reads `OperationalEventRow` records and
groups them by `outcome_id` — the same code path that already works.

### 2.2 The identity review workbench

This is a new UI surface. For each unmatched or low-confidence event:

- Show the event's raw fields.
- Show candidate claims it might belong to (by customer ID, timestamp
  proximity, action type).
- Let the operator confirm or reject a match.
- Store the confirmed match as a `ManualMatchRow` with the operator's
  rationale.
- The confirmed match feeds back into the matching pipeline so
  re-reconciliation uses it.

This is essential because the first real data will have match problems
we cannot predict. Without this surface, every match failure requires
a code change. With it, an operator (you) can fix matches and keep
the reconciliation moving.

### 2.3 New database tables for matching

```
ManualMatchRow
  id: int
  event_id: str (FK → OperationalEventRow)
  outcome_id: str
  confirmed_by: str
  confirmed_at: datetime
  rationale: str
  supersedes_match_id: int | None (FK → EvidenceMatchRow)
```

### 2.4 Match quality metrics

After matching completes, the status endpoint returns:

- Total events uploaded.
- Direct matches (count, %).
- Secondary matches (count, %).
- Manual matches (count, %).
- Unresolved (count, %, financial value at stake).

The unresolved financial value is important: if 5% of events are
unmatched but they represent $50 of a $15,000 invoice, it is not
blocking. If they represent $3,000, the matching needs more work
before reconciliation results are trustworthy.

---

## Stage 3 — Pilot reconciliation

Once claims and evidence are uploaded and matched, reconciliation uses
the existing code path:

1. `repository.run_reconciliation()` reads claims and events from the
   database.
2. `_domain_claim()` and `_domain_event()` convert DB rows to domain
   objects. These functions already exist.
3. `domain.engine.reconcile()` runs the two-pass evaluation. Unchanged.
4. Results are stored as `OutcomeDeterminationRow`. Unchanged.
5. Exports (disputes CSV, evidence JSON, summary JSON) work unchanged.

### 3.1 What might break on real data

The engine is correct, but it was validated only on synthetic data
where every claim has a perfectly constructed event set. Real data
will surface:

**Claims with no evidence at all.** The engine handles this — a claim
with no directly matched events and no contradictory evidence will
hit the `validate_evidence_envelope` rule and get `needs_review`
because the closure event is missing. But the UI needs to show this
clearly: "no evidence found for this claim" is different from
"evidence found but it contradicts the claim."

**Claims with evidence from the wrong time period.** The billing
period rule (`claim_datetime_in_range`) uses the approved rule's
`start` and `end_exclusive` parameters. For a real invoice, these
must match the actual billing period, not the demo's hardcoded
June 2026 window. The contract compiler should propose the right
dates from the contract text, but this needs manual verification.

**Event types that do not map cleanly.** The engine evaluates
`customer_recontact`, `human_completion`, `downstream_succeeded`,
`downstream_failed`, etc. The normalization layer must map real
Zendesk/Intercom/Stripe events to these canonical types. A Zendesk
"ticket reopened" is a `customer_recontact`. A Stripe "refund.failed"
is a `downstream_failed`. These mappings will be source-specific and
need to be correct — a wrong mapping produces wrong determinations.

**Account IDs and action types that use different conventions.** The
demo's `ACC-001381` and `refund` are synthetic. Real account IDs are
UUIDs or email addresses or Stripe customer IDs. The `account_id` and
`expected_action` fields on claims and the `account_id` and `action`
fields on events must use the same identifiers after normalization, or
the `prohibit_field_mismatch_event` rule (R5) will produce false
disputes.

### 3.2 Reconciliation is synchronous for now

The demo runs `reconcile()` synchronously in a single HTTP request for
10,000 claims. A real pilot invoice may be smaller (hundreds to low
thousands of claims). Do not build async job infrastructure until one
of these is observed:

- Processing exceeds ~20 seconds.
- Invoice volumes regularly exceed what fits in one request.
- Data retrieval depends on slow external APIs (not applicable for
  uploads).
- Partial retries become operationally necessary.

If the first real invoice has 50,000 claims and takes 2 minutes, then
build async. Not before.

---

## Stage 4 — Dispute output and customer review

The existing export endpoints produce everything needed for a dispute:

- `GET /api/reconciliations/current/exports/disputes.csv` — all
  disputed lines with outcome ID, customer ID, intent, status, reason,
  rule ID, amounts.
- `GET /api/reconciliations/current/exports/evidence.json` — full
  evidence package with provenance.
- `GET /api/reconciliations/current/exports/summary.json` — financial
  summary.

### 4.1 What to add for the pilot

**A PDF dispute report.** Finance teams want a PDF they can attach to
an email or put in a shared drive. One page summary (submitted,
payable, disputed, review amounts), then a table of disputed lines
with the reason and decisive evidence for each. This is a reporting
task, not an engine change.

**A reconciliation comparison view.** After the customer reviews
the first reconciliation and provides feedback ("these 12 disputes
are wrong, here is additional evidence"), the operator uploads the
new evidence, reruns reconciliation, and the customer needs to see
what changed. This requires storing the prior reconciliation's
results alongside the new ones.

New table:

```
ReconciliationRunRow
  id: str
  run_number: int
  invoice_upload_id: str (FK → UploadRow)
  started_at: datetime
  completed_at: datetime
  engine_version: str
  rule_program_version: int
  claimed_outcomes: int
  payable_outcomes: int
  disputed_outcomes: int
  needs_review_outcomes: int
  submitted_amount: NUMERIC(12,2)
  confirmed_payable_amount: NUMERIC(12,2)
  recommended_deduction: NUMERIC(12,2)
  needs_review_amount: NUMERIC(12,2)
  supersedes_run_id: str | None
```

Each `OutcomeDeterminationRow` gets a `run_id` foreign key so prior
determinations are preserved, not overwritten. The existing code
currently deletes all determinations before each reconciliation
(`session.execute(delete(OutcomeDeterminationRow))`). This must
change to append-only with a run reference.

---

## Stage 5 — Vendor challenge workflow (manual, no portal)

The feedback is right that the vendor portal is premature. The first
challenge workflow is:

1. Customer exports the dispute package (existing export).
2. Customer emails it to the vendor.
3. Vendor replies with additional evidence (CSV/PDF attachment).
4. Operator uploads the vendor's evidence as a new evidence upload
   with `source_type=vendor_challenge`.
5. Matching pipeline processes the new evidence.
6. Operator reruns reconciliation.
7. Both the original and revised determinations are visible.
8. Customer reviews the diff.

This proves the challenge workflow without building vendor auth,
vendor login, or a vendor UI. It is an email-and-upload workflow.

### Version 2 (if demand proves it)

A secure, time-limited challenge link: the customer generates a URL
that lets a vendor upload evidence for specific disputed claims
without creating a full account. The link expires. The upload is
scoped to the disputed claims only.

### Version 3 (after multiple customers request it)

Full vendor portal with identity, permissions, challenge history,
and integrations.

---

## Stage 6 — Production foundation (after Gate E)

This work begins only after a second reconciliation or paid pilot
proves the product is not a one-off.

### 6.1 Postgres and Alembic

Replace SQLite with Postgres. Add Alembic for migrations. Every model
added before this point gets a migration; every model added after
this point is migration-first.

### 6.2 Organization model

Not just `tenant_id` on every table. The actual entity model:

```
Organization
  id, name, created_at

OrganizationMember
  id, organization_id, user_id, role (admin | operator | viewer)

VendorEngagement
  id, organization_id, vendor_name, created_at
  (A customer org can have multiple AI-agent vendors)

Contract
  id, organization_id, vendor_engagement_id, ...
  (Replaces the current singleton contract)

Invoice
  id, contract_id, ...
  (Scoped to a contract, not global)

EvidenceSource
  id, organization_id, source_type, name, created_at
  (Tracks connected sources per org)
```

Access is based on resource relationships: a user belongs to an
organization, a contract belongs to an organization, evidence
belongs to an organization. A query for "my invoices" filters by
the user's organization, not a global tenant_id column.

### 6.3 Authentication

Pick one: Clerk, WorkOS, or Auth0. Requirements:

- Email/password and Google SSO.
- Organization-scoped sessions.
- Role claims in the JWT (admin, operator, viewer).
- Invite flow for adding team members.

Do not build a separate vendor identity system yet. Vendor
participation (Stage 5) uses scoped links, not logins.

### 6.4 Authorization

API-level middleware that enforces:

- Every request has a valid session/JWT.
- The authenticated user belongs to the organization that owns the
  requested resource.
- Write operations (upload, reconcile, approve rules) require
  admin or operator role.
- Read-only operations (view determinations, download exports)
  require viewer or above.

### 6.5 Monitoring and observability

- Structured logging (JSON to stdout, not print statements).
- Error tracking (Sentry).
- Health checks beyond the current `/api/health` (database
  connectivity, last successful reconciliation time).
- Alerting on failed uploads and failed reconciliations.
- Basic APM (request latency, error rates).

### 6.6 Security hygiene (not formal compliance)

Do now (on the product branch, before Gate F):

- Encrypt secrets in environment / secret manager.
- Use least-privilege database credentials.
- Log access to evidence data.
- Document data retention and deletion procedures.
- Keep dependencies updated.
- Do not store unnecessary PII.
- Sanitize uploaded file names.
- Enforce upload size limits.
- Validate file types before parsing.

Start a formal compliance programme (SOC 2, etc.) only when a
serious customer makes it a procurement requirement, you have a
pilot or LOI, and you can afford the audit.

---

## Success metrics

### Data ingestion

- % of source rows successfully parsed per upload.
- % rejected with readable errors.
- Duplicate detection rate.
- Ingestion latency (seconds per upload).
- % retaining source provenance.

### Identity matching

- Direct match rate (target: ≥80% for a well-instrumented customer).
- Confident secondary match rate.
- Manual review rate.
- False match rate (discovered during customer review).
- Unmatched financial value ($ at stake in unresolved matches).

### Reconciliation

- Deterministic repeatability (same input → same output, always).
- Reconciliation completion time.
- % payable / % disputed / % needs_review.
- Customer-confirmed true disputes (disputes the customer agrees with).
- Overturned dispute rate (disputes the customer disagrees with).
- Dollar value corrected (the money the customer would have overpaid).

### Product validation

- Qualified conversations completed.
- Companies that shared real data.
- Completed pilot reconciliations.
- Pilot-to-paid conversion.
- Monthly reconciled spend (total invoice value processed).
- Recoverable value found (total disputed amount confirmed correct).
- Time saved per invoice vs. the customer's current manual process.

---

## File and module structure on the product branch

```
backend/app/
  domain/             ← UNCHANGED
    engine.py
    models.py
  upload/             ← NEW: file upload + parsing
    __init__.py
    router.py         (FastAPI router for /api/pilot/ endpoints)
    parsers.py        (CSV/JSON/JSONL parsing)
    normalize.py      (source-type field mapping + normalization)
    match.py          (identity matching pipeline)
  contracts/          ← UNCHANGED
    compiler.py
  db/
    models.py         ← EXTENDED (UploadRow, ManualMatchRow, etc.)
    repository.py     ← EXTENDED (upload-path functions)
  api/
    schemas.py        ← EXTENDED (upload request/response models)
  fixtures/           ← KEPT for demo, not used by product path
    demo.py
  ingestion/          ← KEPT for demo, not used by product path
    demo_pipeline.py
  main.py             ← EXTENDED (mount pilot router)
```

The demo path (`/api/demo/*`, fixtures, demo_pipeline) stays intact.
The product path (`/api/pilot/*`, upload, normalize, match) is parallel and
uses a separate pilot database plus an invoice-scoped reconciliation service.
Both paths reuse the deterministic domain engine only.

---

## Pricing hypothesis

Do not decide a pricing model. Instrument the system so these
metrics are measurable per reconciliation:

- Invoice count.
- Outcome/claim count.
- Reconciled spend (total submitted amount).
- Disputed amount.
- Needs-review amount.
- Processing duration.
- Number of evidence sources used.

The first pilot should test willingness to pay informally. Possible
value metrics to explore:

- Monthly platform fee (simplest; $X/month regardless of volume).
- Per invoice reconciled.
- Per outcome reconciled.
- Percentage of verified savings (aligns incentives but complicates
  accounting).
- Annual contract based on reconciled spend.

Finalize after observing 2–3 real customers. Do not distort the data
model around an unvalidated pricing scheme.

---

## Immediate next steps

These are ordered. Do them in this order.

1. **Finish 5 qualified customer conversations.** No code. Confirm
   which evidence sources they actually use, what format their vendor
   invoices arrive in, and whether they can export data.

2. **Obtain one anonymized invoice and one evidence export from a
   willing company.** This may be a CSV email attachment. It does not
   require an integration.

3. **Confirm which evidence sources are required to verify that
   specific invoice.** Do not guess. Ask the customer: "If I could
   look at your Zendesk tickets and your Stripe refunds for this
   period, would that be enough to verify these charges?" The answer
   determines which parser to build first.

4. **Build the invoice CSV upload endpoint and parser** (Stage 1.1,
   1.2) for the exact format the design partner provided.

5. **Build the evidence upload endpoint and parser** for the one or
   two source types the design partner uses.

6. **Run the real data through the existing engine.** See what
   happens. The match rate, the determination distribution, and the
   error cases will be surprising.

7. **Build the identity review workbench** (Stage 2.2) for the
   records that did not match.

8. **Show the payable/disputed/review breakdown to the customer.**
   Ask: "Does this look right? Are these disputed charges real?"

9. **Export a dispute package.** Ask if they would use it.

10. **Ask for a second invoice or a paid pilot.**

11. **Only then:** Postgres, tenancy, auth (Stage 6).

---

## Relationship to the demo

The demo (`main` branch) continues to work exactly as it does today.
It is the YC presentation, the HN landing, the recorded walkthrough.

The product branch preserves the demo routes and adds the pilot
routes alongside them. A deployment can serve both: `/demo` shows
the synthetic demonstration, `/pilot` (or whatever the product routes
become) shows the real data workflow.

In the long term, the demo routes will be removed or moved to a
separate deployment. But not now. The demo is still earning attention
and conversations. It stays.

---

## Risks and hard problems

### Identity matching is the biggest unknown

The demo's 99.75% direct match rate is a best case. Real customers
will have:

- Vendors that use conversation IDs, not outcome IDs, in their
  invoices.
- Support systems that do not tag tickets with the vendor's outcome
  ID.
- Payment systems that use their own transaction IDs.
- Multiple customers with the same name or similar IDs.
- Timezone-shifted timestamps.
- Retroactively corrected records.

The identity review workbench (Stage 2.2) is the mitigation. It
lets an operator fix matches without a code change. But if the
match rate on real data is below ~70%, the product is not viable
as a self-service tool — it becomes a consulting engagement. The
match rate is the single most important metric to watch during
the first pilot.

### The engine's event type vocabulary may not fit

The engine evaluates specific event types: `customer_recontact`,
`human_completion`, `downstream_succeeded`, `downstream_failed`,
`ai_closed`, etc. These were designed around the demo's synthetic
data. Real support and payment systems use different vocabularies.

The normalization layer (Stage 1.3) maps real event types to the
engine's vocabulary. But if a real customer's workflow involves
event types that do not map to any existing category, the engine
may need new rule operations. The existing seven operations
(`validate_evidence_envelope`, `claim_datetime_in_range`,
`prohibit_event_within`, `require_success_event_within`,
`prohibit_field_mismatch_event`, `unique_first_claim_within`) cover
the demo's five dispute categories. A real customer may have dispute
categories that require a seventh operation.

This is not catastrophic — the engine is designed to be extended with
new operations. But it means the engine is not purely untouchable;
it may need careful additions after real data reveals new patterns.

### Contract text may not compile cleanly

The compiler was validated against one contract (the Acme-Nova order
form). A real customer's contract may use language that Gemini does
not map cleanly to the seven supported operations. The human approval
step catches this, but it requires someone who understands both the
contract and the rule schema to review the proposal. For the first
few customers, that person is you.

### Customers may not be able to export their data

Enterprise security teams may restrict data exports. The customer
may need internal approval to share support tickets or payment
records with a third party. This is a sales/access problem, not a
technical one, but it can block the entire pilot timeline. Surface
it early in conversations.
