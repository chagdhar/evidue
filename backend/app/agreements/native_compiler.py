"""Native contract-language to AgreementCompilationProposal compiler.

The LLM is constrained to the semantic proposal schema. A deterministic source
binder verifies that every proposed clause is an exact span of an uploaded
agreement document before the proposal may be lowered into executable AIR.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from hashlib import sha256
from typing import Any

from pydantic import ValidationError

from app.contracts.compiler import DEFAULT_MODEL, load_recorded_proposal, sha256_text

from .compiler_models import (
    AgreementCompilationProposal,
    ClauseAnalysisProposal,
    ConditionProposal,
    DiagnosticProposal,
    NormProposal,
    ProofRequirementProposal,
    SettlementProposal,
    SourceDocumentRef,
)

NATIVE_COMPILER_VERSION = "native-air-0.2"
NATIVE_PROMPT_VERSION = "native-air-prompt-0.2"


@dataclass(frozen=True)
class NativeCompilationResult:
    proposal: AgreementCompilationProposal
    prompt_hash: str
    raw_response: dict[str, Any]
    live_model_call: bool
    model: str
    provider: str


def _extract_response_text(payload: dict[str, Any]) -> str:
    candidates = payload.get("candidates") or []
    if not candidates:
        raise ValueError("Gemini returned no candidates")
    parts = candidates[0].get("content", {}).get("parts", [])
    text = "".join(str(part.get("text", "")) for part in parts).strip()
    if not text:
        raise ValueError("Gemini returned an empty native AIR proposal")
    return text


def _proposal_schema() -> dict[str, Any]:
    """Return the strict Pydantic schema used for model output validation."""

    return AgreementCompilationProposal.model_json_schema()


def build_native_compiler_prompt(
    *,
    contract_id: str,
    source_documents: dict[str, tuple[str, str]],
    metadata: dict[str, str],
) -> str:
    document_block = "\n\n".join(
        f"DOCUMENT_ID: {document_id}\nTITLE: {title}\n---\n{text}"
        for document_id, (title, text) in source_documents.items()
    )
    return f"""You are Evidue's contract clause-analysis compiler.

Your output is a proposal for deterministic lowering. You DO NOT decide whether
an invoice claim is payable and you DO NOT calculate a final payable amount.

Rules:
1. Analyze every material commercial clause in the supplied documents.
2. Copy source_text EXACTLY from the source document. Do not paraphrase it.
3. Use only condition_type, settlement_type, norm_type, consequence, clause_type,
   automation classification, and diagnostic values allowed by the JSON schema.
4. Never invent an observation window, rate, threshold, party, definition, or
   exception. If a material concept cannot be represented safely, classify the
   clause as unsupported or human_attestation_required and emit a blocking or
   warning diagnostic as appropriate.
5. A pricing term belongs in settlement_effects. A performance requirement
   belongs in norms. Do not encode prices as prose-only diagnostics.
6. Missing evidence must be capable of resolving to unknown/needs_review rather
   than automatically proving breach.
7. Identify defined terms and cross-references. Unresolved material references
   must be explicit diagnostics.
8. Use proof requirements to state the FACTS needed, not vendor product names.
   Do NOT create a proof requirement for a condition that can be evaluated only
   from normalized invoice claim fields already present in the claim (for
   example billed amount, claim timestamp, identifiers, or batch uniqueness).
   Proof requirements are for facts that require external evidence, state, or
   authoritative absence/completeness guarantees.
9. Prefer customer_system_of_record authority for operational outcome facts.
10. Respect document precedence, effective dates, amendments, supersession, and incorporation relationships supplied in METADATA. When commercial terms conflict, represent the controlling effective term rather than combining incompatible rates or conditions. If precedence is ambiguous, require human review instead of guessing.
11. Subjective standards such as "reasonable", "material", "satisfactory", "good faith", or similar judgment language must not be silently converted into fully executable predicates unless the contract itself defines an objective measurable test.
12. Preserve negation and exceptions exactly. "Unless", "except", "only if", "not payable", and similar language can reverse financial effect and must never be flattened into the opposite rule.
13. Do not emit executable code, SQL, Python, Rego, JavaScript, or arbitrary AST.

CONTRACT_ID: {contract_id}
METADATA: {json.dumps(metadata, sort_keys=True)}
COMPILER_VERSION: {NATIVE_COMPILER_VERSION}

SOURCE DOCUMENTS:
{document_block}

Return only JSON matching the supplied response schema.
"""


def _find_exact_span(text: str, clause_text: str) -> tuple[int, int]:
    start = text.find(clause_text)
    if start < 0:
        raise ValueError("Proposed source_text is not an exact substring of the source document")
    return start, start + len(clause_text)


def bind_proposal_to_sources(
    proposal: AgreementCompilationProposal,
    *,
    expected_contract_id: str,
    source_documents: dict[str, tuple[str, str]],
) -> AgreementCompilationProposal:
    """Verify and attach exact source spans/hashes for every proposed clause."""

    if proposal.contract_id != expected_contract_id:
        raise ValueError(
            f"Proposal contract_id {proposal.contract_id!r} does not match {expected_contract_id!r}"
        )
    known_documents = set(source_documents)
    proposal_document_ids = {item.document_id for item in proposal.source_documents}
    unknown = proposal_document_ids - known_documents
    if unknown:
        raise ValueError(f"Proposal references unknown source documents: {sorted(unknown)}")

    bound_clauses: list[ClauseAnalysisProposal] = []
    for clause in proposal.clauses:
        if clause.source_document_id not in source_documents:
            raise ValueError(
                f"Clause {clause.clause_id} references unknown document {clause.source_document_id}"
            )
        _, source_text = source_documents[clause.source_document_id]
        start, end = _find_exact_span(source_text, clause.source_text)
        if clause.source_start is not None and clause.source_start != start:
            raise ValueError(f"Clause {clause.clause_id} source_start does not match source text")
        if clause.source_end is not None and clause.source_end != end:
            raise ValueError(f"Clause {clause.clause_id} source_end does not match source text")
        text_hash = sha256(clause.source_text.encode("utf-8")).hexdigest()
        if clause.source_text_hash is not None and clause.source_text_hash != text_hash:
            raise ValueError(
                f"Clause {clause.clause_id} source_text_hash does not match source text"
            )
        bound_clauses.append(
            clause.model_copy(
                update={
                    "source_start": start,
                    "source_end": end,
                    "source_text_hash": text_hash,
                }
            )
        )

    expected_documents = [
        SourceDocumentRef(document_id=document_id, title=title)
        for document_id, (title, _) in source_documents.items()
    ]
    return proposal.model_copy(
        update={
            "contract_id": expected_contract_id,
            "source_documents": expected_documents,
            "clauses": bound_clauses,
        }
    )


def compile_native_with_gemini(
    *,
    contract_id: str,
    source_documents: dict[str, tuple[str, str]],
    metadata: dict[str, str],
    api_key: str | None = None,
    model: str | None = None,
    timeout_seconds: int = 60,
) -> NativeCompilationResult:
    key = api_key or os.getenv("GEMINI_API_KEY")
    if not key:
        raise RuntimeError("GEMINI_API_KEY is not configured")
    selected_model = model or os.getenv("GEMINI_MODEL", DEFAULT_MODEL)
    prompt = build_native_compiler_prompt(
        contract_id=contract_id,
        source_documents=source_documents,
        metadata=metadata,
    )
    request_payload = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0,
            "responseMimeType": "application/json",
            "responseSchema": _proposal_schema(),
        },
    }
    request = urllib.request.Request(
        f"https://generativelanguage.googleapis.com/v1beta/models/{selected_model}:generateContent",
        data=json.dumps(request_payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "x-goog-api-key": key},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            raw = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Gemini native compilation failed ({exc.code}): {body[:500]}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Gemini native compilation failed: {exc.reason}") from exc

    payload = json.loads(_extract_response_text(raw))
    payload.update(
        {
            "compiler_version": NATIVE_COMPILER_VERSION,
            "contract_id": contract_id,
            "model": selected_model,
            "provider": "google-gemini",
        }
    )
    try:
        proposal = AgreementCompilationProposal.model_validate(payload)
    except ValidationError as exc:
        raise ValueError(f"Model output failed native proposal validation: {exc}") from exc
    proposal = bind_proposal_to_sources(
        proposal,
        expected_contract_id=contract_id,
        source_documents=source_documents,
    )
    return NativeCompilationResult(
        proposal=proposal,
        prompt_hash=sha256_text(prompt),
        raw_response=raw,
        live_model_call=True,
        model=selected_model,
        provider="google-gemini",
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
    )
