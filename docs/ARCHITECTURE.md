# Architecture

## Boundaries

Evidue is a single deployable application with deliberately separated concerns:

- `backend/app/domain/` contains immutable domain entities and the pure,
  deterministic reconciliation engine. It imports neither FastAPI nor
  SQLAlchemy.
- `backend/app/fixtures/` generates the same claims, conversations, and
  provenance-bearing operational events on every run.
- `backend/app/db/` defines SQLAlchemy 2.x persistence entities and repositories.
  Inputs and determinations are separate tables.
- `backend/app/api/` contains Pydantic response contracts.
- `backend/app/main.py` owns HTTP transport and production asset serving.
- `frontend/src/` owns presentation and calls the HTTP API. It performs no
  financial calculations.
- `e2e/` exercises the real backend and frontend together.

## Reconciliation lifecycle

Reset deletes and regenerates the deterministic input dataset but creates no
determinations. The initial `/demo` screen therefore shows a submitted invoice,
contract rules, and evidence sources without implying that reconciliation has
already happened.

`POST /api/reconciliations` loads persisted claims and events, converts them to
domain objects, evaluates each claim, and stores:

- reconciliation identity and engine version;
- status, reason, applied contract rule, billed amount, and payable amount;
- references from every determination to the operational events it considered.

Aggregates and exports query stored determinations. The route and frontend do not
contain the headline payable totals.

## Deterministic rule ordering

The engine evaluates minimum identifiers, contradictory evidence, billing
period, recontact, human completion, downstream completion, duplicate
attribution, and account/action match in a fixed order. The synthetic headline
fixture is mutually exclusive, so each disputed line has exactly one financial
reason. Missing or contradictory evidence becomes `needs_review` and is not an
automatic deduction.

## Money

Domain and persistence amounts use Python `Decimal` and SQL `NUMERIC(12, 2)`.
JSON serializes money as fixed two-decimal strings. React formats those strings
for display but never adds, subtracts, or determines payability.
