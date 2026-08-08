# Agreement Runtime

> **Implementation status:** the verified-runtime RFC set in [`VERIFIED_RUNTIME_DESIGN_INDEX.md`](VERIFIED_RUNTIME_DESIGN_INDEX.md) is now substantially implemented in the product path: first-class predicates, compiler assurance, verification planning/facts, AIR financial authority, provenance, and versioned migration comparison. Remaining future work is connector breadth and managed production tenancy—not a second adjudication architecture.

Evidue separates contract interpretation from financial adjudication.

## Runtime boundary

```text
agreement packet
  -> native clause-analysis proposal (LLM, optional recorded fixture)
  -> exact source-span binding
  -> deterministic Agreement IR lowering
  -> conformance gate + human approval
  -> persisted immutable AIR version
  -> persisted verification plan
  -> evidence / deterministic facts
  -> deterministic obligation + settlement evaluation
```

The LLM never returns a payable/disputed invoice decision and never calculates a final payable amount.

## Agreement packets

A pilot contract automatically owns an agreement bundle. Additional text, Markdown, or PDF documents can be added with effective periods and precedence. Relations are explicit: `amends`, `supersedes`, and `incorporates`. Circular relation graphs are rejected. A native compilation is bound to the effective documents and relation metadata for the billing period.

## Native compilation

`POST /api/pilot/contracts/{contract_id}/compile-native?mode=auto|live|recorded`

Live mode calls Gemini using the strict `AgreementCompilationProposal` schema. Every proposed clause must be an exact substring of an effective source document. Evidue records its byte/character span and SHA-256 hash before deterministic lowering. A caller-supplied proposal is accepted for tests but receives the same source-binding validation.

Approval is refused if the persisted AIR payload hash has changed or if conformance has blocking diagnostics, unsupported material clauses, or unrepresented material clauses.

## Verification plans

Proof requirements are matched to evidence capabilities, not product names. Capabilities describe entity type, fields, event types, state transitions, authority, identity keys, timestamps, historical availability, and whether absence can be proven. Plans are immutable/versioned per approved AIR version.

## Facts

Deterministic facts are persisted with truth values `true`, `false`, `unknown`, or `conflicting`, exact evidence IDs, authority, evaluator version, and input hash. Missing evidence does not become false.

Semantic fact extraction is isolated behind `SemanticFactExtractor`. It asks one narrow question, requires exact evidence citations for decisive answers, forces low-confidence output to `unknown`, and has no settlement API. Model-assisted facts must remain reviewable and must not directly determine money.

## Dual run

`EVIDUE_AGREEMENT_RUNTIME_DUAL_RUN=true` runs legacy and AIR compatibility paths together. An approved persisted AIR version is required; there is no silent legacy-to-AIR fallback in production dual-run mode. The legacy result remains authoritative while differences are persisted and exposed through:

`GET /api/pilot/reconciliations/{run_id}/agreement-comparison`

A reconciliation records the exact AIR and verification-plan IDs used.

## Current migration boundary

The existing legacy engine remains the financial authority by default. Native AIR compilation, packet persistence, verification planning, deterministic fact derivation, and safe semantic extraction now exist, but broad contract generality must be proven with cross-domain fixtures and real pilot agreements before AIR becomes the default financial authority.
