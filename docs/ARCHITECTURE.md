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

Reset accepts a scenario ID from a fixed domain fixture catalog. The active
scenario is persisted in the single demo-state row and exposed with its name,
description, and highlighted outcome ID. Scenario metadata contains no
financial results. Claims, events, determinations, summaries, exports, and UI
values all follow the same lifecycle regardless of fixture size:

- `headline` is the complete 10,000-line, five-category invoice;
- `evidence_review` isolates contradictory directly matched evidence;
- `recovery` proves that a failed first claim does not suppress a valid
  follow-up;
- `duplicate_window` shows one deterministic winner and two later R4
  duplicates.

Changing the scenario regenerates inputs and clears the current
reconciliation. A user must run reconciliation again before any determination
or corrected amount is shown.

`POST /api/reconciliations` loads persisted claims and events, converts them to
domain objects, attributes evidence, provisionally evaluates every claim
without R4, builds duplicate context from only the provisional payable results,
applies R4 in a second pass, and stores:

- reconciliation identity and engine version;
- status, reason, applied contract rule, billed amount, confirmed payable
  amount, confirmed disputed amount, and needs-review amount;
- references only to the operational events used by the decisive rule;
- the winning outcome ID for a contextual duplicate determination.

Aggregates and exports query stored determinations. The route and frontend do not
contain the headline payable totals.

## Evidence attribution

Before applying a billing rule, the domain engine classifies evidence as
`directly_matched`, `requires_review`, `unrelated`, or `contradictory`.

A direct match requires the event's customer ID and outcome ID to equal the
claim. Account-sensitive downstream events must also match the claim account,
and action-sensitive events must match the expected action. Missing outcome
identifiers and duplicate source records require review. Events associated with
another customer, outcome, account, or action are unrelated and cannot make a
claim payable or disputed. Conflicting directly matched terminal events are
contradictory and require review.

This attribution result is a domain value, independent of persistence and HTTP
transport. Determinations retain only the directly matched evidence actually
used by their decisive rule. A completion-window deadline is calculated from
the contract and claim close time; it is exposed separately as a computed
timeline marker and is never represented as imported customer-owned evidence.

## Deterministic rule ordering

The first pass evaluates minimum identifiers and contradictory evidence (R7),
billing period (R6), recontact (R1), human completion (R2), downstream
completion (R3), and account/action match (R5). The second pass applies
duplicate attribution (R4) only to claims whose provisional result is payable.
The synthetic headline fixture is mutually exclusive, so each disputed line has
exactly one financial reason. Missing or contradictory evidence becomes
`needs_review` and is not an automatic deduction.

Duplicate detection is based on reconciliation context, not an evidence label.
Provisionally payable claims with the same customer ID and normalized intent are
ordered by `closed_at`, then lexicographically by outcome ID. The earliest
otherwise-payable claim is the deterministic winner; later otherwise-payable
claims closed within 24 hours are duplicates of that winner. A disputed or
needs-review result from the first pass is excluded and cannot become a winner
or an R4 duplicate. The determination references the winner and duplicate
outcome IDs and their closing evidence. A directly matched
`duplicate_attribution` event can corroborate the conclusion but cannot create
it.

## Money

Domain and persistence amounts use Python `Decimal` and SQL `NUMERIC(12, 2)`.
JSON serializes money as fixed two-decimal strings. React formats those strings
for display but never adds, subtracts, or determines payability.

Every stored determination has three mutually exclusive financial buckets:

- payable: confirmed payable equals billed; disputed and review are zero;
- disputed: confirmed disputed equals billed; payable and review are zero;
- needs review: review equals billed; payable and disputed are zero.

The summary preserves the identity `submitted = confirmed payable + confirmed
disputed + needs review`. `recommended_deduction` is the sum of confirmed
disputed amounts only.
