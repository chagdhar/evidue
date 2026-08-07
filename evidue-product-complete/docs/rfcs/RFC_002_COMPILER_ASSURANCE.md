# RFC 002 — Compiler Assurance

Status: Design baseline; core implemented in `product-complete`
Depends on: RFC 001

## Problem

Schema-valid LLM output is not evidence that the model understood a contract correctly. A second LLM that simply says “looks correct” only moves the trust problem.

Evidue will treat contract compilation like a safety-critical compiler pipeline with independent assurance stages.

## Principle

The LLM proposes semantics. Evidue proves as much as possible deterministically, then uses narrow semantic checks for what cannot be statically proven.

No single model result can make a compilation approvable.

## Assurance pipeline

```text
Effective contract graph
      ↓
Primary semantic compiler
      ↓
Candidate canonical graph
      ↓
┌──────────────────────────────────────┐
│ deterministic static assurance      │
│ semantic equivalence assurance      │
│ metamorphic mutation assurance      │
│ generated execution probes          │
│ optional differential compilation   │
└──────────────────────────────────────┘
      ↓
AssuranceRun
      ↓
PASS / REVIEW / BLOCK
```

## Stage A — deterministic grounding

Hard-block on:

- source span not found;
- text hash mismatch;
- unknown document/clause ID;
- unresolved material definition;
- unresolved material reference;
- circular amendment/reference where semantics cannot be resolved;
- unknown predicate/operator;
- type mismatch;
- invalid money/currency;
- invalid time unit;
- settlement node without precise source provenance;
- material clause with no coverage classification.

These checks do not use an LLM.

## Stage B — semantic coverage

Every source clause must be classified:

- `EXECUTED`
- `PROOF_DEPENDENT`
- `MODEL_ASSISTED`
- `HUMAN_REQUIRED`
- `PROCEDURAL`
- `NON_OPERATIONAL`
- `UNSUPPORTED`

For material clauses:

```text
unclassified > 0       => BLOCK
unsupported > 0        => BLOCK unless explicitly approved as manual-only
missing source binding => BLOCK
```

The report must expose counts and exact clauses.

## Stage C — structured semantic critique

Run a separate semantic critic per material clause and candidate nodes.

The critic does not issue a score. It answers structured questions:

- omitted condition?
- omitted exception?
- changed deadline?
- changed amount/rate?
- changed party/bearer/beneficiary?
- changed modality (must/may/must-not)?
- changed threshold?
- strengthened obligation?
- weakened obligation?
- added unsupported inference?

Each finding cites both source span and candidate node.

Disagreements become findings; they are not silently auto-resolved.

## Stage D — bidirectional semantic equivalence

Generate a canonical natural-language rendering from the candidate graph.

Check both directions:

```text
source clause entails canonical rendering
canonical rendering entails source clause
```

The two directions catch both weakening and strengthening.

This is a semantic assurance signal, not a formal proof. Any material mismatch becomes `REVIEW` or `BLOCK` depending on risk class.

## Stage E — metamorphic mutation tests

Automatically mutate contract text in controlled ways, recompile, and compare normalized graphs.

Mutation classes:

- money values;
- percentages;
- dates/durations;
- thresholds;
- inclusive/exclusive boundaries;
- party names/roles;
- negation;
- exception insertion/removal;
- conjunction/disjunction;
- rate-table entries.

Example:

```text
$1.50 -> $2.10
7 days -> 14 days
```

Expected result:

- corresponding constant node changes;
- dependent normalized hash changes;
- unrelated graph nodes remain stable.

Failure modes:

- source mutation produces no semantic change => compiler missed term;
- unrelated nodes change => unstable compiler;
- mutation changes wrong node => semantic misbinding.

## Stage F — generated execution probes

Every executable predicate/norm/settlement expression generates boundary cases.

Example:

```text
within 4 hours
```

Probe:

```text
3:59:59  -> expected satisfied
4:00:00  -> explicit boundary semantics
4:00:01  -> expected violated
missing   -> expected unknown
conflict  -> expected conflicting/indeterminate
```

Money example:

```text
$20 per eligible unit
```

Probe:

```text
eligible=true, quantity=1  -> $20
eligible=false             -> $0
eligible=unknown           -> review
quantity=2                 -> $40
```

Execution probes run before approval.

## Stage G — optional differential compilation

For high-risk clauses, compile independently using:

- a second prompt path;
- optionally a different model/provider.

Normalize both outputs before comparison.

Agreement is a positive signal. Disagreement creates targeted findings. Evidue does not choose by majority vote.

## Risk classes

Classify material clauses:

### Critical

- pricing;
- liability/credits affecting settlement;
- eligibility/exclusions;
- thresholds;
- timing windows;
- duplicate rules;
- amendments changing financial terms.

Require all assurance stages.

### Standard

- objective operational obligations without direct financial effect.

Require deterministic + semantic critique + probes.

### Low

- non-operational/procedural metadata.

Deterministic grounding and classification may be sufficient.

## Approval gate

Persist:

```text
AssuranceRun
AssuranceFinding
AssuranceProbeResult
AssuranceMutationResult
```

Approval requires:

```text
no blocking findings
100% material coverage
grounding pass
static type pass
all critical probes pass
no unresolved critical semantic disagreement
```

Scores may be displayed, but hard gates decide approval.

## Efficiency controls

Compiler assurance must be cost-aware:

- deterministic stages always run;
- semantic critique only on material clauses;
- metamorphic tests target extracted constants/conditions, not entire documents blindly;
- cache assurance by source hash + graph hash + model/prompt version;
- differential compilation only for critical/high-risk clauses or manual escalation.

## Acceptance gates

- intentionally deleting an exception is detected;
- changing a price mutates the correct settlement node;
- changing a deadline mutates the correct temporal predicate;
- an unrelated mutation does not rewrite unrelated nodes;
- a missing material clause cannot pass approval;
- an assurance run is reproducible from stored hashes and versions.
