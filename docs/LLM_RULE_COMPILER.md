# LLM contract rule compiler

Evidue separates contract interpretation from invoice adjudication.

## Control flow

1. The contract text is hashed and sent to Gemini with a closed list of supported deterministic operations.
2. Gemini returns only a JSON rule proposal. It never receives invoice claims or customer evidence.
3. Pydantic rejects unknown fields, unsupported operations, malformed windows, duplicate IDs, and invalid consequences.
4. The proposal is stored as `pending_approval` with model, prompt hash, source hash, and version metadata.
5. A human explicitly approves the proposal. Approval activates an immutable rule version.
6. Reconciliation loads only the active approved version and runs the generic deterministic interpreter.

## Supported operations

- `validate_evidence_envelope`
- `claim_datetime_in_range`
- `prohibit_event_within`
- `require_success_event_within`
- `prohibit_field_mismatch_event`
- `unique_first_claim_within`

The LLM cannot emit Python, SQL, JavaScript, or arbitrary expressions. Adding a new operator requires a reviewed code change and tests.

## Demo modes

`POST /api/contracts/current/compile?mode=auto`

- Uses a live Gemini call when `GEMINI_API_KEY` is set.
- Otherwise replays `demo-data/contract/recorded-gemini-rule-proposal.json` so the YC demo works offline.

`mode=live` requires a configured key. `mode=recorded` always uses the checked-in response.

The contract screen shows the source text, hashes, model, generated operations, parameters, evidence requirements, pending approval, and active version.
