# Evidue — Setup and architecture guide

## What Evidue does

Evidue independently verifies outcome-priced AI-agent vendor invoices against the customer's contract and customer-controlled operational evidence.

```text
Vendor claim → Approved authority → Customer proof → Determination → Financial impact → Commercial action
```

The model proposes structured interpretations of contract language. A human approves the rule set. A deterministic engine evaluates every claim. The model never decides payable dollars.

## Customer-facing surfaces

```text
/             Landing page
/try          Public no-signup proof using synthetic data
/contact      Customer discovery / sales contact
/workspace    Protected product
```

`/try` and `/workspace` are deliberately separate. `/try` is a bounded synthetic proof. `/workspace` is the authenticated product for operator-provided agreements, invoices, evidence, review, settlement, and disputes. The old standalone public demo UI has been removed; its useful inspection depth now lives inline in `/try`.

## Local setup

### Prerequisites

- Python 3.13+
- Node.js 20+
- uv

### Install

```bash
git clone <repo-url> evidue && cd evidue
uv sync --group dev
npm --prefix frontend ci
```

### Environment

```dotenv
EVIDUE_PILOT_TOKEN=<at-least-24-random-characters>
GEMINI_API_KEY=<optional-server-owned-key>
EVIDUE_AGREEMENT_RUNTIME_DUAL_RUN=true
```

Generate a workspace token with `openssl rand -hex 32`.

### Run

```bash
./scripts/dev.sh
```

Open `/try` for the public proof or `/workspace` for the protected product.

### Verify

```bash
./scripts/dev-check.sh fast
./scripts/dev-check.sh full
```

## Protected workspace flow

1. Enter workspace access key.
2. Upload or select the governing agreement bundle.
3. Compile a structured rule proposal.
4. Review and approve an immutable rule version.
5. Upload the vendor invoice.
6. Add customer-side evidence.
7. Resolve identity/matching exceptions.
8. Run deterministic reconciliation.
9. Review contradicted and insufficient-evidence lines.
10. Approve settlement and create the vendor dispute/credit handoff.

The synthetic public-try fixture database and protected workspace database remain isolated.
