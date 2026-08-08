# Verification Kernel v3

## Purpose

Verification Kernel v3 prevents a structurally valid contract compilation from being mistaken for a complete or financially safe interpretation. The LLM remains an interpreter. Human approval remains the authority boundary. All invoice-line decisions and money calculations remain deterministic.

## Compiler pipeline

```text
contract bundle
  -> transport/text integrity checks
  -> immutable source spans
  -> atomic requirement ledger pass
  -> deterministic requirement source binding
  -> AIR proposal pass constrained by the ledger
  -> proposal schema + semantic validation
  -> bounded same-provider repair
  -> fail-closed artifact rejection when localized repair is exhausted
  -> deterministic AIR lowering
  -> atomic requirement binding/data-dependency assurance
  -> compiler assurance / optional independent compiler consensus
  -> human approval and immutable AIR version
  -> deterministic claim/evidence adjudication
  -> deterministic settlement
```

## Invariants

### Interpretation completeness

- One atomic requirement is one independently testable proposition.
- A single source sentence may yield multiple requirements.
- Material `and`, `or`, `unless`, `except`, timing, identity, exclusion, performance, and pricing semantics must not be collapsed into a generic executable rule when they can independently affect settlement.
- Every material requirement has exact source grounding and an explicit disposition.

### Executable binding

- A material `norm` requirement must bind to exactly one norm.
- A material `settlement` requirement must bind to exactly one settlement policy.
- Manual-review, unresolved-dependency, and non-operational requirements must not acquire executable financial semantics.
- Executable norms and settlement policies without a requirement binding are blocking.
- One executable artifact may not claim multiple independent atomic requirements.

### Data provenance

Requirement data classes are explicit:

- `claim`
- `invoice`
- `contract_constant`
- `batch_claims`
- `customer_evidence`
- `external_document`
- `human_attestation`

The lowerer independently derives the runtime data consumed by each condition. Direct claim/invoice/batch conditions cannot be made indeterminate by an unrelated downstream proof requirement. Conditions that consume customer evidence require a proof plan.

### Model failure behavior

- Invalid structured output is rejected by deterministic schema/semantic validation.
- Repairs are bounded and stay on the pinned provider/model for qualification.
- Exhausted localized norm/settlement repair removes the invalid executable artifact, emits a blocking diagnostic, and requires human review.
- The fail-closed path never invents replacement financial semantics.

### Approval

AIR approval requires deterministic conformance. Unmapped material atomic requirements block approval even if a diagnostic was accidentally omitted from a stored/intermediate AIR.

## Qualification v3

Qualification separates five questions that were previously conflated:

1. **Source recall** — is the reviewed source language represented?
2. **Atomic requirement recall** — is the independently testable requirement represented?
3. **Semantic fidelity** — does one specific requirement/artifact candidate match the reviewed norm/settlement meaning?
4. **Numeric parameter fidelity** — are reviewed rates/windows/thresholds preserved exactly (numeric-equivalent Decimal forms are accepted)?
5. **Automation fidelity** — is the automation class safe and expected?

Gold matching is candidate-specific. Two rules that share one source sentence cannot cross-credit each other's norm type, consequence, numeric parameter, proof plan, or automation class.

The controlled qualification gold also records expected atomic requirement kind and exact data-dependency classes where reviewed.

## Controlled proof

`qualification/fixtures/outcome-pricing-e2e` is synthetic, human-reviewed control data. It proves the offline path from recorded source-grounded proposal to AIR to exact deterministic dollars. It does not prove live-model quality or customer demand.

Current expected controlled totals:

- billed: `12.50`
- payable: `1.50`
- disputed: `8.00`
- needs review: `3.00`

Money conservation must hold exactly.

## Release commands

Normal development uses wrappers rather than a pasted sequence of commands:

```bash
./scripts/check-fast.sh
./scripts/check-all.sh
```

`check-all.sh` bootstraps dependencies and runs the complete offline repository gate. It never invokes an LLM provider.

Live provider qualification is explicit:

```bash
./scripts/check-live.sh --provider gemini --model "$GEMINI_MODEL"
./scripts/check-release.sh --provider gemini --model "$GEMINI_MODEL"
```

The release wrapper adds live qualification to the complete offline gate. Customers never supply provider API keys; these commands use server/operator deployment credentials.

## Non-claims

This architecture does not claim that software can prove legal interpretation correctness. It makes omissions, unsafe mappings, structural failures, data-source mistakes, and financial behavior more measurable and fail-closed. Human approval and reviewed qualification gold remain necessary trust boundaries.
