# Contract Compiler Qualification

Evidue separates two correctness problems:

1. **Contract interpretation** — an LLM proposes structured Agreement IR (AIR) from source documents.
2. **Financial adjudication** — only a human-approved AIR is allowed to drive deterministic invoice reconciliation.

The normal automated test suite heavily covers the second problem. The qualification harness in
`backend/app/agreements/qualification.py` exists to make the first problem measurable against contracts
that were not designed around Evidue's demo fixtures.

## Safety boundary

A qualification run never makes an LLM response financial authority. The output is a candidate AIR plus
an evaluation report. Approval remains an explicit product action. Invoice-line adjudication continues to
run without an LLM.

Do not put expected qualification answers into compiler prompts or production runtime code. Gold labels
belong only in qualification packs.

## Qualification pack

A pack is a directory containing `manifest.json`, source documents, and optionally a `gold.json` file.
The manifest supports multiple documents, precedence metadata, document relations, effective dates, and
financially material mutation cases.

A gold standard records reviewer-controlled expected financial terms. Gold created by engineering before
an independent review must be marked `provisional_engineering_gold`; it must not be presented as an
independently validated score.

The scorer checks, among other things:

- critical financial-term recall;
- source grounding of executable rules and pricing policies;
- exact numeric parameter fidelity;
- expected rule type/consequence and automation classification;
- evidence-plan fact types;
- unsupported executable financial rules when the gold set is exhaustive;
- silent automation of subjective/manual clauses;
- deterministic compiler assurance.

For a human-reviewed exhaustive pack, the intended release gate is:

- 100% recall of critical financial terms;
- zero unsupported executable financial rules;
- zero ungrounded executable financial rules or pricing policies;
- zero critical numeric mismatches;
- zero silently automated subjective/manual terms.

A release-level `qualification_passed=true` additionally requires the gold set to be
`human_reviewed` **and** `exhaustive_financial_terms=true`. Provisional engineering gold,
partial gold, or no gold may still expose useful metrics, but the harness reports
`review_required` rather than claiming the contract is qualified.

A pack may also include `scenario_file` containing reviewer-controlled synthetic invoice
claims/evidence with expected payable/disputed/needs-review dollars. These scenarios execute
through the same deterministic AIR adjudicator as the pilot, proving the path from real
contract semantics to financial outcomes. Scenario expectations must be marked
`human_reviewed` before they can pass the scenario qualification gate.

## Live qualification

Never put `GEMINI_API_KEY` into a pack or command-line argument. Configure it only in the shell/server
environment.

```bash
GEMINI_API_KEY=... uv run python scripts/qualify_contract.py \
  --pack qualification/my-reviewed-pack \
  --mode live \
  --runs 3 \
  --mutations \
  --output /tmp/evidue-contract-qualification.json
```

`--runs 3` compares financial-semantic fingerprints rather than raw generated IDs. `--mutations` applies
contract mutations declared in the manifest and verifies that financially material source changes alter the
compiled financial policy.

For an ad-hoc real contract without a gold standard:

```bash
GEMINI_API_KEY=... uv run python scripts/qualify_contract.py \
  --document ORDER_FORM=/path/to/order-form.pdf \
  --document MSA=/path/to/msa.pdf \
  --customer "Acme" \
  --vendor "Vendor" \
  --runs 3
```

An ad-hoc run can prove parser/compiler execution, source grounding, assurance, and semantic stability. It
cannot honestly claim contract-interpretation accuracy until a reviewer creates a human-reviewed, exhaustive
gold standard. The command therefore returns a review-required qualification status rather than a pass.

## Public-source research packs

`qualification/public_sources.json` lists lawful public sources useful for generalization work. They are
source definitions, not baked-in expected answers and not part of the production runtime.

Download a source pack locally with:

```bash
python scripts/fetch_qualification_sources.py --pack intercom-fin-current
```

Downloaded third-party documents are intentionally ignored by Git. Review licensing/terms before
redistributing any downloaded source. Public product/help documentation must not be described as a signed
customer contract. The catalog distinguishes public commercial terms from public executed agreements.

## Effective-date boundary in the current pilot

The current pilot binds one approved AIR rule set to one configured reconciliation/agreement period.
If a governing amendment starts or ends *inside* that period, Evidue intentionally fails closed and asks
the operator to split the reconciliation into periods with one governing rule set each. This prevents a
mid-period amendment from being silently ignored or applied retroactively. Native temporal AIR selection
across multiple rule sets is a future capability and should not be simulated with one blended AIR.

## Human review workflow

For a real pilot, the strongest qualification is:

1. ingest the customer's redacted executed agreement/order form plus incorporated documents;
2. run live compilation at least three times;
3. have a finance/legal reviewer create or review the gold labels independently of compiler output;
4. fix generic AIR/compiler gaps rather than vendor-specific special cases;
5. approve the resulting AIR in `/pilot` only after comparing finance-readable rules with source clauses;
6. reconcile a synthetic invoice/evidence set derived from that real agreement and independently verify the
   expected dollar totals.

This establishes the complete path: **real contract semantics → approved structured policy → deterministic
dollars**.
