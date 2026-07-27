# Final validation

All results below were produced on 2026-07-27. None are inferred.

## Repository-wide validation

Command:

```text
./scripts/dev-check.sh full
```

Result: passed.

- Ruff formatting: 14 files already formatted.
- Ruff lint: passed.
- Pytest: 41 passed.
- ESLint: passed.
- Vitest: 2 files, 18 tests passed.
- TypeScript and Vite 8.1.5 production build: passed.
- Playwright: 2 tests passed against live FastAPI and Vite servers: the complete
  headline financial-decision path and the focused multi-scenario path.

## Deterministic result

The domain, API, Playwright, and container checks agreed on:

- 10,000 claimed outcomes
- $15,000.00 submitted amount
- 8,320 payable outcomes
- 1,680 disputed outcomes
- 0 needs-review outcomes
- $12,480.00 corrected payable amount
- $2,520.00 recommended deduction
- $0.00 needs-review amount
- R1 recontacts: 720 / $1,080.00
- R2 human completions or corrections: 360 / $540.00
- R3 failed downstream actions: 300 / $450.00
- R4 duplicate charges: 180 / $270.00
- R5 account or action mismatches: 120 / $180.00

The separate ambiguous-evidence domain regression produced `needs_review` with
$0.00 confirmed payable, $0.00 confirmed disputed/recommended deduction, and
$1.50 needs-review amount.

## Selectable synthetic data sets

The API, frontend, Playwright, and production container agreed on four
deterministic scenarios:

- `headline`: 10,000 claims; $15,000.00 submitted; 8,320 payable; 1,680
  disputed; $12,480.00 payable; $2,520.00 deduction; $0.00 review.
- `evidence_review`: 2 claims; $3.00 submitted; 1 payable; 1 needs review;
  $1.50 payable; $0.00 deduction; $1.50 review. `CASE-REVIEW-001` references
  only its contradictory success and failure evidence.
- `recovery`: 2 claims; $3.00 submitted; the failed first claim is R3 and the
  valid follow-up is payable; $1.50 payable and $1.50 deduction.
- `duplicate_window`: 3 otherwise-payable claims; $4.50 submitted; the earliest
  remains payable and the later two are R4; $1.50 payable and $3.00 deduction.
  `CASE-DUP-002` references `CASE-DUP-001` as its winner.

Changing data sets cleared the current reconciliation and restored an honest
ready state. Scenario metadata exposed no computed money. The headline
reconciliation ID remained `REC-2026-06-001`.

## Financial-correctness regressions

Domain and API tests verify:

- same-intent evidence from another customer is unrelated;
- same-customer evidence for another outcome is unrelated;
- reuse of an outcome ID by the wrong customer is unrelated;
- correct action/wrong account and correct account/wrong action are unrelated;
- an event without an outcome ID requires review;
- duplicate source evidence requires review;
- contradictory directly matched events require review;
- unrelated evidence cannot make a claim payable or disputed;
- `needs_review` money never increases the recommended deduction;
- duplicate status requires claim comparison by customer, normalized intent,
  close time, and the 24-hour window;
- a failed R3 claim followed by a valid claim leaves the valid claim payable;
- a needs-review claim followed by a valid claim leaves the valid claim payable;
- an out-of-period R6 claim followed by a valid in-period claim leaves the
  valid claim payable;
- two otherwise-payable claims within 24 hours produce one payable winner and
  one R4 duplicate;
- three otherwise-payable claims in one window produce one payable winner and
  two R4 duplicates;
- otherwise-payable claims more than 24 hours apart both remain payable;
- equal closure timestamps are deterministically ordered by outcome ID;
- a duplicate label alone cannot create a duplicate;
- each determination exposes only decisive evidence;
- completion-window expiry is a computed marker, not imported evidence.

## Interface regressions

Frontend and Playwright tests verify:

- the pre-reconciliation screen shows only submitted invoice data and a ready
  action;
- both required synthetic-data disclosures remain visible;
- the corrected payable amount is the dominant financial value;
- the subtraction bridge uses API summary totals and category values;
- claims default to server-filtered disputed outcomes;
- selecting a finding applies its rule filter to the claims request;
- OUT-004821 is visibly marked as the demo example;
- the evidence inspector presents vendor claim, contract obligation,
  determination, readable timeline labels, source systems, and source records;
- all clause-to-executable-rule mappings remain accessible;
- the primary dispute-package action calls the evidence export and confirms the
  disputed count and amount;
- needs-review money remains visually separate from the confirmed deduction;
- the selector is populated by the scenario API and switching performs a real
  reset before displaying any new financial result;
- `/demo` contains no selector and restores `headline` if a lab scenario was
  previously active; `/demo/lab` is the only selector-bearing route;
- a review-only scenario defaults claims to `needs_review`, displays no
  confirmed deductions, and includes review money in the bridge;
- the live browser exercises all four scenarios and their highlighted outcomes;
- desktop and narrow-width layouts were visually inspected with the live API.

## Docker

Command:

```text
docker build -t evidue-demo .
```

Result: passed. Image ID:
`8ee28831bfe0e5e2129f6c89d002dc72a0381b5f3162e32d649f56aefa03f54b`.

The image was run as `evidue-scenarios-validation` on local port 18080. The
following checks passed:

- `GET /api/health` returned `{"status":"ok"}`.
- `GET /api/demo/scenarios` returned the four expected scenario IDs.
- `POST /api/demo/reset` returned 10,000 seeded claims and
  `"reconciled":false`.
- `POST /api/reconciliations` returned the exact deterministic result above.
- The R4 category contained exactly 180 outcomes / $270.00.
- `GET /api/contracts/current` stated that R4 applies after R1, R2, R3, R5,
  R6, and R7 and only among otherwise-payable claims.
- `GET /api/reconciliations/current/outcomes/OUT-001381` returned R4, winning
  outcome `OUT-001081`, and evidence references for both outcome closures.
- `GET /api/reconciliations/current` and the summary export agreed.
- `GET /api/reconciliations/current/outcomes/OUT-004821` returned disputed R3,
  $1.50 confirmed disputed, and only `ai_closed`, `downstream_failed`, and late
  `human_refund_completed` source evidence. The two-hour expiry appeared only
  in `computed_timeline_markers`.
- The dispute CSV contained its header plus 1,680 rows and all three explicit
  financial columns.
- The evidence JSON contained 1,680 dispute packages, including the precise
  OUT-004821 evidence above.
- `GET /api/reconciliations/current/exports/summary.json` matched it exactly.
- `GET /demo` returned HTTP 200 and the production React root document.
- Every focused scenario was reset and reconciled inside the container; its
  exact financial buckets and highlighted determination matched the domain and
  API regressions.
- The production UI showed the honest ready state, completed reconciliation,
  displayed `$12,480.00` as the dominant payable amount, defaulted to 1,680
  disputed outcomes, exposed the dispute-package action, and retained the
  synthetic-data disclosure.
- Docker reported `running healthy`.

The disposable validation container was removed afterward.

## Clean checkout

A `--no-local` clone of commit `041b08a`
was created under `/tmp`. Commands:

```text
./scripts/bootstrap.sh
./scripts/seed-demo.sh evidence_review
./scripts/demo-reset.sh headline
./scripts/dev-check.sh full
git status --short
```

Results:

- bootstrap completed with uv-managed Python 3.13.14, `npm ci`, and Chromium;
- the argument-aware seed created the 2-claim review scenario, then reset
  restored the 10,000-claim headline scenario in unreconciled state;
- full validation passed: 41 pytest tests, 18 Vitest tests, production build,
  headline Playwright path, and focused multi-scenario Playwright path;
- `git status --short` produced no output;
- the temporary checkout was removed afterward.

## Adversarial review

Repository searches found no float construction, random fixture generation,
frontend headline totals, secrets, TODO/FIXME markers, dependency directories,
runtime databases, Python bytecode, or build output committed. Category amounts
were changed during review to sum persisted disputed determinations rather than
multiply a category count by a price constant. Bootstrap was changed from
`npm install` to `npm ci` after the first isolated clone changed its lockfile.

`npm audit` reports two high-severity package entries (`react-router-dom` and
its transitive `react-router`) for one React Router RSC-mode advisory. This
application uses only client-side declarative `BrowserRouter`, serves static
assets, and implements no React Server Components, actions, or server-side
rendering, so the affected RSC action path is not used in this architecture.

## Recording-surface cleanup validation

On 2026-07-27, after separating `/demo` from `/demo/lab`, removing generated
TypeScript metadata, and refining the dispute handoff, the sandbox-safe command
`./scripts/dev-check.sh fast` passed:

- Ruff format and lint passed;
- 41 Pytest tests passed;
- ESLint passed;
- 20 Vitest tests passed;
- TypeScript and the Vite production build passed.

The new regressions verify that the primary demo resets a previously active lab
scenario to `headline`, hides the selector, returns to an unreconciled state,
and presents the vendor-dispute readiness copy. The Playwright source now
starts the golden path from `evidence_review` and requires `/demo` to restore
the 10,000-line headline fixture; focused scenarios run at `/demo/lab`.

A repeat of the live Playwright, Docker, and isolated-checkout commands was
requested but not executed in this environment because its execution-approval
quota was exhausted. The last successfully reproduced full, Docker, and
isolated-checkout results remain documented above; this section does not claim
that those commands were rerun after the recording-surface cleanup.

## Two-sided product extension validation

Validation performed on the archive in this environment:

- `python -m pytest -q` — **41 passed**.
- TypeScript parser validation using the installed TypeScript compiler for `ProductShell.tsx`, `main.tsx`, and the extended Playwright specification — **syntax passed**.
- Production React search for hardcoded headline currency strings — none found outside tests.
- Backend SPA route handlers updated for `/demo/vendor-preflight` and `/demo/outcome-ledger`.

Not independently rerun in this environment because frontend dependencies could not be installed from the package registry:

- ESLint
- Vitest
- dependency-aware TypeScript build
- Vite production build
- Playwright browser execution
- Docker build

Run `./scripts/dev-check.sh full` and the Docker verification locally before recording or submission.
