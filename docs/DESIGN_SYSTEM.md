# Evidue Product Design System

## Design principle

Evidue is an audit workspace, not a dashboard gallery. The UI should prioritize
financial hierarchy, evidence traceability, and dense operational review.

## Information hierarchy

Every primary screen follows this order:

1. Decision or task state
2. Financial consequence
3. Contractual reason
4. Supporting evidence
5. Audit metadata

## Navigation

Primary navigation:

- Decision
- Findings
- Contract rules
- Evidence

Secondary technical navigation:

- Overview
- Invoices
- Outcome ledger
- Vendor preflight
- Scenario lab

Technical surfaces are visually subordinate. This prevents the application from
presenting every demo capability as an equally important product module.

## Layout

- Permanent 252px dark navigation on desktop
- 64px top context bar
- Maximum content width: 1320px
- Page padding: 36px desktop, 16px mobile
- Use one dominant work surface per page
- Use 18–28px section spacing depending on hierarchy

## Surfaces

### Primary work surface

White or dark neutral surface with a one-pixel border. No drop shadow. Maximum
radius 6px.

### Metric strip

Metrics share one bordered row rather than appearing as independent floating
cards. Semantic status can be shown with a 3px top rule.

### Financial decision panel

The payable amount is the largest number. Submitted amount, deduction, and needs
review appear as secondary line items in a structured side panel.

### Tables

Use compact headers, tabular numerals, restrained hover state, and sticky context
where needed. Tables should enable comparison rather than decorate a page.

### Evidence drawer

Use a right-side drawer for claim detail so users retain invoice context. Show:

- vendor assertion
- contract clause
- approved rule
- deterministic result
- source events
- provenance
- deduction

## Components

### Buttons

- One primary action per page
- Primary buttons use evidence blue
- Secondary actions use outlines
- Destructive actions use semantic red only when genuinely destructive
- Disabled public-demo actions should be removed, not merely allowed to fail

### Status labels

Use concise labels:

- Payable
- Disputed
- Needs review
- Read-only preview
- Approved
- Superseded

### Form fields

Contract source text should look like a document work surface. In public mode,
read-only state must be visually obvious and explained in adjacent copy.

### Empty and error states

State what is unavailable, why, and what the user can still do. Never show an
indefinite spinner after a request has failed.

## Motion

Use only short functional transitions for drawers, loading state, or selection.
No animated gradients, floating cards, pulsing badges, or decorative motion.

## Accessibility

- Maintain 4.5:1 text contrast
- Never rely only on color for payable/disputed/review status
- Preserve keyboard focus and native controls
- Use meaningful table headings and drawer labels
- Format money consistently and with tabular numerals
