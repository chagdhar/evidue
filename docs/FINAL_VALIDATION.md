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
- Pytest: 39 passed.
- ESLint: passed.
- Vitest: 2 files, 7 tests passed.
- TypeScript and Vite 8.1.5 production build: passed.
- Playwright: complete golden demo path passed against live FastAPI and Vite
  servers.

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

## Docker

Command:

```text
docker build -t evidue-demo .
```

Result: passed. Image ID:
`5b6a57aa0b34799977653ca6a607de850e052574295b9cd204eb1b86f1b5a777`.

The image was run as `evidue-duplicate-validation` on local port 18080. The
following checks passed:

- `GET /api/health` returned `{"status":"ok"}`.
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
- Docker reported `running healthy`.

The disposable validation container was removed afterward.

## Clean checkout

A `--no-local` clone of commit `1d66d6eca39ceabf9e61ad284dfeb56dac402f84`
was created under `/tmp`. Commands:

```text
./scripts/bootstrap.sh
./scripts/seed-demo.sh
./scripts/dev-check.sh full
git status --short
```

Results:

- bootstrap completed with uv-managed Python 3.13.14, `npm ci`, and Chromium;
- deterministic seed created 10,000 claims in unreconciled state;
- full validation passed: 39 pytest tests, 7 Vitest tests, production build,
  and Playwright golden path;
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
