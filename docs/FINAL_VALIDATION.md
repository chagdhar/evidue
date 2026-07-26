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
- Pytest: 19 passed.
- ESLint: passed.
- Vitest: 2 files, 6 tests passed.
- TypeScript and Vite 8.1.5 production build: passed.
- Playwright: complete golden demo path passed against live FastAPI and Vite
  servers.

## Deterministic result

The domain, API, Playwright, and container checks agreed on:

- 10,000 claimed outcomes
- $15,000.00 submitted amount
- 8,320 payable outcomes
- 1,680 disputed outcomes
- $12,480.00 corrected payable amount
- $2,520.00 recommended deduction
- R1 recontacts: 720 / $1,080.00
- R2 human completions or corrections: 360 / $540.00
- R3 failed downstream actions: 300 / $450.00
- R4 duplicate charges: 180 / $270.00
- R5 account or action mismatches: 120 / $180.00

## Docker

Command:

```text
docker build -t evidue-demo .
```

Result: passed. Image ID: `6c7d15bf97c2`.

The image was run as `evidue-final-validation` on local port 18080. The
following checks passed:

- `GET /api/health` returned `{"status":"ok"}`.
- `POST /api/reconciliations` returned the exact deterministic result above.
- `GET /api/reconciliations/current/exports/summary.json` matched it exactly.
- `GET /demo` returned HTTP 200 and the production React root document.
- Docker reported `running healthy`.

The disposable validation container was removed afterward.

## Clean checkout

A `--no-local` clone of commit `583611772c26a1a0985b4ff162af5b93fe520096`
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
- full validation passed: 19 pytest tests, 6 Vitest tests, production build,
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

`npm audit` reports one React Router RSC-mode advisory through
`react-router-dom`. This application uses only client-side declarative
`BrowserRouter`, serves static assets, and implements no React Server
Components, actions, or server-side rendering. No currently published router
version in the audit database avoids all overlapping advisories; the exposure
is not reachable in this architecture.
