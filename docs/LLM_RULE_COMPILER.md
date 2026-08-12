# LLM contract rule compiler

Evidue separates contract interpretation from invoice adjudication.

## Product compiler

The protected `/workspace` product uses the provider-independent native Agreement IR compiler described in
[`CONTRACT_COMPILER.md`](CONTRACT_COMPILER.md):

1. Evidue deterministically segments original contract documents into immutable source spans.
2. A server-owned LLM provider proposes constrained contractual semantics and cites those span IDs.
3. Evidue validates the proposal, retrieves the original source text itself, attaches offsets/hashes, and lowers it into Agreement IR (AIR).
4. Compiler assurance/conformance runs before approval. An optional independent assurance provider can block approval when material semantics disagree.
5. A human explicitly approves an immutable AIR version.
6. Reconciliation loads only the approved AIR and runs deterministic adjudication. No LLM decides payable/disputed/needs-review or calculates final payable dollars.

Customers never provide LLM credentials. Gemini/OpenAI credentials are deployment secrets owned by Evidue.

## Legacy demo compiler

The repository also retains an older, narrow rule-program compiler for the public technical demo and migration comparison. It supports these closed deterministic operations:

- `validate_evidence_envelope`
- `claim_datetime_in_range`
- `prohibit_event_within`
- `require_success_event_within`
- `prohibit_field_mismatch_event`
- `unique_first_claim_within`

The model cannot emit Python, SQL, JavaScript, or arbitrary expressions. Adding a new operator requires a reviewed code change and tests.

`POST /api/contracts/current/compile?mode=auto` is this **legacy demo path**:

- a developer/operator may configure the server-side Gemini credential for a live demo call;
- otherwise the route replays `demo-data/contract/recorded-gemini-rule-proposal.json` so the public technical preview works offline.

Do not use the legacy demo compiler as the production contract-authority path. New product work should use `/api/pilot/contracts/{contract_id}/compile-native` and approved AIR versions.
