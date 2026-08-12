# Public Try Evidue demo

`/try` is the public validation surface intended for Indie Hackers, Hacker News, direct
outreach, and other zero-trust visitors. It is deliberately different from `/workspace`.

## Product goal

A visitor should understand the core value in seconds and reach one real result without
creating an account:

```text
synthetic contract
    -> model rule proposal
    -> explicit visitor approval
    -> deterministic 100-claim reconciliation
    -> billed vs substantiated vs unsupported
    -> inspect a real evidence chain
    -> Talk to us
```

The public trial does not accept uploads or pasted customer data. Acme Commerce and Nova
Support AI are fictional.

## Trust boundary

The public route does not weaken the protected product.

- `/workspace/*` is the authenticated customer UI; its `/api/pilot/*` data boundary remains bearer-token protected and workspace-scoped.
- public contract analysis is ephemeral and does not create an authoritative AIR/rule version.
- the visitor must explicitly approve the proposed demo rules before money is calculated.
- reconciliation runs in memory against the synthetic 100-claim sample.
- `/api/reconciliations` and other shared-state mutation routes remain blocked when
  `EVIDUE_PUBLIC_DEMO=true`.
- public sessions expire after 30 minutes.

## Live compiler budget

When `GEMINI_API_KEY` is configured, `/api/public-demo/try/analyze` attempts one live Gemini
compile per hashed network address per seven-day process window. This is a cost/abuse control,
not an authentication mechanism. If the live compiler is unavailable, unconfigured, rate
limited, or already used from that network, the UI explicitly states that it is replaying the
validated recorded model proposal.

The deterministic reconciliation still runs live in either case. The UI must never label a
recorded replay as a live model call.

## Public API

### Analyze

```http
POST /api/public-demo/try/analyze
```

Returns the exact synthetic contract, compiler mode, diagnostics, proposed rules, source hash,
and an ephemeral `sandbox_id` when the proposal is approval-ready.

### Approve and reconcile

```http
POST /api/public-demo/try/{sandbox_id}/approve-and-reconcile
```

The session must belong to the same network and still be live. The response is the deterministic
100-claim sample result. Current golden output for the bundled fixture is:

- 100 claims
- $150.00 submitted
- 83 substantiated / $124.50
- 17 disputed / $25.50
- 0 needs-review claims

These figures are synthetic test data, not a customer savings claim.

## Validation funnel

Optional PostHog analytics track only anonymous product events. For community links, use:

```text
/try?source=indie_hackers
/try?source=hacker_news
```

Key events:

- `try_evidue_viewed`
- `try_evidue_analyze_started`
- `try_evidue_analyzed`
- `try_evidue_rules_approved`
- `try_evidue_result_seen`
- `try_evidue_talk_clicked`

The useful funnel is not page views. It is:

```text
view -> analyze -> approve -> result -> conversation
```

## Design decisions from early-founder feedback

The page intentionally applies several recurring lessons from public founder feedback:

1. one value proposition above the fold;
2. no signup before value;
3. show the product doing the work instead of describing features;
4. show the financial before/after result clearly;
5. diagnose/justify the result with inspectable rules and evidence;
6. ask for a conversation only after the visitor has seen the result;
7. instrument activation stages so traffic is not confused with validation.
