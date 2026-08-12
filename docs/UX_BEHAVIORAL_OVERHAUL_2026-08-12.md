# Evidue UX behavioral overhaul — 2026-08-12

## Goal

Make Evidue feel like a trustworthy finance control product rather than an AI demo. The interface should reduce uncertainty, show progress toward a defensible payment decision, and keep the user focused on one next control at a time.

## Interaction principles

1. **Value before complexity** — lead with the financial decision or the next action, not architecture.
2. **Progressive disclosure** — show advanced traceability only after the user asks for it; contact questions adapt to intent.
3. **Visible progress** — make completion and payment readiness legible so users know what remains.
4. **One recommended next action** — every incomplete state should point to the next control required to move forward.
5. **Loss prevention, not fear** — frame Needs review as money protected from an unsupported decision.
6. **Trust through boundaries** — repeat the authority model at moments where AI involvement could be misunderstood: AI proposes, humans approve, deterministic code decides dollars.
7. **Specific, reversible actions** — labels should describe the consequence (Review contract rules, Import invoice, Export & action) rather than vague verbs.
8. **Calm visual hierarchy** — restrained surfaces, limited accent color, consistent spacing, and finance-grade typography replace decorative gradients and neon.
9. **Preserve context** — workspace identity and current section stay visible while the user works.
10. **No dark patterns** — no fake urgency, scarcity, pre-checked marketing consent, hidden costs, or deceptive defaults.

## Public contact flow

- Route changes restore scroll position to the top.
- Visitors choose an intent first.
- Only intent-relevant questions appear.
- Generic product feedback does not require identity.
- Billing/verification conversations collect the minimum qualification gates needed to assess fit.
- Submission language emphasizes useful criticism over praise.
- Sensitive customer data is explicitly excluded.

## Private workspace

- Persistent left rail on desktop; compact horizontal navigation on smaller screens.
- Workspace identity and privacy state remain visible.
- Reconciliation, finance operations, and settings are presented as one product.
- The reconciliation stage rail communicates payment readiness and completion.
- The command header shows the financial payoff when available.
- The recommended-next-step card turns the workflow into a sequence of controls rather than a collection of features.
- Finance operations focuses on exception exposure, settlement authority, and vendor action.

## Regression expectations

- Navigating to `/contact` from another route restores scroll to the top.
- Legacy `/pilot/*` routes redirect into `/workspace*`.
- Workspace navigation remains within the customer workspace.
- Public privacy checks continue to reject personal email markers and public `mailto:` links.
