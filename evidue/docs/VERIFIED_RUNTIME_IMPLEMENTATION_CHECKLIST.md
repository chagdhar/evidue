# Verified Runtime — Implementation Checklist

Status of the verified runtime/product branch. `PASS` means implemented and covered by repository tests or product-smoke validation; environment-specific browser/package validation is recorded separately in release notes.

## Architecture

- [x] No vendor-name branches in the authoritative AIR runtime.
- [x] No contract-category branches in the authoritative AIR runtime.
- [x] LLM does not return invoice determinations or money.
- [x] Financial calculations use `Decimal`.
- [x] Missing evidence does not become false without explicit authoritative absence capability.
- [x] Conflicting evidence remains reviewable rather than silently resolved.
- [x] Approved source/AIR versions are immutable and historical runs pin their version.

## Compiler

- [x] Exact source span and source-text hash for every material clause.
- [x] Material clause coverage must be 100% for approval.
- [x] Proof requirements resolve to persisted atomic predicates.
- [x] Predicate canonical hashes are recomputed at approval.
- [x] Pricing/settlement terms retain precise clause provenance.
- [x] Compiler assurance exists and gates activation.
- [x] Generated missing-evidence boundary probes execute safely.
- [x] Deterministic semantic-constant mutation probes change fingerprints.
- [x] Non-deterministic/model-assisted semantics remain an explicit human-review boundary.

## Verification

- [x] Each proof requirement references one atomic predicate.
- [x] Capability planning is vendor-neutral and based on normalized evidence/event capabilities.
- [x] Absence capability requires an explicit complete-export assertion.
- [x] Verification plans are persisted/versioned.
- [x] Facts are keyed by predicate/evidence snapshot/version.
- [x] Original facts remain intact when human review metadata is added.

## Settlement and provenance

- [x] Norm evaluation happens before settlement.
- [x] Approved AIR is the authoritative adjudication path.
- [x] Every determination exposes applicable source clauses and decisive evidence.
- [x] `submitted = payable + disputed + needs_review` is enforced/tested.
- [x] Reconciliation runs are append-only and pin AIR/evidence plan versions.
- [x] Corrected invoice, dispute CSV, summary JSON, evidence package, and review report exports exist.

## Product usability

- [x] One-click sample workspace produces payable, disputed, and needs-review outcomes.
- [x] Contract input supports paste, TXT/Markdown, DOCX, and PDF.
- [x] Invoice CSV preview and arbitrary column mapping are supported.
- [x] Evidence CSV/JSON/JSONL import and completeness declaration are supported.
- [x] Identity matching/manual confirmation is available before adjudication.
- [x] Normal UI hides proof-planner/compiler plumbing under an Advanced section.
- [x] Workspace-scoped server storage and audit log are enforced.

## Delivery gate

Before release packaging run:

1. Ruff format/check.
2. Backend pytest suite.
3. `scripts/product-smoke.py`.
4. Frontend unit/build/E2E where the package registry is available.
5. `git diff --check`.
6. Verify archive excludes secrets, DBs, VCS metadata, caches, dependencies, and build output.
