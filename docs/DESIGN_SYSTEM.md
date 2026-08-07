# Evidue Product Design System

## Design principle

Evidue is a finance-assurance workspace, not a dashboard gallery and not an AI chat surface. The UI prioritizes financial hierarchy, evidence traceability, dense operational review, and calm decision-making.

The protected `/pilot` product must feel usable by a finance/AP operator without exposing compiler plumbing. Technical reviewers can still reach provenance, AIR hashes, compiler assurance, fact derivation, and audit history under **Advanced**.

## Information hierarchy

Every primary surface follows this order:

1. Decision or task state.
2. Financial consequence.
3. Contractual reason.
4. Supporting customer evidence.
5. Audit/runtime metadata.

For the product workflow, the top-level sequence is:

```text
Contract → Rules → Invoice → Evidence → Reconcile → Export
```

The first screen after reconciliation leads with **vendor billed**, **verified payable**, **recommended deduction**, and **needs review**. AI/model details never outrank those numbers.

## Product character

- Calm, exact, auditable, operational.
- Sparse use of semantic color; no ornamental gradients or motion.
- Plain finance/operator language instead of internal model names.
- One primary action per workflow stage.
- Dollar outcomes and exceptions are visually dominant.
- AI is disclosed as a contract-interpretation aid, never represented as the financial adjudicator.

## Layout

- Centered wide workspace (`maxWidth="xl"`) for dense reconciliation review.
- 64px-class sticky context bar on desktop.
- Page padding approximately 32–36px desktop and 16px mobile.
- One dominant vertical workflow rather than a grid of competing dashboard modules.
- Major workflow cards use 18–28px section spacing.
- Metric grids may use two columns on small screens and four on desktop.
- Avoid modal-heavy normal flows; keep ingestion and review in context.

The older public demo may retain its own demonstration navigation. It must not dictate the protected product information architecture.

## Surfaces

### Workflow surface

Use a restrained bordered card with:

- overline step/category;
- descriptive title;
- optional **Ready / Not ready** state;
- one focused body;
- primary action close to the data it advances.

Use a subtle radius only. Avoid decorative drop shadows.

### Metric strip

Metrics should read as one financial summary, even when implemented as responsive bordered cells/cards. Use tabular numerals and short labels. Never communicate outcome only by color.

### Financial decision area

The four canonical numbers are:

- Vendor billed
- Verified payable
- Recommended deduction
- Needs review

`Needs review` is not payable and is not a deduction. Keep it visually and mathematically separate.

### Tables

Use tables for invoice lines, derived facts, and dense evidence/review data. Requirements:

- compact headers;
- right-aligned money;
- readable row identifiers;
- restrained hover state;
- explicit textual status;
- provenance in the explanation/detail area rather than extra decorative columns.

For each determination, expose the plain-English reason, approved rule identifier when useful, exact contract source clause, and decisive evidence timeline.

## Components

### Buttons

- One obvious primary action per stage.
- Secondary actions use outline/neutral treatment.
- Destructive actions use semantic red and require explicit confirmation.
- Disabled actions explain the missing prerequisite nearby.
- Use action-oriented labels: **Analyze contract with AI**, **Approve this rule version**, **Import evidence**, **Run reconciliation**, **Corrected invoice CSV**.

### Status labels

Canonical labels:

- Payable
- Disputed
- Needs review
- Ready
- Not ready
- Approved
- Active
- Superseded

Recommended semantics:

- payable/ready/approved: success;
- disputed: error;
- needs review/partial evidence: warning;
- not ready: neutral unless a real error exists.

### Alerts

Alerts are reserved for consequential state:

- compiler hard-gate failure;
- immutable approval;
- incomplete evidence capability;
- unresolved identity;
- needs-review lines;
- authentication/session problems.

Do not use alerts as decoration.

### Form fields

- Every input has a visible label.
- Invoice mapping happens before persistence.
- Contract upload supports common documents or pasted text.
- Evidence completeness is an explicit operator assertion with a safety explanation.
- A normal operator is never asked to author AIR, predicates, capability JSON, or proof-planner configuration.

## First-run and state design

### Empty workspace

Offer two explicit paths:

- **Try sample workspace** — creates an end-to-end safe example with payable, disputed, and needs-review lines.
- **Use my own data** — starts at agreement ingestion.

A populated workspace exposes **Reset workspace** as a confirmed destructive action so sample data never traps a user in the demo path.

### Loading

Use one top progress indicator and disable duplicate actions while an operation is in flight. Avoid indefinite per-card spinners.

### Errors

Show human-readable recovery language. Examples:

- missing invoice field → ask the user to map a source column;
- unsupported/ungrounded contract interpretation → block approval and identify the assurance failure;
- incomplete evidence → keep the affected amount in needs review rather than infer a failure.

### Needs review

State what resolves the line. The default resolution is to add authoritative evidence or fix identity and create a new append-only reconciliation run. Do not silently coerce an unresolved line into payable or disputed.

## AI disclosure

The contract stage must make the authority boundary visible:

> AI proposes the agreement interpretation. A human approves an immutable version. Approved deterministic rules and customer evidence decide invoice money.

Do not label reconciliation results as “AI decisions.”

## Advanced boundary

The normal workflow hides implementation internals. **Advanced** may expose:

- AIR version and payload hash;
- compiler assurance checks;
- verification plan;
- derived facts;
- workspace audit history.

These are review/debug artifacts, not prerequisites for operating the product.

## Motion

Use only short functional transitions for loading, disclosure, or selection. No animated gradients, floating cards, pulsing badges, or decorative motion.

## Accessibility

- Maintain at least 4.5:1 text contrast.
- Never rely on color alone for payable/disputed/review status.
- Preserve keyboard focus and native controls.
- Use meaningful table headings and field labels.
- Format money consistently with tabular numerals.
- Access keys use password inputs and are not placed in URLs.
