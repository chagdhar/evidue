"""Native contract-language to AgreementCompilationProposal compiler.

The LLM is constrained to the semantic proposal schema. A deterministic source
binder validates model-selected immutable source-span IDs, retrieves the original
contract text itself, and attaches hashes before lowering into executable AIR.
"""

from __future__ import annotations

import json
import re
from copy import deepcopy
from dataclasses import dataclass
from hashlib import sha256
from itertools import pairwise
from typing import Any

from pydantic import ValidationError

from app.contracts.compiler import load_recorded_proposal, sha256_text

from .compiler_models import (
    AgreementCompilationProposal,
    AtomicRequirementProposal,
    ClauseAnalysisProposal,
    ConditionProposal,
    DiagnosticProposal,
    NormProposal,
    ProofRequirementProposal,
    RequirementLedgerProposal,
    SettlementProposal,
    SourceDocumentRef,
)
from .providers import (
    ProviderError,
    ProviderResult,
    call_provider,
    canonical_provider_name,
    compilation_provenance,
)

NATIVE_COMPILER_VERSION = "native-air-0.5"
NATIVE_PROMPT_VERSION = "native-air-prompt-0.5"
REQUIREMENT_LEDGER_VERSION = "atomic-requirements-0.1"
MAX_SEMANTIC_REPAIRS = 2

_SEMANTIC_PARAMETER_CONTRACT = r"""
STRICT SEMANTIC PARAMETER CONTRACT:
- field_present.parameters = {"field": ...}
- field_equals.parameters = {"field": ..., "expected_value": ...}; never use "value".
- field_in_set.parameters = {"field": ..., "values": [..]} with a non-empty values list.
- datetime_in_range.parameters = {"field": ..., "start": ..., "end_exclusive": ...}.
- amount_equals.parameters = {"field": ..., "expected_amount": ...}.
- event_exists/event_absent require a non-empty "event_types" list.
- event_within_window requires event_types, anchor_field, window_value, and window_unit.
- all_of/any_of/none_of.parameters.conditions MUST be a non-empty JSON array of full
  condition objects, each with condition_type, parameters, and description. Never place
  strings, IDs, or prose in conditions.
- fixed_per_unit settlement requires an explicit unit_price present in the supplied source.
- rate_table settlement requires an explicit lookup_field and a non-empty rates object present
  in the supplied source.
- tiered_rate requires an explicit non-empty tiers list.
- percentage requires an explicit percent; cap requires maximum; floor requires minimum;
  deduction requires amount.
- If the agreement delegates a price/rate to a missing Order Form, SOW, exhibit, schedule,
  or redacted text, DO NOT create a partially parameterized settlement effect and DO NOT
  guess the missing value. Leave settlement_effects empty for that clause, classify the
  clause as human_attestation_required or unsupported as appropriate, record the missing
  concept in unsupported_concepts, and emit a diagnostic.
- If a contractual obligation cannot be expressed with the allowed deterministic condition
  vocabulary using parameters explicitly supported by the source, DO NOT invent event types
  or claim fields. Keep it non-executable/review-required and emit a diagnostic.
- proof_requirements.missing_evidence_result MUST be exactly "unknown".
- "needs_review" is a financial/adjudication consequence, not a TruthValue. If missing
  evidence should send the invoice line to review, use the enclosing norm's
  indeterminate_consequence="needs_review".
- proof_requirements.preferred_authority is an AUTHORITY CLASS, not a system name,
  event type, database name, log type, or evidence-source identifier.
- preferred_authority MUST be exactly one of:
    customer_system_of_record
    independent_third_party
    signed_execution_log
    vendor_tool_trace
- For example, "system_audit_log", "zendesk", "salesforce", "refund_event", and
  "transaction_log" are NOT authority values. Represent those concepts through
  fact_types, entity_type, required_fields, descriptions, or evidence-source
  capabilities instead.
- requirement_ids bind executable artifacts to the authoritative atomic requirement ledger.
- Every executable norm MUST bind to exactly one atomic requirement. Never merge multiple
  independent requirements into one generic norm merely because they share a source clause.
- Every settlement effect MUST bind to exactly one pricing requirement.
- Conditions based only on normalized claim/invoice fields MUST NOT have proof requirements.
- Conditions that consume downstream operational events MUST declare proof requirements.
- duplicate_in_window is evaluated from the invoice/batch claim set and MUST NOT require
  downstream evidence proof.
"""


@dataclass(frozen=True)
class NativeCompilationResult:
    proposal: AgreementCompilationProposal
    prompt_hash: str
    raw_response: dict[str, Any]
    live_model_call: bool
    model: str
    provider: str
    provenance: dict[str, Any]


def _proposal_schema() -> dict[str, Any]:
    """Return the schema used for live structured model output."""

    schema = AgreementCompilationProposal.model_json_schema()

    clause_schema = schema.get("$defs", {}).get("ClauseAnalysisProposal")
    if clause_schema is None:
        raise ValueError("ClauseAnalysisProposal missing from generated response schema")

    required = clause_schema.setdefault("required", [])

    if "source_span_ids" not in required:
        required.append("source_span_ids")

    return schema


def _requirement_schema() -> dict[str, Any]:
    """Return the strict schema for the independent requirement-decomposition pass."""

    schema = RequirementLedgerProposal.model_json_schema()
    requirement_schema = schema.get("$defs", {}).get("AtomicRequirementProposal")
    if requirement_schema is None:
        raise ValueError("AtomicRequirementProposal missing from requirement schema")
    required = requirement_schema.setdefault("required", [])
    if "source_span_ids" not in required:
        required.append("source_span_ids")
    return schema


@dataclass(frozen=True)
class SourceSpan:
    """Exact immutable span from an original contract document."""

    span_id: str
    document_id: str
    ordinal: int
    start: int
    end: int
    text: str


_SOURCE_SPAN_MAX_CHARS = 700
_SOURCE_SPAN_MAX_PER_CLAUSE = 6


def _split_source_line(
    text: str,
    start: int,
    end: int,
) -> list[tuple[int, int]]:
    """Split source text into sentence-sized immutable spans with exact offsets."""

    while start < end and text[start].isspace():
        start += 1
    while end > start and text[end - 1].isspace():
        end -= 1
    if start >= end:
        return []

    # Prefer sentence boundaries because atomic contractual requirements often
    # correspond to individual sentences even when PDF/HTML extraction places
    # an entire paragraph on one physical line. Long sentences are still split
    # deterministically by the bounded-size fallback below.
    sentence_ranges: list[tuple[int, int]] = []
    cursor = start
    for match in re.finditer(r"(?<=[.!?])\s+(?=[A-Z0-9])", text[start:end]):
        candidate_end = start + match.start()
        if cursor < candidate_end:
            sentence_ranges.append((cursor, candidate_end))
        cursor = start + match.end()
    if cursor < end:
        sentence_ranges.append((cursor, end))

    ranges: list[tuple[int, int]] = []
    for sentence_start, sentence_end in sentence_ranges:
        cursor = sentence_start
        while cursor < sentence_end:
            candidate_end = min(cursor + _SOURCE_SPAN_MAX_CHARS, sentence_end)
            if candidate_end < sentence_end:
                minimum_break = cursor + (_SOURCE_SPAN_MAX_CHARS // 2)
                break_at = text.rfind(" ", minimum_break, candidate_end)
                if break_at > cursor:
                    candidate_end = break_at

            chunk_start = cursor
            chunk_end = candidate_end
            while chunk_start < chunk_end and text[chunk_start].isspace():
                chunk_start += 1
            while chunk_end > chunk_start and text[chunk_end - 1].isspace():
                chunk_end -= 1
            if chunk_start < chunk_end:
                ranges.append((chunk_start, chunk_end))
            cursor = candidate_end
            while cursor < sentence_end and text[cursor].isspace():
                cursor += 1

    return ranges


def _build_source_spans(
    source_documents: dict[str, tuple[str, str]],
) -> dict[str, SourceSpan]:
    """Create deterministic citable spans from original contract text."""

    spans: dict[str, SourceSpan] = {}
    global_index = 1

    for document_id, (_, source_text) in source_documents.items():
        ordinal = 0
        offset = 0

        for raw_line in source_text.splitlines(keepends=True):
            line_start = offset
            line_end = offset + len(raw_line)
            offset = line_end

            for start, end in _split_source_line(
                source_text,
                line_start,
                line_end,
            ):
                ordinal += 1
                span_id = f"SPAN-{global_index:06d}"

                spans[span_id] = SourceSpan(
                    span_id=span_id,
                    document_id=document_id,
                    ordinal=ordinal,
                    start=start,
                    end=end,
                    text=source_text[start:end],
                )

                global_index += 1

        if ordinal == 0 and source_text.strip():
            start = len(source_text) - len(source_text.lstrip())
            end = len(source_text.rstrip())

            span_id = f"SPAN-{global_index:06d}"

            spans[span_id] = SourceSpan(
                span_id=span_id,
                document_id=document_id,
                ordinal=1,
                start=start,
                end=end,
                text=source_text[start:end],
            )

            global_index += 1

        if ordinal == 0 and not source_text.strip():
            raise ValueError(f"Source document {document_id} contains no citable text")

    return spans


def _render_source_documents_with_spans(
    source_documents: dict[str, tuple[str, str]],
) -> str:
    spans = _build_source_spans(source_documents)
    sections: list[str] = []

    for document_id, (title, _) in source_documents.items():
        rendered_spans = [span for span in spans.values() if span.document_id == document_id]

        body = "\n\n".join(f"[{span.span_id}]\n{span.text}" for span in rendered_spans)

        sections.append(f"DOCUMENT_ID: {document_id}\nTITLE: {title}\n---\n{body}")

    return "\n\n".join(sections)


def build_requirement_ledger_prompt(
    *,
    contract_id: str,
    source_documents: dict[str, tuple[str, str]],
    metadata: dict[str, str],
) -> str:
    document_block = _render_source_documents_with_spans(source_documents)
    return f"""You are Evidue's independent atomic-contract-requirement analyzer.

You do NOT produce executable rules and you do NOT decide invoice outcomes. Your only
job is to identify every indivisible contractual requirement that could matter to
financial reconciliation or evidence sufficiency.

ATOMICITY RULES:
1. One requirement = one independently testable contractual proposition.
2. If a sentence contains AND/OR/UNLESS/EXCEPT/PROVIDED THAT/ONLY IF and each branch can
   independently change whether an amount is payable, emit separate requirements.
3. Never collapse several exclusions, timing windows, identity checks, or performance
   conditions into a generic summary requirement.
4. Pricing and validation are separate when both are present: a rate is a settlement
   requirement; an invoice/claim amount check is a norm requirement.
5. Preserve every explicit numeric value exactly. Never infer redacted or omitted values.

DATA DEPENDENCY CLASSIFICATION:
- claim: normalized invoice-line/claim fields such as billed amount, service timestamp,
  account ID, outcome ID, or expected action.
- invoice: invoice-level metadata not belonging to a single claim.
- contract_constant: literal rate/date/window/threshold supplied by the contract.
- batch_claims: cross-claim comparisons such as uniqueness or duplicate attribution.
- customer_evidence: downstream operational events or customer systems of record.
- external_document: a referenced Order Form/SOW/exhibit/schedule that is not available.
- human_attestation: a fact that cannot be objectively established from available systems.
Do not label direct claim/invoice checks as customer_evidence merely because evidence exists
elsewhere in the contract.

DISPOSITION:
- norm: deterministic eligibility/performance/exclusion/timing/identity rule.
- settlement: explicit, fully parameterized pricing/amount calculation.
- manual_review: material requirement requiring human judgment.
- unresolved_dependency: material requirement whose referenced/redacted parameter is absent.
- non_operational: source language not used in reconciliation.

SOURCE GROUNDING:
- Every requirement MUST cite source_span_ids supplied below.
- Use only span IDs from the requirement's source_document_id.
- Up to {_SOURCE_SPAN_MAX_PER_CLAUSE} consecutive spans may support one requirement.
- source_text is informational; Evidue will replace it with exact source bytes.
- Set source_start/source_end/source_text_hash to null; Evidue computes them.

CONTRACT_ID: {contract_id}
METADATA: {json.dumps(metadata, sort_keys=True)}
LEDGER_VERSION: {REQUIREMENT_LEDGER_VERSION}

SOURCE DOCUMENTS:
{document_block}

Return only JSON matching the supplied requirement-ledger response schema.
"""


def build_native_compiler_prompt(
    *,
    contract_id: str,
    source_documents: dict[str, tuple[str, str]],
    metadata: dict[str, str],
    requirements: list[AtomicRequirementProposal] | None = None,
) -> str:
    document_block = _render_source_documents_with_spans(source_documents)
    requirement_block = json.dumps(
        [item.model_dump(mode="json") for item in requirements or []],
        indent=2,
        sort_keys=True,
    )

    return f"""You are Evidue's contract clause-analysis compiler.

Your output is a proposal for deterministic lowering. You DO NOT decide whether
an invoice claim is payable and you DO NOT calculate a final payable amount.

SOURCE GROUNDING:
1. Every material clause MUST cite source_span_ids.
2. Use only SPAN IDs supplied below.
3. Every cited span must belong to the clause's source_document_id.
4. A clause may cite up to {_SOURCE_SPAN_MAX_PER_CLAUSE} consecutive spans.
5. Never invent a SPAN ID.
6. source_text is informational only. Evidue will replace it with the exact
   original source bytes selected by source_span_ids.
7. Set source_start, source_end, and source_text_hash to null. Evidue computes
   them deterministically.

CONTRACT INTERPRETATION:
8. Analyze every material commercial clause.
9. Never invent a rate, observation window, threshold, exception, party,
   effective date, definition, or commercial condition.
10. If a material concept cannot be safely represented, classify it as
    unsupported or human_attestation_required and emit an appropriate
    diagnostic.
11. Only explicit, fully parameterized pricing terms belong in settlement_effects.
    If a price/rate is delegated to a missing document or redacted, do not fabricate a
    settlement effect. Performance requirements belong in norms only when representable
    with the allowed deterministic vocabulary.
12. Missing evidence at the proof/fact layer must resolve to "unknown"; it must
    never silently prove satisfaction or breach. "needs_review" is NOT a truth
    value. When an indeterminate norm should cause financial review, express that
    with norm.indeterminate_consequence="needs_review".
13. Proof requirements describe facts needed from external evidence, not vendor
    product names.
14. Do not create proof requirements for data already present on normalized
    invoice claims.
15. Respect document precedence, effective dates, amendments, supersession,
    and incorporation relationships supplied in METADATA.
16. If precedence is ambiguous, require human review rather than guessing.
17. Subjective standards must not become deterministic predicates unless the
    agreement defines an objective test.
18. Preserve negation and exceptions exactly, including unless, except,
    only if, and not payable.
19. Treat redaction markers such as [***], [REDACTED], or omitted-confidential
    language as UNKNOWN. Never reconstruct, infer, or guess a missing rate, date,
    duration, percentage, threshold, party, or condition. If the missing value is
    financially material, keep the clause non-executable and emit a blocking or
    review diagnostic instead of parameterizing it.
20. Do not emit executable code or arbitrary expression trees.

{_SEMANTIC_PARAMETER_CONTRACT}

CONTRACT_ID: {contract_id}
METADATA: {json.dumps(metadata, sort_keys=True)}
COMPILER_VERSION: {NATIVE_COMPILER_VERSION}
PROMPT_VERSION: {NATIVE_PROMPT_VERSION}

AUTHORITATIVE ATOMIC REQUIREMENT LEDGER:
{requirement_block}

REQUIREMENT BINDING:
21. The requirement ledger above was produced by an independent pass. Do not add, remove,
    merge, split, or rewrite those requirements.
22. Bind every executable norm and settlement_effect to requirement_ids from that ledger.
23. Every financial/operational requirement whose disposition is norm or settlement must be
    implemented exactly once. If you cannot safely implement it with the allowed vocabulary,
    leave it unmapped and emit a blocking diagnostic; do not invent substitute semantics.
24. A norm may bind to only one atomic requirement. A settlement effect may bind to only one
    atomic requirement.
25. Match each requirement's declared data_dependencies. Direct claim/invoice checks do not
    get proof requirements; customer_evidence conditions do; batch_claim uniqueness does not.

SOURCE DOCUMENTS:
{document_block}

Return only JSON matching the supplied response schema.
"""


def _find_exact_span(
    text: str,
    clause_text: str,
    *,
    hinted_start: int | None = None,
) -> tuple[int, int]:
    """Ground an LLM quote without allowing paraphrase.

    Exact matches are preferred. As a concession to document-layout artifacts,
    a quote may differ only in runs of whitespace (spaces, tabs, newlines,
    non-breaking spaces). The returned offsets always point into the original
    source text.

    No case folding, punctuation normalization, edit-distance matching, or
    semantic/fuzzy matching is allowed.
    """

    exact_matches = list(re.finditer(re.escape(clause_text), text))
    if len(exact_matches) == 1:
        return exact_matches[0].span()

    if len(exact_matches) > 1:
        if hinted_start is not None:
            hinted = next(
                (match for match in exact_matches if match.start() == hinted_start),
                None,
            )
            if hinted is not None:
                return hinted.span()

        raise ValueError(
            "Proposed source_text occurs more than once in the source document; "
            "the source location is ambiguous"
        )

    stripped = clause_text.strip()
    if not stripped:
        raise ValueError("Proposed source_text is empty after trimming whitespace")

    pieces = re.split(r"(\s+)", stripped)
    pattern = "".join(r"\s+" if piece.isspace() else re.escape(piece) for piece in pieces if piece)

    layout_matches = list(re.finditer(pattern, text))

    if len(layout_matches) == 1:
        return layout_matches[0].span()

    if len(layout_matches) > 1:
        if hinted_start is not None:
            hinted = next(
                (match for match in layout_matches if match.start() == hinted_start),
                None,
            )
            if hinted is not None:
                return hinted.span()

        raise ValueError(
            "Proposed source_text has multiple whitespace-equivalent matches; "
            "the source location is ambiguous"
        )

    raise ValueError(
        "Proposed source_text is not an exact substring of the source document, "
        "even after layout-only whitespace normalization"
    )


def bind_proposal_to_sources(
    proposal: AgreementCompilationProposal,
    *,
    expected_contract_id: str,
    source_documents: dict[str, tuple[str, str]],
    require_source_spans: bool = False,
) -> AgreementCompilationProposal:
    """Attach authoritative source provenance to every proposed clause."""

    if proposal.contract_id != expected_contract_id:
        raise ValueError(
            f"Proposal contract_id {proposal.contract_id!r} does not match {expected_contract_id!r}"
        )

    known_documents = set(source_documents)

    proposal_document_ids = {item.document_id for item in proposal.source_documents}

    unknown = proposal_document_ids - known_documents

    if unknown:
        raise ValueError(f"Proposal references unknown source documents: {sorted(unknown)}")

    span_index = _build_source_spans(source_documents)
    bound_clauses: list[ClauseAnalysisProposal] = []

    for clause in proposal.clauses:
        if clause.source_document_id not in source_documents:
            raise ValueError(
                f"Clause {clause.clause_id} references unknown document {clause.source_document_id}"
            )

        _, source_text = source_documents[clause.source_document_id]

        if clause.source_span_ids:
            selected: list[SourceSpan] = []

            for span_id in clause.source_span_ids:
                span = span_index.get(span_id)

                if span is None:
                    raise ValueError(
                        f"Clause {clause.clause_id} references unknown source span {span_id}"
                    )

                if span.document_id != clause.source_document_id:
                    raise ValueError(
                        f"Clause {clause.clause_id} cites {span_id} from "
                        f"{span.document_id}, not "
                        f"{clause.source_document_id}"
                    )

                selected.append(span)

            if len(selected) > _SOURCE_SPAN_MAX_PER_CLAUSE:
                raise ValueError(f"Clause {clause.clause_id} cites too many source spans")

            ordinals = [span.ordinal for span in selected]

            if ordinals != sorted(ordinals):
                raise ValueError(
                    f"Clause {clause.clause_id} source spans are not in document order"
                )

            if any(current != previous + 1 for previous, current in pairwise(ordinals)):
                raise ValueError(f"Clause {clause.clause_id} source spans must be consecutive")

            start = selected[0].start
            end = selected[-1].end

            canonical_source_text = source_text[start:end]

        else:
            if require_source_spans:
                raise ValueError(f"Clause {clause.clause_id} omitted source_span_ids")

            # Backward compatibility for recorded/offline proposals.
            start, end = _find_exact_span(
                source_text,
                clause.source_text,
                hinted_start=clause.source_start,
            )

            canonical_source_text = source_text[start:end]

        text_hash = sha256(canonical_source_text.encode("utf-8")).hexdigest()

        bound_clauses.append(
            clause.model_copy(
                update={
                    "source_text": canonical_source_text,
                    "source_start": start,
                    "source_end": end,
                    "source_text_hash": text_hash,
                }
            )
        )

    expected_documents = [
        SourceDocumentRef(
            document_id=document_id,
            title=title,
        )
        for document_id, (title, _) in source_documents.items()
    ]

    bound_requirements = proposal.requirements
    if proposal.requirements:
        requirement_ledger = bind_requirement_ledger_to_sources(
            RequirementLedgerProposal(
                ledger_version=REQUIREMENT_LEDGER_VERSION,
                contract_id=expected_contract_id,
                requirements=proposal.requirements,
            ),
            expected_contract_id=expected_contract_id,
            source_documents=source_documents,
            require_source_spans=require_source_spans,
        )
        bound_requirements = requirement_ledger.requirements

    return proposal.model_copy(
        update={
            "contract_id": expected_contract_id,
            "source_documents": expected_documents,
            "requirements": bound_requirements,
            "clauses": bound_clauses,
        }
    )


def bind_requirement_ledger_to_sources(
    ledger: RequirementLedgerProposal,
    *,
    expected_contract_id: str,
    source_documents: dict[str, tuple[str, str]],
    require_source_spans: bool = True,
) -> RequirementLedgerProposal:
    """Bind every atomic requirement to immutable original source bytes."""

    if ledger.contract_id != expected_contract_id:
        raise ValueError(
            f"Requirement ledger contract_id {ledger.contract_id!r} does not match "
            f"{expected_contract_id!r}"
        )
    span_index = _build_source_spans(source_documents)
    bound: list[AtomicRequirementProposal] = []
    for requirement in ledger.requirements:
        if requirement.source_document_id not in source_documents:
            raise ValueError(
                f"Requirement {requirement.id} references unknown document "
                f"{requirement.source_document_id}"
            )
        if require_source_spans and not requirement.source_span_ids:
            raise ValueError(f"Requirement {requirement.id} omitted source_span_ids")

        selected: list[SourceSpan] = []
        for span_id in requirement.source_span_ids:
            span = span_index.get(span_id)
            if span is None:
                raise ValueError(
                    f"Requirement {requirement.id} references unknown source span {span_id}"
                )
            if span.document_id != requirement.source_document_id:
                raise ValueError(
                    f"Requirement {requirement.id} cites {span_id} from {span.document_id}, "
                    f"not {requirement.source_document_id}"
                )
            selected.append(span)

        if selected:
            if len(selected) > _SOURCE_SPAN_MAX_PER_CLAUSE:
                raise ValueError(f"Requirement {requirement.id} cites too many source spans")
            ordinals = [span.ordinal for span in selected]
            if ordinals != sorted(ordinals):
                raise ValueError(
                    f"Requirement {requirement.id} source spans are not in document order"
                )
            if any(current != previous + 1 for previous, current in pairwise(ordinals)):
                raise ValueError(f"Requirement {requirement.id} source spans must be consecutive")
            _, document_text = source_documents[requirement.source_document_id]
            start = selected[0].start
            end = selected[-1].end
            source_text = document_text[start:end]
        else:
            _, document_text = source_documents[requirement.source_document_id]
            start, end = _find_exact_span(
                document_text,
                requirement.source_text,
                hinted_start=requirement.source_start,
            )
            source_text = document_text[start:end]

        bound.append(
            requirement.model_copy(
                update={
                    "source_text": source_text,
                    "source_start": start,
                    "source_end": end,
                    "source_text_hash": sha256(source_text.encode("utf-8")).hexdigest(),
                }
            )
        )

    return ledger.model_copy(
        update={
            "ledger_version": REQUIREMENT_LEDGER_VERSION,
            "contract_id": expected_contract_id,
            "requirements": bound,
        }
    )


def _requirement_payload_for_validation(
    result: ProviderResult,
    *,
    contract_id: str,
) -> dict[str, Any]:
    payload = dict(result.payload)
    payload.update(
        {
            "ledger_version": REQUIREMENT_LEDGER_VERSION,
            "contract_id": contract_id,
        }
    )
    return payload


def _validate_requirement_ledger(
    *,
    initial_result: ProviderResult,
    contract_id: str,
    original_prompt: str,
    schema: dict[str, Any],
    requested_provider: str | None,
    api_key: str | None,
    timeout_seconds: int,
    max_retries: int,
) -> tuple[RequirementLedgerProposal, ProviderResult, dict[str, Any]]:
    """Validate the independent requirement pass with one bounded structural repair."""

    result = initial_result
    history: list[dict[str, Any]] = []
    for repair_count in range(2):
        payload = _requirement_payload_for_validation(result, contract_id=contract_id)
        try:
            ledger = RequirementLedgerProposal.model_validate(payload)
        except ValidationError as exc:
            issues = _validation_error_summary(exc)
            history.append({"attempt": repair_count + 1, "issues": issues})
            if repair_count == 1:
                raise ValueError(
                    "Model output failed atomic requirement-ledger validation after "
                    f"1 repair attempt: {issues}"
                ) from exc
            repair_prompt = f"""{original_prompt}

ATOMIC REQUIREMENT LEDGER REPAIR
Your previous requirement JSON failed deterministic structural validation. Return a COMPLETE
replacement ledger. Repair structure only; do not invent contractual facts and do not merge
requirements to make validation easier.

VALIDATION ERRORS:
{json.dumps(issues, indent=2, sort_keys=True)}

PREVIOUS JSON:
{json.dumps(payload, indent=2, sort_keys=True)}
"""
            result = call_provider(
                repair_prompt,
                schema,
                provider=result.provider,
                model=result.model,
                api_key=_repair_api_key_for_result(
                    requested_provider=requested_provider,
                    actual_provider=result.provider,
                    api_key=api_key,
                ),
                fallback_provider=None,
                timeout=timeout_seconds,
                max_retries=max_retries,
                pin_provider=True,
            )
            continue
        return (
            ledger,
            result,
            {
                "first_pass_valid": repair_count == 0,
                "repair_attempts": repair_count,
                "validation_history": history,
            },
        )
    raise AssertionError("requirement validation loop terminated unexpectedly")


def _payload_for_validation(
    result: ProviderResult,
    *,
    contract_id: str,
    authoritative_requirements: list[AtomicRequirementProposal] | None = None,
) -> dict[str, Any]:
    payload = dict(result.payload)
    payload.update(
        {
            "compiler_version": NATIVE_COMPILER_VERSION,
            "contract_id": contract_id,
            "model": result.model,
            "provider": result.provider,
        }
    )
    if authoritative_requirements is not None:
        payload["requirements"] = [
            item.model_dump(mode="json") for item in authoritative_requirements
        ]
    return payload


def _validation_error_summary(exc: ValidationError) -> list[dict[str, str]]:
    """Return only structural validation metadata, never input values/source text."""

    issues: list[dict[str, str]] = []
    for error in exc.errors(include_input=False, include_url=False):
        location = ".".join(str(part) for part in error.get("loc", ())) or "<root>"
        issues.append(
            {
                "location": location,
                "type": str(error.get("type", "validation_error")),
                "message": str(error.get("msg", "invalid structured output")),
            }
        )
    return issues


def _semantic_repair_prompt(
    *,
    original_prompt: str,
    invalid_payload: dict[str, Any],
    issues: list[dict[str, str]],
    attempt: int,
) -> str:
    """Ask the same pinned provider to repair schema-valid but semantically invalid JSON."""

    return f"""{original_prompt}

SEMANTIC VALIDATION REPAIR {attempt}

Your previous JSON was syntactically valid but rejected by Evidue's deterministic
semantic validators. Return a COMPLETE replacement JSON object, not a patch.

You are repairing structure only. Re-read the ORIGINAL SOURCE DOCUMENTS above.
Do not invent facts merely to satisfy validation. In particular, if a required
rate, event type, field, threshold, date, or referenced document is not explicitly
supported by source text, REMOVE the invalid executable norm/settlement and mark
the clause review-required/unsupported with a diagnostic instead.

{_SEMANTIC_PARAMETER_CONTRACT}

VALIDATION ERRORS (no source text is included in these diagnostics):
{json.dumps(issues, indent=2, sort_keys=True)}

PREVIOUS JSON:
{json.dumps(invalid_payload, indent=2, sort_keys=True)}

Return only the complete corrected JSON matching the supplied response schema.
"""


def _repair_api_key_for_result(
    *,
    requested_provider: str | None,
    actual_provider: str,
    api_key: str | None,
) -> str | None:
    """Reuse an explicitly supplied key only when repair stays on that same provider."""

    if api_key is None or requested_provider is None:
        return None
    if canonical_provider_name(requested_provider) != canonical_provider_name(actual_provider):
        return None
    return api_key


def _degrade_invalid_executable_artifacts(
    *,
    payload: dict[str, Any],
    issues: list[dict[str, str]],
) -> tuple[AgreementCompilationProposal, list[dict[str, Any]]] | None:
    """Fail closed on localized invalid executable artifacts after repair is exhausted.

    This transformation never invents executable semantics. It removes only rejected
    norms or settlement effects, marks the source clause as requiring human attestation,
    and attaches blocking diagnostics. If any issue is outside those executable artifacts,
    or the degraded proposal still fails validation, no degradation is performed.
    """

    targets: dict[tuple[int, str], set[int]] = {}
    for issue in issues:
        parts = issue.get("location", "").split(".")
        if len(parts) < 4 or parts[0] != "clauses":
            return None
        artifact_kind = parts[2]
        if artifact_kind not in {"norms", "settlement_effects"}:
            return None
        try:
            clause_index = int(parts[1])
            artifact_index = int(parts[3])
        except ValueError:
            return None
        targets.setdefault((clause_index, artifact_kind), set()).add(artifact_index)

    if not targets:
        return None

    candidate = deepcopy(payload)
    clauses = candidate.get("clauses")
    if not isinstance(clauses, list):
        return None

    degraded: list[dict[str, Any]] = []
    touched_clauses: set[int] = set()
    for (clause_index, artifact_kind), artifact_indexes in sorted(targets.items()):
        if clause_index < 0 or clause_index >= len(clauses):
            return None
        clause = clauses[clause_index]
        if not isinstance(clause, dict):
            return None
        artifacts = clause.get(artifact_kind)
        if not isinstance(artifacts, list):
            return None

        removed: list[dict[str, Any]] = []
        for artifact_index in sorted(artifact_indexes, reverse=True):
            if artifact_index < 0 or artifact_index >= len(artifacts):
                return None
            artifact = artifacts.pop(artifact_index)
            removed.append(
                {
                    "clause_index": clause_index,
                    "clause_id": clause.get("clause_id"),
                    "artifact_kind": artifact_kind,
                    "artifact_index": artifact_index,
                    "artifact_id": artifact.get("id") if isinstance(artifact, dict) else None,
                }
            )
        degraded.extend(reversed(removed))
        touched_clauses.add(clause_index)

    for clause_index in sorted(touched_clauses):
        clause = clauses[clause_index]
        clause["automation_classification"] = "human_attestation_required"
        unsupported = clause.setdefault("unsupported_concepts", [])
        marker = "Executable artifact rejected by deterministic semantic validation"
        if marker not in unsupported:
            unsupported.append(marker)

        rejected_kinds = sorted(
            {item["artifact_kind"] for item in degraded if item["clause_index"] == clause_index}
        )
        clause.setdefault("diagnostics", []).append(
            {
                "code": "SEMANTIC_COMPILER_ARTIFACT_REJECTED",
                "severity": "blocking",
                "message": (
                    "LLM-proposed executable artifact(s) failed deterministic semantic "
                    f"validation after bounded repair ({', '.join(rejected_kinds)}) and "
                    "were removed. No replacement semantics were inferred; human review "
                    "is required."
                ),
                "clause_id": clause.get("clause_id"),
                "suggested_action": (
                    "Review the source clause and approve a corrected AIR before "
                    "using it for financial decisions."
                ),
            }
        )

    try:
        proposal = AgreementCompilationProposal.model_validate(candidate)
    except ValidationError:
        return None
    return proposal, degraded


def _validate_with_semantic_repairs(
    *,
    initial_result: ProviderResult,
    contract_id: str,
    original_prompt: str,
    schema: dict[str, Any],
    authoritative_requirements: list[AtomicRequirementProposal] | None,
    requested_provider: str | None,
    api_key: str | None,
    timeout_seconds: int,
    max_retries: int,
    max_semantic_repairs: int,
) -> tuple[AgreementCompilationProposal, ProviderResult, dict[str, Any]]:
    """Validate provider JSON and make bounded same-provider structural repair attempts.

    JSON-schema structured output cannot encode all of Evidue's parameter-dependent
    semantic invariants because several proposal fields intentionally use constrained
    dictionaries. The Pydantic validators remain authoritative. Production may ask the
    same provider to repair rejected JSON, but every repair is recorded in provenance so
    qualification can distinguish first-pass validity from repaired validity.
    """

    result = initial_result
    validation_history: list[dict[str, Any]] = []

    for repair_count in range(max_semantic_repairs + 1):
        payload = _payload_for_validation(
            result,
            contract_id=contract_id,
            authoritative_requirements=authoritative_requirements,
        )
        try:
            proposal = AgreementCompilationProposal.model_validate(payload)
        except ValidationError as exc:
            issues = _validation_error_summary(exc)
            validation_history.append(
                {
                    "attempt": repair_count + 1,
                    "issues": issues,
                }
            )
            if repair_count >= max_semantic_repairs:
                degraded = _degrade_invalid_executable_artifacts(payload=payload, issues=issues)
                if degraded is not None:
                    proposal, degraded_artifacts = degraded
                    return (
                        proposal,
                        result,
                        {
                            "first_pass_valid": False,
                            "semantic_repair_attempts": repair_count,
                            "validation_history": validation_history,
                            "degraded_after_semantic_repair": True,
                            "degraded_artifacts": degraded_artifacts,
                        },
                    )
                raise ValueError(
                    "Model output failed native proposal semantic validation after "
                    f"{repair_count} repair attempt(s): {issues}"
                ) from exc

            repair_prompt = _semantic_repair_prompt(
                original_prompt=original_prompt,
                invalid_payload=payload,
                issues=issues,
                attempt=repair_count + 1,
            )
            result = call_provider(
                repair_prompt,
                schema,
                provider=result.provider,
                model=result.model,
                api_key=_repair_api_key_for_result(
                    requested_provider=requested_provider,
                    actual_provider=result.provider,
                    api_key=api_key,
                ),
                fallback_provider=None,
                timeout=timeout_seconds,
                max_retries=max_retries,
                pin_provider=True,
            )
            continue

        return (
            proposal,
            result,
            {
                "first_pass_valid": repair_count == 0,
                "semantic_repair_attempts": repair_count,
                "validation_history": validation_history,
                "degraded_after_semantic_repair": False,
                "degraded_artifacts": [],
            },
        )

    raise AssertionError("semantic repair loop terminated unexpectedly")


def compile_native(
    *,
    contract_id: str,
    source_documents: dict[str, tuple[str, str]],
    metadata: dict[str, str],
    provider: str | None = None,
    model: str | None = None,
    api_key: str | None = None,
    fallback_provider: str | None = None,
    timeout_seconds: int = 120,
    max_retries: int = 3,
    max_semantic_repairs: int = MAX_SEMANTIC_REPAIRS,
    pin_provider: bool = False,
    requirement_ledger: RequirementLedgerProposal | None = None,
) -> NativeCompilationResult:
    """Compile contract language through independent interpretation and deterministic gates.

    Live compilation deliberately uses two model passes: an atomic-requirement pass
    followed by a clause/AIR proposal pass. The second pass receives the first pass as
    authoritative input and cannot silently merge or discard its requirements.
    """

    requirement_prompt: str | None = None
    requirement_result: ProviderResult | None = None
    requirement_validation: dict[str, Any] = {
        "first_pass_valid": True,
        "repair_attempts": 0,
        "validation_history": [],
    }

    if requirement_ledger is None:
        requirement_prompt = build_requirement_ledger_prompt(
            contract_id=contract_id,
            source_documents=source_documents,
            metadata=metadata,
        )
        requirement_schema = _requirement_schema()
        try:
            requirement_result = call_provider(
                requirement_prompt,
                requirement_schema,
                provider=provider,
                model=model,
                api_key=api_key,
                fallback_provider=fallback_provider,
                timeout=timeout_seconds,
                max_retries=max_retries,
                pin_provider=pin_provider,
            )
        except ProviderError as exc:
            raise RuntimeError(f"Atomic requirement extraction failed: {exc}") from exc

        requirement_ledger, requirement_result, requirement_validation = (
            _validate_requirement_ledger(
                initial_result=requirement_result,
                contract_id=contract_id,
                original_prompt=requirement_prompt,
                schema=requirement_schema,
                requested_provider=provider,
                api_key=api_key,
                timeout_seconds=timeout_seconds,
                max_retries=max_retries,
            )
        )

    requirement_ledger = bind_requirement_ledger_to_sources(
        requirement_ledger,
        expected_contract_id=contract_id,
        source_documents=source_documents,
        require_source_spans=True,
    )

    prompt = build_native_compiler_prompt(
        contract_id=contract_id,
        source_documents=source_documents,
        metadata=metadata,
        requirements=requirement_ledger.requirements,
    )
    schema = _proposal_schema()
    try:
        result = call_provider(
            prompt,
            schema,
            provider=provider,
            model=model,
            api_key=api_key,
            fallback_provider=fallback_provider,
            timeout=timeout_seconds,
            max_retries=max_retries,
            pin_provider=pin_provider,
        )
    except ProviderError as exc:
        raise RuntimeError(f"Native agreement compilation failed: {exc}") from exc

    proposal, result, semantic_validation = _validate_with_semantic_repairs(
        initial_result=result,
        contract_id=contract_id,
        original_prompt=prompt,
        schema=schema,
        authoritative_requirements=requirement_ledger.requirements,
        requested_provider=provider,
        api_key=api_key,
        timeout_seconds=timeout_seconds,
        max_retries=max_retries,
        max_semantic_repairs=max_semantic_repairs,
    )

    proposal = bind_proposal_to_sources(
        proposal,
        expected_contract_id=contract_id,
        source_documents=source_documents,
        require_source_spans=True,
    )
    schema_hash = (
        "sha256:"
        + sha256(
            json.dumps(schema, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
    )
    source_hashes = {
        document_id: "sha256:" + sha256(text.encode("utf-8")).hexdigest()
        for document_id, (_, text) in sorted(source_documents.items())
    }
    original_prompt_hash = sha256_text(prompt)
    provenance = compilation_provenance(
        result,
        prompt_hash=original_prompt_hash,
        final_provider_request_prompt_hash=result.prompt_hash,
        compiler_version=NATIVE_COMPILER_VERSION,
        prompt_version=NATIVE_PROMPT_VERSION,
        schema_hash=schema_hash,
        source_hashes=source_hashes,
        first_pass_semantically_valid=semantic_validation["first_pass_valid"],
        semantic_repair_attempts=semantic_validation["semantic_repair_attempts"],
        semantic_validation_history=semantic_validation["validation_history"],
        degraded_after_semantic_repair=semantic_validation["degraded_after_semantic_repair"],
        degraded_artifacts=semantic_validation["degraded_artifacts"],
        requirement_ledger_version=REQUIREMENT_LEDGER_VERSION,
        requirement_count=len(requirement_ledger.requirements),
        requirement_first_pass_valid=requirement_validation["first_pass_valid"],
        requirement_repair_attempts=requirement_validation["repair_attempts"],
        requirement_validation_history=requirement_validation["validation_history"],
        requirement_provider=(
            requirement_result.provider if requirement_result is not None else "prevalidated"
        ),
        requirement_model=(
            requirement_result.model if requirement_result is not None else "prevalidated"
        ),
        requirement_prompt_hash=(
            sha256_text(requirement_prompt) if requirement_prompt is not None else None
        ),
    )
    return NativeCompilationResult(
        proposal=proposal,
        prompt_hash=original_prompt_hash,
        raw_response={
            "provider_metadata": result.raw_metadata,
            "structured_payload": result.payload,
            "response_text_hash": "sha256:"
            + sha256(result.response_text.encode("utf-8")).hexdigest(),
            "provenance": provenance,
            "semantic_validation": semantic_validation,
            "requirement_validation": requirement_validation,
        },
        live_model_call=True,
        model=result.model,
        provider=result.provider,
        provenance=provenance,
    )


def compile_native_with_gemini(
    *,
    contract_id: str,
    source_documents: dict[str, tuple[str, str]],
    metadata: dict[str, str],
    api_key: str | None = None,
    model: str | None = None,
    timeout_seconds: int = 120,
) -> NativeCompilationResult:
    """Backward-compatible pinned Gemini wrapper used by older callers/tests."""

    return compile_native(
        contract_id=contract_id,
        source_documents=source_documents,
        metadata=metadata,
        provider="gemini",
        model=model,
        api_key=api_key,
        timeout_seconds=timeout_seconds,
        pin_provider=True,
    )


def _legacy_condition(operation: str, parameters: dict[str, Any]) -> ConditionProposal:
    if operation == "validate_evidence_envelope":
        conditions = [
            {
                "condition_type": "field_present",
                "parameters": {"field": field},
                "description": f"Required claim field {field} is present",
            }
            for field in parameters.get("required_claim_fields", [])
        ]
        conditions.append(
            {
                "condition_type": "event_exists",
                "parameters": {"event_types": [parameters["closure_event_type"]]},
                "description": "Direct closure evidence exists",
            }
        )
        return ConditionProposal(
            condition_type="all_of",
            parameters={"conditions": conditions},
            description="Required claim identifiers and closure evidence exist",
        )
    if operation == "claim_amount_equals":
        return ConditionProposal(
            condition_type="amount_equals",
            parameters={
                "field": parameters["claim_field"],
                "expected_amount": parameters["expected_amount"],
            },
            description="Billed amount matches the contractual unit price",
        )
    if operation == "claim_datetime_in_range":
        return ConditionProposal(
            condition_type="datetime_in_range",
            parameters={
                "field": parameters["claim_field"],
                "start": parameters["start"],
                "end_exclusive": parameters["end_exclusive"],
            },
            description="Claim falls within the contractual billing period",
        )
    if operation == "prohibit_event_within":
        compare_fields = []
        if parameters.get("compare_event_value") and parameters.get("compare_claim_field"):
            compare_fields.append(
                {
                    "event_field": parameters["compare_event_value"],
                    "claim_field": parameters["compare_claim_field"],
                    "normalizer": "text" if parameters.get("normalization") else None,
                }
            )
        return ConditionProposal(
            condition_type="event_within_window",
            parameters={
                "event_types": parameters["event_types"],
                "anchor_field": parameters["anchor_claim_field"],
                "window_value": parameters["window_value"],
                "window_unit": parameters["window_unit"],
                "start_exclusive": True,
                "compare_fields": compare_fields,
            },
            description="Prohibited event occurs within the contractual window",
        )
    if operation == "require_success_event_within":
        return ConditionProposal(
            condition_type="terminal_outcome",
            parameters={
                "success_types": [parameters["success_event_type"]],
                "failure_types": [parameters["failure_event_type"]],
                "anchor_field": parameters["anchor_claim_field"],
                "window_value": parameters["window_value"],
                "window_unit": parameters["window_unit"],
            },
            description="Required downstream success occurs within the contractual window",
        )
    if operation == "prohibit_field_mismatch_event":
        return ConditionProposal(
            condition_type="field_mismatch",
            parameters={
                "event_type": parameters["event_type"],
                "comparisons": parameters["comparisons"],
            },
            description="No authoritative mismatch event exists",
        )
    if operation == "unique_first_claim_within":
        return ConditionProposal(
            condition_type="duplicate_in_window",
            parameters={
                "group_by": parameters["group_by"],
                "order_by": parameters["order_by"],
                "window_value": parameters["window_value"],
                "window_unit": parameters["window_unit"],
                "normalizers": parameters.get("normalizers", {}),
            },
            description="Only the first eligible claim in the duplicate window is billable",
        )
    raise ValueError(f"Recorded native fixture cannot translate operation {operation}")


_EXTERNAL_EVIDENCE_CONDITION_TYPES = frozenset(
    {
        "event_exists",
        "event_absent",
        "event_within_window",
        "terminal_outcome",
        "field_mismatch",
        "count_events_exceeds",
    }
)


def _needs_external_evidence(candidate: ConditionProposal) -> bool:
    if candidate.condition_type in _EXTERNAL_EVIDENCE_CONDITION_TYPES:
        return True
    if candidate.condition_type in {"all_of", "any_of", "none_of"}:
        return any(
            _needs_external_evidence(ConditionProposal.model_validate(item))
            for item in candidate.parameters.get("conditions", [])
        )
    return False


def _recorded_source_clause(rule_id: str, contract_text: str) -> str:
    exact_by_rule = {
        "R0": "Price: $1.50 per supported outcome",
        "R6": "Billing period: 2026-06-01 through 2026-06-30",
        "R3": "A promised downstream action must complete successfully within two hours.",
        "R1": (
            "A resolution is not billable when a human completes or materially corrects "
            "the promised work within 24 hours, or when the customer recontacts support "
            "for the same intent within seven calendar days."
        ),
        "R2": (
            "A resolution is not billable when a human completes or materially corrects "
            "the promised work within 24 hours, or when the customer recontacts support "
            "for the same intent within seven calendar days."
        ),
        "R5": "Evidence must match the expected account and action.",
        "R7": "Evidence must match the expected account and action.",
        "R4": (
            "Only the earliest otherwise-payable outcome is billable for the same customer "
            "and normalized intent inside the 24-hour attribution window."
        ),
    }
    clause = exact_by_rule[rule_id]
    if clause not in contract_text:
        raise ValueError(
            f"Recorded native source clause for {rule_id} is missing from demo contract"
        )
    return clause


def recorded_native_proposal(
    *,
    contract_id: str,
    document_id: str,
    title: str,
    contract_text: str,
) -> NativeCompilationResult:
    """Offline proposal for the bundled demo contract only.

    This is intentionally a fixture path. Production native compilation must use
    the direct LLM clause-analysis pipeline above.
    """

    legacy = load_recorded_proposal(contract_text)
    clauses: list[ClauseAnalysisProposal] = []
    for rule in legacy.proposal.rules:
        consequence = rule.consequence
        norm_type = "prohibition" if rule.operation.startswith("prohibit_") else "obligation"
        condition = _legacy_condition(rule.operation, rule.parameters)
        proofs: list[ProofRequirementProposal] = []
        if _needs_external_evidence(condition):
            proofs.append(
                ProofRequirementProposal(
                    description=f"Evidence needed to evaluate {rule.title}",
                    fact_types=list(rule.evidence_required) or [f"rule.{rule.id}"],
                    preferred_authority="customer_system_of_record",
                )
            )
        norm = NormProposal(
            id=rule.id,
            norm_type=norm_type,
            subject="vendor",
            condition=condition,
            consequence=consequence,
            indeterminate_consequence="needs_review",
            proof_requirements=proofs,
            violation_reason_code=rule.id,
            violation_reason=rule.description,
            indeterminate_reason_code="MISSING_EVIDENCE",
            indeterminate_reason="Required evidence is unavailable or conflicting",
        )
        settlement_effects: list[SettlementProposal] = []
        if rule.operation == "claim_amount_equals":
            settlement_effects.append(
                SettlementProposal(
                    id="PRICE",
                    settlement_type="fixed_per_unit",
                    parameters={"unit_price": rule.parameters["expected_amount"]},
                    source_clause_id=rule.id,
                    description="Contractual per-outcome rate",
                )
            )
        clauses.append(
            ClauseAnalysisProposal(
                clause_id=rule.id,
                source_document_id=document_id,
                source_text=_recorded_source_clause(rule.id, contract_text),
                material=True,
                clause_type="pricing" if settlement_effects else "performance",
                norms=[norm],
                settlement_effects=settlement_effects,
                automation_classification="executable_if_data_available",
            )
        )
    proposal = AgreementCompilationProposal(
        compiler_version=NATIVE_COMPILER_VERSION,
        contract_id=contract_id,
        model="recorded-fixture",
        provider="recorded-fixture",
        source_documents=[SourceDocumentRef(document_id=document_id, title=title)],
        clauses=clauses,
        global_diagnostics=[
            DiagnosticProposal(
                code="RECORDED_NATIVE_FIXTURE",
                severity="info",
                message="Offline native proposal derived from the bundled recorded demo fixture.",
            )
        ],
    )
    proposal = bind_proposal_to_sources(
        proposal,
        expected_contract_id=contract_id,
        source_documents={document_id: (title, contract_text)},
    )
    return NativeCompilationResult(
        proposal=proposal,
        prompt_hash=sha256_text("recorded-native-fixture"),
        raw_response={"recorded_fixture": True},
        live_model_call=False,
        model="recorded-fixture",
        provider="recorded-fixture",
        provenance={
            "provider": "recorded-fixture",
            "model": proposal.model,
            "prompt_hash": sha256_text("recorded-native-proposal"),
            "compiler_version": NATIVE_COMPILER_VERSION,
            "prompt_version": NATIVE_PROMPT_VERSION,
        },
    )
