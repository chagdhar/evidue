# Evidue Brand Guidelines

**Version:** 1.0  
**Brand direction:** Audit-grade financial control  
**Applies to:** Product UI, website, demos, exports, sales material, documentation, and customer communications

---

## 1. Brand foundation

### What Evidue is

Evidue is the buyer-side financial control for outcome-priced AI. It determines what an AI vendor actually earned by applying customer-approved contract rules to evidence from customer-owned systems.

### Brand promise

**One invoice enters. One defensible payable amount leaves.**

### Positioning statement

For finance, procurement, and operations teams paying AI vendors for outcomes, Evidue independently reconciles every billed claim against the contract and operational evidence. Unlike invoice-processing tools or AI quality platforms, Evidue produces a corrected payable amount with a reproducible reason and evidence trail for every exception.

### Brand pillars

1. **Independent** — Evidue represents the buyer's evidence and contract, not the vendor's self-reported metric.
2. **Deterministic** — Models may propose rules; only approved deterministic logic makes financial classifications.
3. **Traceable** — Every amount, rule, event, and version can be inspected and reproduced.
4. **Operational** — Evidue ends in a financial action: pay, dispute, or review.
5. **Calm** — The product communicates risk without alarmism or spectacle.

### Brand personality

Evidue should feel:

- precise, not clever;
- impartial, not adversarial;
- confident, not promotional;
- technical, not cryptic;
- financial, not “fintech lifestyle”;
- modern, not fashionable;
- evidence-led, not AI-led.

### The brand is not

- a glowing AI dashboard;
- a generic analytics product;
- a fraud alarm;
- a legal opinion;
- a vendor scorecard;
- a quality-management system;
- an autonomous payment decision-maker.

---

## 2. Audience hierarchy

### Primary buyer

Finance, procurement, or accounts-payable leaders responsible for approving outcome-priced AI vendor invoices.

They need:

- the amount to pay;
- the amount to hold or dispute;
- the contractual basis;
- the evidence;
- confidence that the result is reproducible.

### Primary operator

Support operations, AI operations, or vendor-management teams who understand the workflow, data sources, and exceptions.

They need:

- explainable findings;
- evidence coverage;
- fast correction of mappings;
- an audit trail;
- exports that finance and vendors can use.

### Secondary audience

Technical teams evaluating the integration and trust boundary.

They need:

- rule schema visibility;
- source provenance;
- model boundaries;
- deterministic behavior;
- version and hash information.

The UI must prioritize the buyer's decision first, then reveal operational and technical detail progressively.

---

## 3. Naming and messaging

### Primary name

**Evidue**

Use the standalone wordmark. Do not append “AI,” “Verify,” “Control,” “Prove,” or other product qualifiers to the company name in the main brand lockup.

### Descriptor

Use one of these when context is needed:

- Outcome invoice control
- Independent AI invoice reconciliation
- Buyer-side verification for outcome-priced AI

Preferred product-header descriptor:

> Outcome invoice control

### Tagline

Primary:

> Know what the AI vendor actually earned.

Functional alternative:

> Reconcile outcome-priced AI invoices against the contract and customer evidence.

### Core product explanation

> Evidue turns the contract into approved, versioned rules, applies those rules deterministically to customer-owned evidence, and produces the payable amount, disputed charges, and review items.

### Trust-boundary statement

Use this wording consistently:

> The LLM proposes contract rules. A human approves and versions them. Deterministic code evaluates every invoice line.

### Synthetic-data disclosure

Use the existing required disclosure:

> Synthetic demonstration data. Operationally realistic data generated deterministically. No real customer or vendor data is shown.

### Vocabulary

Use:

- submitted invoice;
- payable amount;
- recommended deduction;
- disputed charge;
- needs review;
- approved rule version;
- evidence source;
- source record;
- contractual condition;
- determination;
- reconciliation;
- vendor claim;
- audit trail;
- evidence coverage.

Avoid:

- savings, unless a customer accepted the deduction;
- fraud, unless fraud was independently established;
- overcharge, before customer confirmation;
- hallucination;
- AI-powered;
- magic;
- smart;
- confidence score;
- “verified” without naming what evidence was verified;
- quality score;
- autonomous adjudication.

### CTA language

Primary actions should be nouns or clear verbs tied to work:

- Review findings
- Open invoice decision
- Inspect evidence
- Review contract rules
- Export dispute package
- Download evidence JSON
- Approve rule version
- Compile rule proposal

Avoid vague CTAs:

- Explore
- Learn more
- Get started
- See magic
- Analyze now
- Optimize

---

## 4. Logo system

### Recommended launch identity

Use a restrained wordmark plus a simple monogram. Do not delay launch for a complex custom logo.

### Monogram concept

A square **E** mark composed of:

- one vertical ledger spine;
- three horizontal evidence rows;
- the middle row terminating in a small square “proof point.”

The geometry should feel like a ledger, rule list, and evidence trace—not a shield, wallet, sparkle, robot, scale of justice, or checkmark badge.

### Lockup

- Mark on the left, “Evidue” on the right.
- Product descriptor below only in large navigation contexts.
- Minimum mark size: 24 px digital.
- Clear space: at least half the mark width on every side.

### Temporary implementation

Until a custom SVG is drawn, use a text-only wordmark or a simple `E` in a 28 × 28 square. Remove the existing wallet icon; it implies payments rather than evidence and reconciliation.

---

## 5. Visual direction

### Design phrase

**Audit-grade clarity**

The product should resemble a serious financial review workspace: calm surfaces, strong hierarchy, dense but readable records, and evidence detail that opens without losing context.

### Visual principles

1. **Decision before dashboard** — lead with the payable decision, not a grid of generic KPIs.
2. **One dominant surface** — every page has one primary work surface; supporting content uses dividers and sections rather than nested cards.
3. **Progressive evidence** — summary first, rule next, source record last.
4. **Semantic restraint** — green, red, and amber are reserved for financial state, never decoration.
5. **Tabular precision** — money, counts, IDs, hashes, and timestamps use tabular numerals or monospace.
6. **No decorative AI language** — no gradients, orbit graphics, sparkles, blobs, glass effects, or model avatars.
7. **Quiet confidence** — use neutral backgrounds, one brand accent, crisp borders, and controlled density.

### Recommended palette

#### Core light palette

| Token | Value | Use |
|---|---:|---|
| Ink 950 | `#15181D` | Primary text, solid buttons |
| Ink 700 | `#39414D` | Secondary headings |
| Ink 500 | `#667085` | Supporting text |
| Canvas | `#F5F7F9` | App background |
| Surface | `#FFFFFF` | Primary work surfaces |
| Surface muted | `#F0F3F6` | Table headers, filters, secondary areas |
| Border | `#D8DEE6` | Primary borders |
| Border soft | `#E8ECF1` | Row and section separators |
| Evidence blue | `#315CF4` | Navigation, focus, primary link/action |
| Evidence blue dark | `#2446C7` | Hover/pressed |
| Evidence blue soft | `#EEF2FF` | Selected row, info highlight |

#### Financial semantic palette

| State | Strong | Soft | Use |
|---|---:|---:|---|
| Payable | `#147A55` | `#EAF7F1` | Confirmed payable only |
| Disputed | `#B5473F` | `#FCEFED` | Confirmed dispute/deduction only |
| Needs review | `#9A6815` | `#FFF7E5` | Ambiguous or incomplete evidence |
| Informational | `#315CF4` | `#EEF2FF` | Product selection and guidance |

Rules:

- Never encode status by color alone; always pair with a label and, where useful, an icon.
- Do not use semantic colors for navigation or decorative illustrations.
- Do not place green and red values in equal-weight “trading dashboard” tiles.

### Dark mode

Light mode is the source-of-truth design for finance workflows. Dark mode is secondary and should only ship when every table, drawer, alert, code block, and semantic state passes contrast and visual QA. Do not let dark-mode support block the redesign.

### Typography

Use system-accessible fonts already compatible with the repository:

- UI and prose: `Inter`, fallback system sans-serif.
- Financial values, IDs, hashes, timestamps, and rule operations: `IBM Plex Mono`.

Scale:

| Role | Size / line height | Weight |
|---|---|---|
| Display decision | 48–64 / 1.0 | 680–720 |
| Page title | 28–36 / 1.15 | 650–700 |
| Section title | 18–22 / 1.3 | 620–680 |
| Body | 14–16 / 1.5 | 400–500 |
| Table | 13–14 / 1.4 | 400–550 |
| Label | 11–12 / 1.3 | 600–700 |
| Mono metadata | 12–13 / 1.4 | 500–600 |

Rules:

- Use sentence case.
- Avoid oversized marketing headlines inside the product.
- Use tabular numerals for all financial data.
- Limit uppercase to short metadata labels; never uppercase full sentences.

### Spacing and shape

- Base unit: 4 px.
- Common spacing: 8, 12, 16, 24, 32, 48.
- Page gutters: 24 px at laptop widths, 32 px at desktop widths.
- Border radius: 6 px controls, 8 px panels, 10 px maximum for major surfaces.
- Avoid pill-shaped containers except compact statuses and filters.
- Avoid shadows on standard cards. Use a subtle shadow only for floating drawers, menus, and dialogs.

### Iconography

- Use one outlined icon family consistently.
- Default icon size: 16 or 18 px.
- Icons support labels; they do not replace critical labels.
- Avoid wallet, robot, sparkle, brain, magic wand, and shield imagery as primary product symbols.

---

## 6. Brand voice

### Tone

- Direct
- Evidence-led
- Calm
- Specific
- Honest about uncertainty

### Writing structure

1. State the financial fact.
2. Explain the contractual reason.
3. Name the evidence.
4. Offer the next action.

Example:

> **$1.50 is disputed.** The customer contacted support again within the seven-day exclusion window. The finding is supported by Zendesk conversation `ZD-4821-R` and rule `R1`. Review the evidence timeline.

Avoid:

> Our intelligent AI engine found an exciting optimization opportunity!

### Status copy

Preferred:

- Payable
- Disputed
- Needs review
- Rule proposal pending approval
- Approved rule version
- Evidence unavailable
- Reconciliation complete

Avoid:

- Success
- Failed
- Bad outcome
- Risky
- AI verified
- 97% confident

---

## 7. Brand quality checklist

Before shipping a public screen, confirm:

- The first visible message is about a buyer decision, not the model.
- There is one primary action.
- The screen uses no unnecessary gradient or decorative glow.
- Semantic colors indicate real financial state only.
- Every amount can be traced to a rule and evidence.
- Synthetic data is disclosed.
- No vendor is accused of overbilling or fraud without customer confirmation.
- No model is described as making the payment decision.
- The page remains understandable in grayscale.
- The page feels credible in a finance review meeting or audit screenshot.
