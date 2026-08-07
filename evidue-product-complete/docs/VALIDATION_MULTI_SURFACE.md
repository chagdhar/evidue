# Multi-Surface Revision Validation

Validated in the review environment on July 27, 2026.

## Independently executed

- `python3 -m pytest -q`
- Result: `41 passed`
- TypeScript syntax parsing for `ProductShell.tsx`, `App.tsx`, and `main.tsx`
- Result: syntax valid

## Updated but not executable in this environment

The following were updated for the new route structure but could not be run because the package registry returned 503 errors and the uploaded source archive excluded `node_modules`:

- TypeScript dependency-aware typecheck
- ESLint
- Vitest
- Vite production build
- Playwright
- Docker build

Run locally before recording:

```bash
./scripts/bootstrap.sh
./scripts/dev-check.sh full
docker build -t evidue-demo .
```

The Playwright golden path now enters through `/demo`, opens the June invoice, runs reconciliation, uses the direct `Review example dispute` action, and verifies the dispute-package download.
