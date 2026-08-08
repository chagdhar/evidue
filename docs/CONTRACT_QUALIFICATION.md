# Contract qualification and Evidue verification kernel

Evidue has two different correctness problems and deliberately tests them separately:

1. **Contract interpretation** — an LLM proposes structured contract semantics from source documents.
2. **Financial adjudication** — only a human-approved Agreement IR (AIR) may drive deterministic invoice reconciliation.

A model response is never financial authority. Qualification measures the proposal and AIR before approval; reconciliation uses the approved AIR and customer evidence without requiring an LLM.

## Trust boundary

The live native compiler follows this path:

```text
raw contract bytes
  -> document-integrity / transport-decoding checks
  -> deterministic sentence-sized source spans
  -> independent atomic-requirement extraction
  -> deterministic requirement source binding
  -> AIR proposal pass constrained by the authoritative requirement ledger
  -> strict Pydantic + semantic validation
  -> deterministic requirement/AIR binding assurance
  -> Agreement IR lowering + assurance
  -> human approval / immutable AIR version
  -> deterministic evidence/fact evaluation
  -> payable / disputed / needs-review dollars
```

The model is never authoritative for source text, source offsets, or source hashes. It cites source span IDs; Evidue retrieves the original source bytes and calculates offsets/hashes itself. Fuzzy citation matching is not an acceptable provenance mechanism.

## Document integrity preflight

Qualification refuses to silently parse transport-compressed or obvious non-document content as a contract. The ingestion boundary:

- detects gzip by HTTP metadata or gzip magic bytes;
- supports deflate transport decoding;
- validates basic text readability;
- rejects obvious SEC/rate-limit/access-denied/captcha pages;
- records raw and decoded content hashes when fetched through the qualification source downloader.

This exists because a successful model call is meaningless if the bytes sent to the compiler were not actually the intended contract.

## Gold standards

A qualification pack may contain `gold.json`. Gold is an answer key controlled independently of the model output; it is **not** a previously generated AIR relabeled as truth.

Review status is explicit:

- `provisional_engineering_gold` — useful for engineering evaluation, but not independently reviewed and never sufficient for a release-level pass.
- `human_reviewed` — reviewed controlled truth. `qualification_passed=true` additionally requires `exhaustive_financial_terms=true`.

Gold can describe material source phrases, expected atomic-requirement kind and data dependencies, expected rule/settlement type, automation classification, numeric parameters, evidence facts, forbidden numeric interpretations, redacted/unknown parameters, required diagnostics, and terms that must remain non-executable.

### Hard safety gates

Aggregate scores must not hide financially dangerous errors. Qualification fails if it finds, among other things:

- unsupported/invented executable financial rules in an exhaustive gold set;
- executable semantics without valid source provenance;
- a critical expected numeric parameter mismatch;
- a critical redacted/unknown parameter that was assigned a numeric value;
- a critical term that gold requires to remain non-executable but the compiler automated;
- failed deterministic compiler assurance.

A high average score does not override a hard failure.

### Atomic completeness and qualification v3

Clause-level coverage is not sufficient: one source clause can contain several independently testable financial conditions. The native compiler therefore carries an atomic requirement ledger through AIR lowering. Qualification reports source recall, atomic-requirement recall, semantic fidelity, numeric-parameter fidelity, and automation fidelity separately. A term is not considered found merely because an unrelated rule cites the same clause.

See `docs/ATOMIC_REQUIREMENT_LEDGER.md` for the requirement-to-AIR binding and data-dependency gates.

## Redaction policy

Public executed agreements often redact precisely the parameters that matter. `[***]`, `[REDACTED]`, and equivalent omitted-confidential-information markers are unknown values.

The compiler prompt explicitly forbids inventing a missing rate, duration, percentage, threshold, date, party, or condition. Qualification gold can additionally mark a numeric parameter as `numeric_parameter_must_be_unknown` and `must_not_be_executable`.

The DemandTec/Target SEC pack intentionally contains several such hallucination traps, including a redacted cure period, annual fee, and payment window.

## Semantic stability

Repeated runs compare normalized material semantics rather than generated prose, clause IDs, ordering, or descriptions. The normalized snapshot includes rules, pricing, evidence requirements, and material coverage.

One run reports:

```text
semantic_stability.status = insufficient_runs
```

It never reports one successful run as evidence of stability. Stability is useful, but it is not correctness; correctness still requires gold or another independent oracle.

## Metamorphic / mutation tests

Qualification packs can declare contract mutations with both:

- `expected_changed_sections`
- `expected_unchanged_sections`

A valid mutation test does more than assert that output changed. For example, changing `$1.50` to `$1.75` should change the settlement/rule semantics while leaving unrelated evidence and coverage semantics unchanged. Collateral semantic drift is reported as a failure.

The controlled outcome-pricing pack contains rate, recontact-window, and downstream-window mutations intended for pinned live-provider qualification.

## Controlled contract-to-dollar benchmark

`qualification/fixtures/outcome-pricing-e2e` is a clearly synthetic controlled contract. It is not presented as customer data. It provides:

- source contract text;
- a source-bound native proposal for offline reproducibility;
- human-reviewed exhaustive gold;
- eight reviewed invoice/evidence scenarios with exact Decimal expectations;
- live metamorphic mutations.

Core/offline qualification executes the same native proposal -> AIR lowerer -> deterministic adjudicator used by the product. It checks exact status and payable/disputed/needs-review amounts and verifies financial conservation.

Run it:

```bash
PYTHONPATH=backend uv run python scripts/qualify_contract.py \
  --pack qualification/fixtures/outcome-pricing-e2e \
  --mode proposal \
  --proposal qualification/fixtures/outcome-pricing-e2e/proposal.json \
  --runs 1 \
  --output /tmp/evidue-synthetic-e2e.json
```

The recorded proposal is used only to make the core proof reproducible without network/model access. It does not substitute for live compiler qualification.

## Real executed-contract pack

`qualification/downloaded/sec-demandtec-target-2010` contains an SEC-filed executed SaaS master agreement plus embedded order form. The stored artifact has been transport-decoded and the manifest records both the originally received compressed-byte hash and decoded-content hash.

Its current gold is `provisional_engineering_gold` and non-exhaustive. Therefore a live run may measure structure, source grounding, critical-term behavior and hallucination traps, but it **cannot** honestly return release-level qualification until the gold is independently reviewed and made exhaustive where appropriate.

The earlier live result produced before the transport-decoding bug was discovered is invalid and must not be used as evidence.

## Provider-independent live qualification

Evidue owns inference credentials. Customers do not bring API keys. Server operators configure provider credentials in the deployment environment.

Examples:

```bash
export EVIDUE_LLM_PRIMARY=gemini
export GEMINI_API_KEY='...'
export GEMINI_MODEL='...'
```

or:

```bash
export EVIDUE_LLM_PRIMARY=openai
export OPENAI_API_KEY='...'
export OPENAI_MODEL='...'
```

Qualification pins the provider/model and disables fallback so repeated benchmark runs are interpretable:

```bash
PYTHONPATH=backend uv run python scripts/qualify_contract.py \
  --pack qualification/fixtures/outcome-pricing-e2e \
  --mode live \
  --provider gemini \
  --model "$GEMINI_MODEL" \
  --runs 3 \
  --mutations \
  --output /tmp/evidue-live-e2e.json
```

For the SEC pack:

```bash
PYTHONPATH=backend uv run python scripts/qualify_contract.py \
  --pack qualification/downloaded/sec-demandtec-target-2010 \
  --mode live \
  --provider gemini \
  --runs 1 \
  --output /tmp/evidue-sec.json \
  --exit-zero-on-review
```

`--exit-zero-on-review` means the execution completed successfully but review remains required. It does not convert provisional gold into a pass.

## One-command proof

Run the normal offline proof kernel with its Python quality-tool bootstrap:

```bash
./scripts/check-fast.sh
```

`evidue-proof.sh` remains the low-level runner used by the wrapper scripts.

This generates:

```text
artifacts/validation/latest.json
artifacts/validation/latest.md
```

The generated dossier reports measured results only. Unmeasured real-contract/live-provider claims are marked `NOT MEASURED` rather than inferred.

Run live provider qualification separately:

```bash
./scripts/evidue-proof.sh live --provider gemini --model "$GEMINI_MODEL"
```

For safe mechanical Python cleanup followed by the complete offline repository gate:

```bash
./scripts/fix-and-check.sh
```

For a complete offline repository gate (dependencies are bootstrapped automatically):

```bash
./scripts/check-all.sh
```

For the complete repository gate plus pinned live-provider qualification:

```bash
./scripts/check-release.sh --provider gemini --model "$GEMINI_MODEL"
```

`full` never calls an LLM provider. `release` is the explicit mode that adds live qualification, preventing external provider availability from being confused with deterministic product correctness.

## What qualification does not prove

Qualification does not prove that:

- engineering gold is legally correct;
- a synthetic scenario is customer validation;
- a stable model output is a correct model output;
- an identified dispute will be accepted by the vendor;
- an identified dispute is recovered savings;
- every future contract can be automated.

Uncertain or unsupported material semantics should block approval or require human review rather than being guessed.
