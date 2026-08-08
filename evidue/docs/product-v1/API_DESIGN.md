# Finance Product API

All endpoints are protected by the same workspace token boundary as `/api/pilot`.

## Productization

- `POST /api/pilot/product/bootstrap` — idempotently materialize organization/vendor/invoice/review/statement links for existing pilot data.
- `GET /api/pilot/product/overview`
- `GET /api/pilot/product/vendors`
- `GET /api/pilot/product/invoices`

## Review operations

- `GET /api/pilot/product/review-cases`
- `POST /api/pilot/product/review-cases/{id}/assign`
- `POST /api/pilot/product/review-cases/{id}/decision`

## Settlement authority

- `GET /api/pilot/product/reconciliations/{run}/statement`
- `GET /api/pilot/product/reconciliations/{run}/trust`
- `POST /api/pilot/product/reconciliations/{run}/approve`

## Disputes

- `GET /api/pilot/product/disputes`
- `POST /api/pilot/product/reconciliations/{run}/disputes`
- `GET /api/pilot/product/disputes/{id}`
- `POST /api/pilot/product/disputes/{id}/transition`
- `GET /api/pilot/product/disputes/{id}/print.html`
- `GET /api/pilot/product/disputes/{id}/package.pdf`
