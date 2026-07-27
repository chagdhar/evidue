# Demo UX release notes

## Overview

The Overview is now the finance control center for the June invoice. It shows:

- the submitted amount, claim count, billing period, unit price, and approved rule count;
- collection volume and evidence coverage;
- identity-resolution status, including secondary-key joins;
- the pending or completed payable decision;
- the four-stage path from invoice receipt to payable determination;
- the seven controls or confirmed deduction categories;
- a traceable OUT-004821 example;
- the separation between Evidue Prove, the Outcome Ledger, and Evidue Verify.

The primary actions are functional:

- **Inspect example evidence** opens the Payment processor raw-record inspector.
- **Run June reconciliation** runs the deterministic customer-side evaluation.
- **Open full decision** opens Customer Verify after the result is available.

## Source inspector

The previous inline selection behavior was replaced with an explicit right-side modal inspector. Every Inspect action now:

1. opens the inspector, including when the source is already selected;
2. shows a loading state while the source request runs;
3. shows an actionable error if the request fails;
4. displays the source authority, production collection method, and cadence;
5. compares the original payload with the canonical Evidue record;
6. explains match method, confidence, schema version, receipt time, and payload hash;
7. cancels stale responses logically so rapid source changes cannot overwrite the latest selection.

## Regression coverage

The browser suite now verifies:

- the redesigned Overview and its direct reconciliation action;
- Overview → example evidence → inspector;
- direct URL opening of the inspector;
- closing and reopening an already-selected source;
- switching from Payment processor to Vendor claim manifest without stale data;
- the full customer financial-decision path;
- focused edge-case scenarios;
- the two-sided Prove → Outcome Ledger → Verify product story.

Stable test IDs and accessible metric labels are used for key surfaces to avoid strict-mode collisions caused by legitimate repeated copy.
