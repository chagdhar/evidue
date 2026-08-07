# Contract compiler and deterministic dispute engine

## Safety boundary

Evidue uses an LLM only to translate natural-language billing clauses into a proposed, constrained rule program.
The proposal cannot execute code and cannot adjudicate invoice claims.

The runtime sequence is:

1. Read the contract text.
2. Ask Gemini for JSON using a response schema and temperature `0`.
3. Validate the proposal with strict Pydantic models.
4. Store the proposal as `pending_approval` with source and prompt SHA-256 hashes.
5. Require explicit approval, creating an immutable numbered version.
6. Load that approved version into the deterministic interpreter.
7. Evaluate customer-owned evidence and calculate payable, disputed, and needs-review amounts.

## Allowed operations

The model can select only these operations:

- `validate_evidence_envelope`
- `claim_datetime_in_range`
- `prohibit_event_within`
- `require_success_event_within`
- `prohibit_field_mismatch_event`
- `unique_first_claim_within`

Each operation has required parameters and validation constraints. Unknown operations, missing fields, invalid
window units, invalid dates, duplicate rule IDs, and duplicate priorities are rejected before approval.

## Demo modes

`POST /api/contracts/current/compile?mode=auto`

- Uses Gemini when `GEMINI_API_KEY` is configured.
- Falls back to the validated recorded proposal when the live call fails.
- Uses the recorded proposal immediately when no key is configured.

`POST /api/contracts/current/compile?mode=live`

- Requires a Gemini key.
- Returns an error if the live call fails.

`POST /api/contracts/current/compile?mode=recorded`

- Always loads the checked-in validated proposal.
- Makes the demo deterministic and usable offline.

`POST /api/contracts/current/compilations/{id}/approve`

- Replaces the active rule rows with the approved immutable version.
- Marks the current reconciliation stale.
- Requires reconciliation to be run again using the newly approved program.

## Source-of-truth guarantee

The checked-in contract terms are not duplicated as Python `if` statements. The interpreter branches only on
allowlisted operation names and reads windows, event types, field comparisons, grouping keys, ordering, and
consequences from the approved rule data. Changing an approved rule proposal changes the executed program
without editing the adjudication engine.
