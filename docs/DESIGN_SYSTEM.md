# Evidue Product Design System

**Version:** 1.0  
**Source of truth:** `docs/BRAND_GUIDELINES.md`  
**Implementation target:** React + Material UI

---

## 1. System goals

The Evidue design system exists to make financial decisions easy to inspect, challenge, and reproduce.

It is optimized for:

- invoice review;
- contract-rule approval;
- exception triage;
- evidence inspection;
- audit history;
- exports and handoff.

It is not optimized for decorative dashboards, social engagement, or generic analytics.

---

## 2. Layout model

### App shell

Desktop:

- 216–224 px persistent navigation rail;
- compact 56 px top bar;
- main content maximum width of 1360 px;
- 24–32 px content gutters;
- no duplicate page title in both top bar and page body.

Mobile:

- top bar with product name, page title, and menu;
- navigation in a temporary drawer;
- content uses one column;
- tables collapse to prioritized rows or horizontal scroll only when necessary.

### Page anatomy

Every operational page follows:

1. Breadcrumb or compact context line.
2. Page title and one-line purpose.
3. Primary decision/action strip.
4. Main work surface.
5. Supporting metadata or audit trail.

Do not begin pages with four equal KPI cards unless four independent metrics genuinely drive a decision. Evidue usually has one primary amount and two supporting states.

### Content widths

- Decision summary: full width.
- Reading/document column: 680–760 px.
- Contract split view: 40/60 or 45/55.
- Right detail drawer: 480–560 px desktop.
- Dialogs: reserved for confirmation or blocking tasks, not routine inspection.

---

## 3. Design tokens

Implement these as MUI theme values and CSS variables. Do not scatter raw colors across components.

```css
:root {
  --ev-ink-950: #15181d;
  --ev-ink-700: #39414d;
  --ev-ink-500: #667085;
  --ev-canvas: #f5f7f9;
  --ev-surface: #ffffff;
  --ev-surface-muted: #f0f3f6;
  --ev-border: #d8dee6;
  --ev-border-soft: #e8ecf1;
  --ev-accent: #315cf4;
  --ev-accent-hover: #2446c7;
  --ev-accent-soft: #eef2ff;
  --ev-payable: #147a55;
  --ev-payable-soft: #eaf7f1;
  --ev-disputed: #b5473f;
  --ev-disputed-soft: #fcefed;
  --ev-review: #9a6815;
  --ev-review-soft: #fff7e5;
  --ev-focus-ring: 0 0 0 3px rgba(49, 92, 244, 0.22);
}
```

### Elevation

- Level 0: page and embedded sections; no shadow.
- Level 1: primary work surface; border only.
- Level 2: sticky toolbar or floating drawer; subtle shadow.
- Level 3: menu/dialog only.

Do not apply shadows to every card.

### Motion

- 120–180 ms for hover, selection, and drawer transitions.
- No bounce, spring, shimmer, or decorative number animation.
- Loading states should preserve layout and communicate the operation.

---

## 4. Component inventory

### 4.1 Decision header

Use on invoice overview and reconciliation.

Contains:

- invoice context;
- submitted amount;
- corrected payable amount as the dominant value;
- recommended deduction;
- needs-review amount;
- decision status;
- one primary action.

Rules:

- The payable amount is visually dominant after reconciliation.
- Before reconciliation, the submitted amount is dominant and the future result is explicitly pending.
- Do not use four independent metric cards.
- Use a thin vertical or horizontal divider to separate supporting amounts.

### 4.2 Metric strip

Use for 2–4 supporting facts beneath a decision.

Examples:

- 10,000 claims;
- 8,320 payable;
- 1,680 disputed;
- 100% evidence coverage.

Use a flat strip with separators, not cards.

### 4.3 Status badge

Allowed statuses:

- Payable
- Disputed
- Needs review
- Approved
- Pending approval
- Superseded
- Read only
- Synthetic

Requirements:

- text label always present;
- maximum one icon;
- semantic colors only for financial or approval state;
- no badge walls.

### 4.4 Data table

Use for claims, invoices, rule versions, and source records where users compare multiple attributes.

Required behavior:

- sticky header for long tables;
- right-aligned money and counts;
- tabular numerals;
- first column provides identity/context;
- filters above the table in a single toolbar;
- row click opens detail drawer;
- selected row has a subtle accent background and left indicator;
- empty and error states appear inside the table region;
- actions use a final narrow column or overflow menu.

Avoid:

- excessive columns;
- centered numeric values;
- status represented only by colored text;
- action buttons in every cell;
- card-per-row layouts on desktop.

### 4.5 Filter toolbar

One compact row containing:

- search;
- status filter;
- rule filter;
- evidence filter;
- date/window filter where relevant;
- active-filter count;
- clear filters.

Use a popover or drawer for advanced filters. Do not stack a large filter card above every table.

### 4.6 Finding list

Use for the five dispute categories because the set is small and explanatory.

Each row shows:

- rule ID;
- finding label;
- affected outcomes;
- deduction amount;
- percentage of invoice;
- disclosure chevron.

This is a structured list, not a full table and not five separate cards.

### 4.7 Evidence drawer

Use a right-side drawer to inspect a claim while preserving the table/list behind it.

Width: 520 px desktop; full-screen sheet on narrow viewports.

Sections:

1. Determination header.
2. Vendor claim.
3. Contract condition.
4. Deterministic evaluation.
5. Evidence timeline.
6. Provenance and source record IDs.
7. Financial effect.
8. Export/open raw evidence actions.

The drawer should be deep-linkable through the outcome ID.

Use a modal dialog only for approval confirmation or irreversible actions.

### 4.8 Evidence timeline

Each event row contains:

- timestamp;
- event label;
- source system;
- source record ID;
- direct/derived/computed provenance;
- values relevant to the rule;
- a plain-language explanation.

Use a quiet vertical line and small status marker. Do not use a colorful project-management timeline.

### 4.9 Contract document pane

The source contract appears as a document, not a textarea inside a generic card.

Read-only mode:

- paper-like surface;
- clause anchors;
- selected clause highlight;
- line wrapping optimized for reading;
- source hash and metadata in a compact header.

Editable/local mode:

- editing state clearly distinguished;
- unsaved changes visible;
- compile action belongs in a sticky footer or header toolbar.

### 4.10 Rule proposal pane

For every rule show:

- rule ID and title;
- source clause link;
- operation name in mono;
- parameters in structured rows;
- required evidence;
- validation state;
- change relative to active version.

Avoid raw JSON as the primary interface. Raw JSON may be available in a collapsible technical section.

### 4.11 Approval bar

A sticky action bar at the bottom of the contract workbench:

- proposal status;
- number of rules and validation errors;
- active version;
- secondary action: discard/supersede;
- primary action: approve version.

Approval always shows a confirmation dialog summarizing the version and financial impact boundary.

### 4.12 Audit log

Use a chronological stacked list for:

- compilation created;
- validation completed;
- proposal approved;
- version superseded;
- reconciliation executed;
- export generated.

Each row includes actor, event, timestamp, object ID/version, and optional detail expansion.

### 4.13 Alerts

Use alerts only for:

- synthetic-data disclosure;
- read-only public mode;
- missing/contradictory evidence;
- dangerous approval or reset actions;
- real system errors.

Do not use an alert for ordinary explanatory copy.

### 4.14 Empty states

Every empty state must explain:

- why no data is shown;
- whether it is expected;
- what the user can do next.

Examples:

> No claims match these filters. Clear one or more filters to return to the complete invoice.

> No active rule proposal. Compile the current contract to create a proposal for review.

Avoid “No data” and generic placeholder art.

---

## 5. Navigation system

### Public/demo navigation

Use four primary destinations:

1. **Decision** — current invoice overview.
2. **Findings** — claims and disputes within the current invoice.
3. **Contract rules** — contract-to-rule workbench.
4. **Evidence** — sources, ledger, and audit trail.

Move these out of primary navigation:

- invoice history with only illustrative rows;
- Vendor Preflight;
- Scenario Lab;
- separate Disputes page that duplicates current-invoice findings;
- separate Outcome Ledger and Data Sources destinations when they can be tabs under Evidence.

Experimental/technical surfaces may live under a single **Technical** menu or be available only in local development.

### Navigation labels

Prefer concise buyer language:

- Decision
- Findings
- Contract rules
- Evidence
- Technical

Avoid labels that sound like demo architecture:

- Workspace
- Infrastructure
- Evidue reconciliation
- Scenario Lab
- Outcome Ledger as a primary buyer destination

---

## 6. Accessibility

- Minimum text contrast: WCAG AA.
- All status colors paired with text.
- Visible keyboard focus using `--ev-focus-ring`.
- Tables keyboard navigable; row click has an equivalent button/link target.
- Drawers announce title and determination state.
- Financial values use meaningful labels, not position alone.
- Loading and result changes use appropriate live regions.
- Do not remove outlines.
- Minimum pointer target: 36 × 36 px desktop, 44 × 44 px mobile.

---

## 7. Responsive rules

At widths below 900 px:

- navigation becomes a drawer;
- decision header stacks;
- metric strip wraps to two rows;
- split contract workbench becomes tabs: Contract / Proposed rules / History;
- evidence drawer becomes full-screen;
- low-priority table columns hide before horizontal scrolling is introduced.

At widths below 600 px:

- reduce page gutters to 16 px;
- primary actions become full-width only when necessary;
- findings become stacked rows;
- financial values remain visible without horizontal scrolling.

---

## 8. MUI implementation guidance

Prefer:

- `Box`, `Stack`, `Divider`, `Paper`, `Drawer`, `Table`, `Tabs`, `Toolbar`, `Chip`, `Alert`;
- semantic wrapper components such as `DecisionHeader`, `MetricStrip`, `StatusBadge`, `EvidenceDrawer`, `FilterToolbar`, and `AuditLog`;
- theme component overrides for repeated behavior.

Reduce:

- generic `Card` usage;
- page-specific raw CSS selectors;
- nested `Card` and `Paper` surfaces;
- one-off gradients;
- giant typography classes;
- separate visual systems in `App.tsx` and `ProductShell.tsx`.

One component and token system must serve both the invoice workspace and the product shell.
