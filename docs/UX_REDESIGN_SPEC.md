# Evidue UX Redesign Specification

**Version:** 1.0  
**Objective:** Remove the “vibe-coded dashboard” appearance and make Evidue feel like an audit-grade financial control product.

---

## 1. Current-state audit

The current application has strong functionality, but the presentation exposes implementation history rather than a coherent product model.

### Primary issues

1. **Two visual systems coexist.** `ProductShell.tsx` and `App.tsx` use overlapping but different page structures, typography scales, cards, and CSS conventions.
2. **Navigation mirrors the codebase.** Overview, reconciliation, vendor preflight, invoices, disputes, contracts, outcome ledger, data sources, and scenario lab all receive equal weight.
3. **Too many cards.** Most information is placed inside bordered cards, reducing hierarchy and making the app resemble a generated admin template.
4. **The product story is split.** Buyer reconciliation and vendor preflight appear as peer products, weakening Evidue's initial positioning.
5. **The overview is a dashboard, not a decision brief.** It repeats metrics and educational surfaces before the financial result.
6. **Detail uses large dialogs.** Evidence inspection should preserve list context in a right-side drawer.
7. **Typography is inconsistent.** The application combines marketing-sized headings, dashboard cards, dense tables, and technical copy without a consistent information hierarchy.
8. **Demo-only surfaces are prominent.** Scenario Lab, illustrative invoice history, and technical infrastructure make the app feel staged.
9. **Semantic color is over-distributed.** Accent, success, warning, and error treatments are used in cards and chips beyond the minimum required financial states.
10. **Repeated explanatory alerts create visual noise.** Critical disclosures compete with ordinary guidance.

### What must remain

- Exact financial totals from the backend.
- Contract → proposed rules → approval → deterministic execution boundary.
- Synthetic-data disclosure.
- Detailed `OUT-004821` evidence.
- Evidence provenance.
- Export functionality.
- Public-demo read-only safeguards.
- Existing domain and API behavior.

---

## 2. Target product model

Evidue should feel like a single invoice case file with four views:

1. **Decision** — what should be paid.
2. **Findings** — which claims changed the amount and why.
3. **Contract rules** — which approved rules governed the decision.
4. **Evidence** — which records and audit events support it.

This model is clearer than the current mix of dashboards, infrastructure pages, labs, and separate dispute-package surfaces.

---

## 3. Target information architecture

### Primary navigation

| Label | Route | Purpose |
|---|---|---|
| Decision | `/demo` | Executive invoice decision brief |
| Findings | `/demo/invoices/current` | Reconciliation workspace, claims, and dispute details |
| Contract rules | `/demo/contracts/current` | Contract document, rule proposal, approval/version history |
| Evidence | `/demo/evidence` | Source readiness, outcome ledger, and audit trail |

### Secondary/technical navigation

Accessible through a single “Technical” menu or local-only route:

- Scenario Lab
- Vendor Preflight
- raw data-source samples
- developer architecture details
- illustrative invoice history

### Route consolidation

- Merge `/demo/disputes/current` into Findings as an export/action tab.
- Merge Outcome Ledger and Data Sources into Evidence tabs.
- Remove “Invoices” from public navigation until real multi-invoice history exists.
- Keep old routes as redirects during migration.

---

## 4. Screen specifications

## 4.1 Decision page

### User question

> What should we pay, and what requires attention?

### Header

- Customer and vendor.
- Invoice ID and billing period.
- Status: Decision ready.
- Public-demo/synthetic badges in a compact context line.

### Primary decision block

Dominant:

- Corrected payable amount: `$12,480.00`.

Supporting:

- Submitted: `$15,000.00`.
- Recommended deduction: `$2,520.00`.
- Needs review: `$0.00`.

Actions:

- Primary: `Review findings`.
- Secondary: `Export dispute package`.

### Supporting content

1. Flat metric strip: claims, payable, disputed, evidence coverage.
2. “Why this changed” list with five rule categories.
3. Compact trust boundary.
4. Compact evidence-source readiness.
5. Contact CTA.

### Remove from this page

- large generic workflow cards;
- repeated product education;
- source cards;
- scenario controls;
- multiple equal-weight CTA buttons;
- charts with no decision value.

---

## 4.2 Findings workspace

### User question

> Which billed outcomes should be paid, disputed, or reviewed?

### Layout

- Sticky invoice decision strip at top.
- Tabs: `Findings`, `All claims`, `Exports`.
- Findings view uses a five-row structured list.
- All claims uses a dense data table.
- Row selection opens the Evidence Drawer.

### Table columns

Default:

1. Outcome ID
2. Customer / intent
3. Vendor claim
4. Determination
5. Rule
6. Evidence state
7. Amount
8. Closed at

Hide low-value technical columns behind column settings or the drawer.

### Filter toolbar

- Search outcome ID/customer/intent.
- Determination.
- Rule.
- Evidence state.
- Clear filters.

### Deep link

`?outcome=OUT-004821` opens the Evidence Drawer.

---

## 4.3 Evidence Drawer

### User question

> Can I defend this exact financial determination?

### Header

- Outcome ID.
- Determination badge.
- Amount charged and amount payable.
- Reason code.

### Sections

1. **Vendor claim** — what the vendor says occurred.
2. **Contract condition** — exact approved clause/rule.
3. **Evaluation** — operation, parameters, evaluated inputs, result.
4. **Evidence timeline** — customer and vendor events in time order.
5. **Provenance** — source system, record ID, authority, direct/derived/computed.
6. **Financial effect** — charged, payable, deduction.

### Footer actions

- Open raw evidence.
- Copy outcome ID.
- Export evidence JSON.

Do not place approval or mutation actions in this drawer.

---

## 4.4 Contract rules workbench

### User question

> What interpretation of the contract governs payment?

### Header

- Contract name.
- Active version.
- Approved timestamp.
- Compiler/model identifier.
- Source hash.
- Status badge.

### Main layout

Desktop split view:

- Left 42%: contract document.
- Right 58%: proposed/approved rule list.

A selected rule highlights its source clause and vice versa.

### Top tabs

- Active rules
- Pending proposal
- Version history

### Rule presentation

Each rule uses a flat expandable row:

- ID and title.
- Consequence.
- Source clause.
- Operation.
- Parameters.
- Evidence required.
- Validation status.
- Difference from active version.

Raw JSON is secondary and collapsed.

### Public demo

- Read-only banner at top.
- No active-looking mutation buttons.
- Recorded Gemini disclosure.
- Trust-boundary statement.

### Local/normal mode

- Compile action in toolbar.
- Approval action in sticky bottom bar.
- Confirmation dialog before approval.

---

## 4.5 Evidence page

### User question

> Which systems and records support this invoice decision?

### Tabs

1. Sources
2. Outcome ledger
3. Audit log

### Sources

Use a table, not a grid of cards:

- source;
- authority;
- record count;
- time coverage;
- identity coverage;
- last ingestion/batch;
- status.

Selecting a source opens a side drawer with sample records and schema.

### Outcome ledger

Use a searchable table of proof envelopes. Do not present every proof envelope as a card.

### Audit log

Chronological stacked list with filters for compilation, approval, reconciliation, and export events.

---

## 5. Interaction rules

### One primary action

Every page gets one visually dominant action. Secondary actions are text or outlined buttons.

### Details without navigation loss

Use right-side drawers for claim, source, and audit-event detail. Preserve filters and scroll position.

### Confirmation

Use dialogs only for:

- approving a rule version;
- resetting/reseeding locally;
- destructive changes.

### Progressive disclosure

Default view shows plain-language financial meaning. Operation names, parameters, JSON, hashes, and raw records are available one level deeper.

### Loading

- Preserve the page skeleton.
- Name the operation: “Loading invoice decision,” “Loading evidence,” etc.
- Never show an indefinite spinner without context.

### Errors

Every error states:

- what failed;
- what data remains trustworthy;
- whether retry is possible;
- the next action.

---

## 6. Copy hierarchy

### Page-title examples

- June invoice decision
- Findings
- Contract rules
- Evidence

### Section-title examples

- Payable decision
- Why the invoice changed
- Claims by determination
- Approved rule version
- Evidence timeline
- Source coverage
- Audit history

### Avoid demo language

Do not use:

- Headline demo
- Hero scenario
- Showcase
- Technical wow
- Magic
- AI reasoning

Use:

- Current invoice
- Technical preview
- Example dispute
- Recorded proposal
- Deterministic evaluation

---

## 7. Redesign milestones

### Milestone 1 — Foundation

- Consolidate theme/tokens.
- Replace wallet icon with neutral Evidue mark.
- Simplify navigation.
- Remove duplicate page titles.
- Reduce global card/shadow styling.
- Add core reusable components.

### Milestone 2 — Decision and Findings

- Redesign `/demo` as decision brief.
- Redesign current invoice as tabbed workspace.
- Replace large detail dialog with Evidence Drawer.

### Milestone 3 — Contract workbench

- Implement synchronized contract/rule split view.
- Move version history to tab/list.
- Add sticky approval bar in normal mode.

### Milestone 4 — Evidence

- Consolidate Data Sources and Outcome Ledger.
- Add audit log.
- Introduce source detail drawer.

### Milestone 5 — Responsive and QA

- Mobile layouts.
- Keyboard/focus behavior.
- Empty/error/loading states.
- Visual regression screenshots.
- Dark-mode parity or intentional temporary removal.

Do not combine all milestones into one Codex task.
