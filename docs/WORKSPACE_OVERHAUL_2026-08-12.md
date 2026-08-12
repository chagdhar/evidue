# Customer Workspace Overhaul — 2026-08-12

## Goal

Present Evidue as one customer product rather than a collection of demo, pilot, and finance applications. The public `/try` experience remains synthetic and no-login; real customer work happens inside one authenticated workspace.

## Canonical UI routes

| Route | Purpose |
| --- | --- |
| `/workspace` | Contract → invoice → evidence → deterministic reconciliation → export |
| `/workspace/review` | Evidence gaps, approval work, vendor action, and ready-to-settle decisions |
| `/workspace/invoices` | Searchable invoice register and current invoice case |
| `/workspace/vendors` | Vendor spend, exception, contract, and review history |
| `/workspace/settings` | Workspace defaults and integration readiness |
| `/try` | Public synthetic no-login trial; never customer data |
| `/demo/*` | Deep synthetic reference workspace used for product inspection |

Legacy `/pilot`, `/pilot/config`, `/pilot/finance`, and `/pilot/operations` UI paths redirect to the canonical workspace routes. The protected backend API remains `/api/pilot/*` for compatibility; changing the UI route does not weaken the existing workspace-token boundary.

## Product information architecture

The routine reconciliation path exposes five finance-facing stages:

1. **Contract rules** — upload governing terms, review the model proposal, approve the version that can affect money.
2. **Invoice** — preview and confirm vendor control totals before import.
3. **Evidence** — satisfy contract-driven proof requirements from customer-controlled systems.
4. **Reconcile** — run deterministic adjudication and resolve protected Needs Review cases.
5. **Export & action** — move supported payable, disputes, and evidence packages into AP/vendor workflows.

Technical AIR hashes, compiler assurance, semantic facts, and audit history remain available under Advanced rather than being part of the normal finance path.

## Shared workspace shell

`WorkspaceShell.tsx` is the common authenticated chrome for reconciliation, operations, and settings. It provides:

- one Evidue identity and workspace indicator;
- persistent Reconciliation / Finance operations / Settings navigation;
- consistent refresh and sign-out controls;
- one dark financial-control visual system;
- no separate Finance Operations application header.

The finance operations surface therefore becomes a continuation of reconciliation rather than a separate product.

## Public/private boundary

Public UI must never expose a founder personal email address. `/contact` submits to the configured private contact-sheet backend. An optional `EVIDUE_TALK_BOOKING_URL` may be shown as a scheduling action, but only when it is a valid HTTPS URL.

`scripts/check-public-privacy.py` scans public frontend source and built assets. `dev-check.sh` runs it both before and after the frontend build. The release gate fails on:

- `Email Dharun`;
- any public `mailto:` fallback;
- direct public contact-email constants;
- common personal-webmail addresses embedded in frontend source.

This makes the privacy requirement an executable release invariant rather than a manual convention.

## Trust model unchanged

The visual/route overhaul does not change Evidue's authority model:

`contract → model proposes structured rules → human approval/version → deterministic engine → financial result`

The model does not adjudicate invoice lines. Missing proof continues to fail closed into Needs Review rather than being silently treated as payable or disputed.
