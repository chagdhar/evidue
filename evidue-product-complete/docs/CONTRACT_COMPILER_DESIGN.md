# Contract compiler design

## Non-negotiable boundary

The model is a compiler, not an adjudicator. It proposes a structured rule program. Pydantic validates it, a human approves an immutable version, and the deterministic engine alone evaluates evidence and money.

## Implemented compiler improvements

### Strict operation schemas

Every supported deterministic operation has required and optional parameters. Unknown parameters are rejected instead of being silently ignored. Window values, time units, string lists, comparisons, normalizers, and billing-period bounds receive operation-specific validation.

### Contract metadata grounding

The compiler receives explicit customer, vendor, billing-period, and price metadata. Billing-period rules must use those supplied values instead of inferring dates from unrelated text.

### Clause-by-clause coverage

The model must return `clause_coverage` for material billing, exclusion, evidence, timing, duplication, attribution, and pricing clauses:

- `compiled`: represented by one or more executable rule IDs;
- `needs_review`: material but ambiguous or unsupported;
- `not_applicable`: administrative language that does not affect billing eligibility.

Every executable rule must be referenced by clause coverage. Material clauses may not disappear silently.

### Machine-readable diagnostics

Diagnostics contain a code, severity, message, source clause, and suggested action. A `needs_review` clause requires a corresponding blocking diagnostic. Blocking diagnostics make the compilation non-approvable.

### Approval enforcement

The API exposes `approval_ready`, diagnostics, clause coverage, and the blocking count. Both the pilot and demo approval paths refuse to approve a compilation with unresolved coverage. `to_rule_program` also refuses to produce an executable program from a blocked proposal, providing defense in depth.

## Supported operations

- `validate_evidence_envelope`
- `claim_datetime_in_range`
- `claim_amount_equals`
- `prohibit_event_within`
- `require_success_event_within`
- `prohibit_field_mismatch_event`
- `unique_first_claim_within`

## Adding a new operation

A new operation is allowed only after a real contract demonstrates the need. It requires:

1. an exact deterministic semantic definition;
2. parameter schema and range validation;
3. compiler prompt and response-schema support;
4. deterministic engine implementation;
5. unit and integration tests;
6. rule/compiler version changes;
7. backward-compatibility consideration.

## Explicitly unsupported compiler behavior

The compiler must not perform semantic claim scoring, probabilistic payable decisions, external API calls, fuzzy evidence matching, or discretionary financial judgments. Such terms remain blocking until converted into an approved deterministic policy.
