# Verified Contract Runtime — Design Index

These RFCs were the design baseline for the verified runtime now implemented in the product branch. The current repository includes native AIR compilation, exact source binding, first-class atomic predicates, persisted/immutable AIR versions, agreement packets, compiler assurance, automatic verification planning, deterministic facts, semantic fact review boundaries, generic AIR adjudication, deterministic settlement, clause-to-dollar provenance, and optional legacy/AIR comparison.

The design rationale is preserved in these RFCs:

1. [`RFC 001 — Canonical Contract Graph`](rfcs/RFC_001_CANONICAL_CONTRACT_GRAPH.md)
   - one persisted typed semantic graph;
   - source-bound clauses, definitions, norms, atomic predicates, proof requirements, settlement rules;
   - derived legal/proof/settlement views rather than duplicated IR stores.

2. [`RFC 002 — Compiler Assurance`](rfcs/RFC_002_COMPILER_ASSURANCE.md)
   - deterministic grounding and coverage;
   - semantic critique;
   - bidirectional equivalence;
   - metamorphic contract mutations;
   - generated execution probes;
   - approval hard gates.

3. [`RFC 003 — Verification Planner and Fact Runtime`](rfcs/RFC_003_VERIFICATION_FACT_RUNTIME.md)
   - capability-based proof planning;
   - normalized observations;
   - four-valued facts;
   - fact caching and incremental invalidation;
   - safe semantic/human facts.

4. [`RFC 004 — Settlement and Provenance`](rfcs/RFC_004_SETTLEMENT_AND_PROVENANCE.md)
   - separate deterministic settlement DAG;
   - Decimal-only money;
   - clause-to-dollar trace.

5. [`RFC 005 — Migration and Test Strategy`](rfcs/RFC_005_MIGRATION_AND_TEST_STRATEGY.md)
   - branch order;
   - cross-domain corpus;
   - metamorphic/property tests;
   - performance and cutover gates.

6. [`RFC 006 — Data Model and API Migration`](rfcs/RFC_006_DATA_MODEL_AND_API_MIGRATION.md)
   - concrete table projections;
   - assurance/fact/observation persistence;
   - APIs and service boundaries;
   - shadow migration and rollback.

Current implementation status: [`VERIFIED_RUNTIME_IMPLEMENTATION_CHECKLIST.md`](VERIFIED_RUNTIME_IMPLEMENTATION_CHECKLIST.md). Post-core expansion: [`NEXT_BUILD.md`](NEXT_BUILD.md).

## Architectural thesis

Evidue should not trust one LLM to understand a contract and should not trust a second LLM to judge the first.

The system should compile a source-bound semantic graph, subject it to independent deterministic and semantic assurance, generate executable boundary tests, derive atomic facts from authoritative evidence, and only then calculate settlement deterministically.

That is the architecture now used by the protected product path: model-assisted proposal, human-approved immutable AIR, deterministic evidence evaluation, and deterministic financial settlement.
