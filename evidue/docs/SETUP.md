# Evidue — Setup and architecture guide

## What Evidue does

Evidue independently verifies outcome-priced AI-agent vendor invoices
against the customer's contract and their own operational evidence.

```
Contract → deterministic rules → vendor invoice + customer evidence
→ payable / disputed / needs review
```

The LLM compiles contract language into structured rules. A deterministic
engine evaluates every claim. The LLM never touches money.

## Architecture

```
┌──────────────────────────┐    ┌──────────────────────────┐
│   Synthetic demo         │    │   Operator pilot          │
│   /demo routes           │    │   /pilot routes           │
│   Demo SQLite DB         │    │   Pilot SQLite DB         │
│   10k fixtures           │    │   Real customer data      │
│   Public, no auth        │    │   Token-protected         │
└──────────────────────────┘    └──────────────────────────┘
              │                               │
              └───────────┬───────────────────┘
                          │
              ┌───────────▼───────────────┐
              │   Domain engine            │
              │   (deterministic, shared)  │
              │   Decimal money, frozen    │
              │   models, rule programs    │
              └───────────────────────────┘
                          │
              ┌───────────▼───────────────┐
              │   Agreement IR runtime     │
              │   (generic expressions,    │
              │    4-valued logic,          │
              │    dual-run comparison)     │
              └───────────────────────────┘
```

## Local setup

### Prerequisites

- Python 3.13+
- Node.js 20+
- uv (Python package manager)

### Install

```bash
git clone <repo-url> evidue && cd evidue
uv sync --group dev
npm --prefix frontend ci
```

### Environment

Copy `.env.example` to `.env` and set:

```dotenv
# Required for pilot routes:
EVIDUE_PILOT_TOKEN=<at-least-24-random-characters>

# Optional for live contract compilation:
GEMINI_API_KEY=<your-gemini-key>

# Optional for dual-run AIR comparison:
EVIDUE_AGREEMENT_RUNTIME_DUAL_RUN=true
```

Generate a pilot token: `openssl rand -hex 32`

### Run

```bash
# Backend + frontend dev server
./scripts/dev.sh

# Or separately:
uv run uvicorn app.main:app --reload --app-dir backend --port 8000
npm --prefix frontend run dev
```

### Verify

```bash
uv run ruff format --check backend
uv run ruff check backend
PYTHONPATH=backend uv run pytest
npm --prefix frontend run lint
npm --prefix frontend run test
npm --prefix frontend run build
```

## Demo vs Pilot

| | Demo | Pilot |
|---|---|---|
| URL | /demo | /pilot |
| Auth | None | EVIDUE_PILOT_TOKEN |
| Database | data/evidue.db | data/evidue-pilot.db |
| Data | 10k synthetic claims | Real customer data |
| Purpose | Synthetic product demonstration | First design partner |

Demo results are hardcoded fixtures. Pilot results come from uploaded data.
The two databases are completely isolated — clearing one cannot affect the other.

## Pilot workflow

1. Enter pilot token → connect
2. Upload contract text → view extracted text and metadata
3. Compile rules (recorded or live Gemini) → review proposed rules
4. Approve immutable rule version
5. Upload vendor invoice CSV → review accepted/rejected rows
6. Upload customer evidence (CSV/JSON/JSONL) → review parsing
7. Upload optional identity map → run matching
8. Review unmatched events → confirm/reject suggested matches
9. Run deterministic reconciliation → view payable/disputed/review
10. Export dispute package → record customer feedback

## API routes

### Pilot endpoints (all require `Authorization: Bearer <token>`)

**Contract:**
- `POST /api/pilot/contract` — upload contract
- `GET /api/pilot/contracts/{id}` — view contract + compilations
- `POST /api/pilot/contracts/{id}/compile` — compile rules (legacy)
- `POST /api/pilot/contracts/{id}/compile-native` — compile AIR natively
- `POST /api/pilot/compilations/{id}/approve` — approve rule version
- `GET /api/pilot/compilations/{id}/agreement` — view Agreement IR
- `GET /api/pilot/contracts/{id}/conformance` — conformance report

**AIR versions:**
- `GET /api/pilot/air-versions?contract_id=X` — list AIR versions
- `GET /api/pilot/air-versions/{id}` — view AIR version
- `POST /api/pilot/air-versions/{id}/approve` — approve AIR version

**Verification:**
- `POST /api/pilot/compilations/{id}/verification-plan` — generate plan

**Invoice:**
- `POST /api/pilot/invoice` — upload vendor invoice CSV

**Evidence:**
- `POST /api/pilot/evidence` — upload evidence (CSV/JSON/JSONL)
- `POST /api/pilot/identity-map` — upload identity mapping CSV

**Matching:**
- `POST /api/pilot/match` — run identity matching
- `GET /api/pilot/review/unmatched` — list unmatched events
- `GET /api/pilot/review/candidates/{id}` — match candidates
- `POST /api/pilot/review/confirm` — confirm manual match

**Reconciliation:**
- `POST /api/pilot/reconcile` — run reconciliation
- `GET /api/pilot/reconciliation` — get latest or specific run
- `GET /api/pilot/reconciliations/{id}/agreement-comparison` — AIR dual-run
- `GET /api/pilot/reconciliations/{id}/compare/{prior}` — compare runs

**Exports:**
- `GET /api/pilot/reconciliations/{id}/exports/summary.json`
- `GET /api/pilot/reconciliations/{id}/exports/evidence.json`
- `GET /api/pilot/reconciliations/{id}/exports/disputes.csv`

**Customer validation:**
- `POST /api/pilot/reconciliations/{id}/customer-review`
- `GET /api/pilot/reconciliations/{id}/customer-review`

**Admin:**
- `GET /api/pilot/status` — pilot state
- `POST /api/pilot/clear` — clear all pilot data

## Agreement IR pipeline

The repository supports two compilation paths:

### Legacy path (current production default)
```
Contract text → Gemini → CompilationProposal → RuleProgram
→ legacy engine (financial authority)
→ optional: translate to AIR → dual-run comparison
```

### Native AIR path (new, for testing)
```
Contract text → AgreementCompilationProposal → deterministic lowerer
→ AgreementIR → persisted version → approval → dual-run
```

The native path uses `compiler_models.py` for the LLM proposal schema
and `agreements/compiler.py` for deterministic lowering. The LLM
proposes semantic structure (condition types, norm types); the lowerer
builds Expression trees. The LLM never sees expression operators.

### Dual-run mode

Set `EVIDUE_AGREEMENT_RUNTIME_DUAL_RUN=true` to run both engines on
every reconciliation. The legacy result is returned. The comparison
is persisted and viewable via the agreement-comparison endpoint.

## Security limitations

The pilot uses a shared operator token, not user-level auth. This is
appropriate for an operator-assisted pilot with one customer. It is
NOT appropriate for multi-tenant production. Production auth (Clerk,
WorkOS, or similar) is a separate milestone.

## Known limitations

- No native AIR Gemini prompt yet (the lowerer works, but the LLM prompt
  to generate AgreementCompilationProposal is not implemented — proposals
  must be hand-built or generated externally)
- Single-tenant pilot (one customer at a time)
- No automated connector integrations (CSV/JSON upload only)
- No semantic fact extraction (model-assisted evidence analysis)
- No evidence graph persistence
- No formal compliance certification
- No vendor portal
