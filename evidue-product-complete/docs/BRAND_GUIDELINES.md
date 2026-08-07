# Evidue Brand Guidelines

## Brand position

Evidue is the buyer-side financial control for outcome-priced AI.

It should feel like an audit product used before money moves: calm, exact,
traceable, and independent. It must not look like a generic AI dashboard,
consumer fintech app, or experimental developer tool.

## Brand promise

**One invoice enters. One defensible payable amount leaves.**

## Personality

- Precise, not clever
- Independent, not adversarial
- Evidence-led, not model-led
- Financially serious, not futuristic
- Direct, not promotional

## Voice

Use short declarative language tied to a financial decision.

Preferred:

- Corrected payable amount
- Recommended deduction
- Customer-owned evidence
- Approved rule version
- Needs review
- Evidence unavailable

Avoid:

- AI-powered magic
- Smart insights
- Revolutionary
- Trust us
- Quality score
- Autonomous payment decision

## Visual identity

### Core palette

| Token | Value | Use |
|---|---:|---|
| Graphite | `#17212B` | Primary text |
| Deep navy | `#14212C` | Navigation and product frame |
| Evidence blue | `#275D82` | Primary actions, selected state, evidence links |
| Canvas | `#F4F6F8` | Application background |
| Surface | `#FFFFFF` | Work surfaces |
| Border | `#DCE2E8` | Structure and separation |
| Muted | `#66727D` | Secondary text |
| Payable | `#1E7657` | Confirmed payable states only |
| Disputed | `#B54A42` | Confirmed deductions only |
| Review | `#956A12` | Ambiguous or missing evidence only |

Semantic colors must never be decorative. Green means payable, red means a
supported dispute, and amber means human review.

### Logo

Use the compact `E` ledger mark implemented in the navigation. Do not use a
wallet, robot, sparkle, brain, shield-only, or generic AI icon as the brand mark.

### Typography

- Interface: Inter or system sans-serif
- Money, IDs, hashes, timestamps: IBM Plex Mono or system monospace
- Use tabular numerals for every financial value
- Avoid oversized marketing headlines inside the application

## Product presentation rules

1. The corrected payable amount is the primary visual result.
2. Contract, evidence, and determination remain visually distinct.
3. Tables are used where operators compare multiple records.
4. Drawers preserve context for evidence inspection.
5. Cards are reserved for discrete summaries, not every section.
6. Shadows are minimal; borders carry structure.
7. Gradients are not used in the application UI.
8. Synthetic data is always labeled.
9. The LLM boundary is always explicit.
10. No screen should require users to infer which number finance should act on.
