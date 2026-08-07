# Evidue Design Implementation Plan for Codex

**Use with:** `docs/BRAND_GUIDELINES.md`, `docs/DESIGN_SYSTEM.md`, `docs/UX_REDESIGN_SPEC.md`, and `docs/MOBBIN_REFERENCE_BOARD.md`

The redesign must be implemented in bounded milestones. Do not ask Codex to redesign the whole repository in one run.

---

## 1. Preparation

Before coding:

1. Commit the current repository.
2. Add the design documents.
3. Confirm the current frontend test/build baseline.
4. Capture screenshots at 1440 × 900 and 390 × 844 for:
   - `/demo`;
   - `/demo/invoices/current?outcome=OUT-004821`;
   - `/demo/contracts/current`;
   - `/demo/data-sources`.
5. Create a branch:

```bash
git switch -c design/audit-grade-ui
```

---

## 2. Milestone prompts

## Milestone 1 — Design foundation and navigation

### Goal

Create one visual system and simplify public navigation without changing domain behavior.

### Required work

- Read all four design documents.
- Consolidate MUI theme tokens.
- Remove generic gradients and default card shadows.
- Replace the wallet logo with a simple text/`E` mark.
- Reduce public navigation to Decision, Findings, Contract rules, and Evidence.
- Place technical/demo routes under one secondary menu or retain them as unlisted routes.
- Create reusable components:
  - `PageHeader`;
  - `DecisionHeader`;
  - `MetricStrip`;
  - `StatusBadge`;
  - `FilterToolbar`;
  - `SectionHeader`.
- Do not redesign page bodies yet.

### Validation

- Existing routes continue to render.
- No financial totals change.
- Frontend tests and build pass.
- Public mode remains read-only.

---

## Milestone 2 — Decision page

### Goal

Turn `/demo` from a generic dashboard into a financial decision brief.

### Required work

- Make corrected payable amount dominant.
- Add submitted, deduction, and review values as supporting facts.
- Replace metric cards with one metric strip.
- Show the five deduction categories as a flat structured list.
- Use one primary CTA: `Review findings`.
- Keep export as secondary.
- Compress the trust boundary and evidence readiness.
- Remove duplicate educational content and unnecessary cards.

### Validation

- All values come from the API.
- `10,000`, `$15,000`, `$12,480`, and `$2,520` remain exact.
- Synthetic disclosure remains visible.
- Layout works at desktop and mobile widths.

---

## Milestone 3 — Findings workspace and Evidence Drawer

### Goal

Create a credible operational review workspace.

### Required work

- Add tabs: Findings, All claims, Exports.
- Implement compact filter toolbar.
- Keep the findings list for five categories.
- Use a dense table for all claims.
- Replace the large outcome dialog with a right-side Evidence Drawer.
- Preserve `?outcome=OUT-004821` deep linking.
- Implement drawer sections from the design-system specification.
- Preserve filters and scroll position while the drawer is open.

### Validation

- Existing outcome API and exports remain unchanged.
- Keyboard navigation and focus restoration work.
- Direct refresh with outcome query opens the drawer.
- Public read-only mode shows no mutation controls.

---

## Milestone 4 — Contract rules workbench

### Goal

Make contract compilation look like a governed document-review process.

### Required work

- Split contract source and rules into synchronized panes.
- Add Active rules, Pending proposal, and Version history tabs.
- Present structured rule rows rather than raw JSON cards.
- Add source-clause highlighting.
- Keep live Gemini and recorded proposal behavior unchanged.
- Use a sticky approval bar only in normal mode.
- Keep public mode visibly read-only.

### Validation

- Stale source cannot be approved.
- Approved version behavior is unchanged.
- Compiler tests pass.
- Contract page remains usable at 1024 px and mobile widths.

---

## Milestone 5 — Evidence consolidation

### Goal

Create one Evidence destination.

### Required work

- Combine Data Sources and Outcome Ledger using tabs.
- Add an Audit log tab using existing compilation/reconciliation metadata where available.
- Use source table rather than source cards.
- Use a source detail drawer for samples and schema.
- Keep existing raw-data and provenance access.
- Redirect or preserve legacy routes.

### Validation

- No data source or evidence functionality is lost.
- Source authority and provenance remain explicit.
- Empty/error states are complete.

---

## Milestone 6 — Quality pass

### Goal

Remove remaining generated-template artifacts.

### Required work

- Search for one-off gradients, oversized headings, duplicate alerts, nested cards, and inconsistent radius values.
- Review every status color in grayscale.
- Add skeleton/loading states.
- Add contextual empty states.
- Test keyboard focus and drawer behavior.
- Capture before/after screenshots.
- Decide whether dark mode meets parity; disable the toggle temporarily if it does not.

### Validation

- Frontend test and build pass.
- Backend tests remain unaffected.
- No hidden public mutation controls.
- Visual QA checklist passes.

---

## 3. Codex operating rules

Every Codex prompt must include:

- exact milestone goal;
- relevant files;
- explicit non-goals;
- existing product invariants;
- validation commands;
- instruction to review `git diff`.

Do not use prompts like:

> Make the app look better.

Use:

> Implement Milestone 2 from `docs/DESIGN_IMPLEMENTATION_PLAN.md`. Read the brand, design system, UX spec, and Mobbin reference board first. Do not alter routes, API contracts, financial totals, or the deterministic engine. Return a plan of no more than six bullets, then implement.

Use one new Codex thread per milestone.

---

## 4. Definition of done

The redesign is complete when:

- the UI tells one buyer-side story;
- the payable decision is visible within five seconds;
- navigation no longer exposes the codebase structure;
- contract rules feel governed and versioned;
- evidence can be inspected without losing context;
- tables and filters support real operational review;
- no screen depends on gradients or card grids for hierarchy;
- public/demo truthfulness remains intact;
- all values still originate from backend determinations;
- frontend tests/build and relevant backend tests pass.
