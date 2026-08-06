# Evidue UX Redesign Specification

## Objective

Make Evidue read as a mature financial-control product within the first ten
seconds. A reviewer should immediately understand the payable amount, why it
changed, and how to inspect the evidence.

## Primary workflow

**Decision → Findings → Contract rules → Evidence**

The current implementation preserves technical pages, but they remain secondary
and should not interrupt the main review path.

## Screen specifications

### Decision

The top section shows:

- corrected payable amount
- submitted invoice
- recommended deduction
- needs-review amount
- payable/disputed outcome counts

Below it:

- reconciliation bridge
- deduction categories
- claims table
- export actions

The primary action is evidence inspection, not rerunning the demo.

### Findings

Show the five contractual deduction categories as a flat operational list. Each
row includes rule ID, reason, count, amount, and share of invoice. Selecting a
row filters the claims table or opens the relevant evidence.

### Contract rules

Use a split review model:

- left: source contract language
- right: structured proposed/approved rules

Show model identifier, source hash, version, approval state, and rule changes.
Raw JSON belongs behind progressive disclosure.

### Evidence

Consolidate data source and outcome-ledger concepts around evidence provenance.
Show source authority, record counts, identifiers, timestamps, and transformation
steps. Use a drawer for raw record inspection.

### Technical pages

Overview, invoices, vendor preflight, outcome ledger, and scenario lab remain
available but visually subordinate. They are implementation proof, not the main
customer workflow.

## Content rules

- Use “decision,” “finding,” “rule,” and “evidence” consistently.
- Avoid introducing new product names for internal sub-systems unless required.
- Explain model behavior once, clearly: the LLM proposes; humans approve;
  deterministic code decides.
- Keep synthetic-data language visible but not dominant.

## Definition of done

- Navigation reflects the primary workflow.
- The wallet icon is removed.
- Gradients and excessive shadows are removed.
- Independent cards are consolidated into strips or work surfaces.
- The payable amount is visually dominant.
- Evidence inspection retains context.
- Mobile layouts remain usable at 320px width.
- Existing reconciliation totals and behavior remain unchanged.
