from __future__ import annotations

import hashlib
import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from app.agreements.legacy import conformance_report, legacy_rule_program_to_agreement_ir
from app.agreements.models import (
    AgreementIR,
    AutomationClass,
    ConformanceReport,
    SettlementPolicy,
    SourceClause,
)
from app.agreements.models import (
    ClauseCoverage as AgreementClauseCoverage,
)
from app.agreements.models import (
    CompilerDiagnostic as AgreementCompilerDiagnostic,
)
from app.agreements.models import (
    Expression as AgreementExpression,
)
from app.domain.models import ExecutableRule, RuleProgram

ROOT = Path(__file__).parents[3]
RECORDED_PROPOSAL_PATH = ROOT / "demo-data" / "contract" / "recorded-gemini-rule-proposal.json"
DEFAULT_CONTRACT_PATH = ROOT / "demo-data" / "contract" / "acme-nova-outcome-pricing-order-form.txt"
COMPILER_VERSION = "1.1"
DEFAULT_MODEL = "gemini-2.5-flash-lite"

AllowedOperation = Literal[
    "validate_evidence_envelope",
    "claim_datetime_in_range",
    "claim_amount_equals",
    "prohibit_event_within",
    "require_success_event_within",
    "prohibit_field_mismatch_event",
    "unique_first_claim_within",
]
AllowedConsequence = Literal["payable", "disputed", "needs_review"]
DiagnosticSeverity = Literal["info", "warning", "blocking"]
CoverageStatus = Literal["compiled", "needs_review", "not_applicable"]

_REQUIRED_PARAMETERS: dict[str, set[str]] = {
    "validate_evidence_envelope": {"required_claim_fields", "closure_event_type"},
    "claim_datetime_in_range": {"claim_field", "start", "end_exclusive"},
    "claim_amount_equals": {"claim_field", "expected_amount"},
    "prohibit_event_within": {
        "event_types",
        "anchor_claim_field",
        "window_value",
        "window_unit",
    },
    "require_success_event_within": {
        "success_event_type",
        "failure_event_type",
        "anchor_claim_field",
        "window_value",
        "window_unit",
    },
    "prohibit_field_mismatch_event": {"event_type", "comparisons"},
    "unique_first_claim_within": {
        "group_by",
        "order_by",
        "window_value",
        "window_unit",
    },
}
_OPTIONAL_PARAMETERS: dict[str, set[str]] = {
    "validate_evidence_envelope": set(),
    "claim_datetime_in_range": set(),
    "claim_amount_equals": {"tolerance"},
    "prohibit_event_within": {
        "compare_event_value",
        "compare_claim_field",
        "normalization",
    },
    "require_success_event_within": {"supporting_event_types"},
    "prohibit_field_mismatch_event": set(),
    "unique_first_claim_within": {"normalizers", "applies_after"},
}


def _require_string(value: Any, label: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a non-empty string")


def _require_string_list(value: Any, label: str, *, allow_empty: bool = False) -> None:
    if not isinstance(value, list) or (not value and not allow_empty):
        raise ValueError(f"{label} must be a non-empty list")
    if any(not isinstance(item, str) or not item.strip() for item in value):
        raise ValueError(f"{label} must contain only non-empty strings")


class CompilerDiagnostic(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str = Field(pattern=r"^[A-Z][A-Z0-9_]{2,63}$")
    severity: DiagnosticSeverity
    message: str = Field(min_length=5, max_length=1000)
    clause_text: str | None = Field(default=None, max_length=1500)
    suggested_action: str | None = Field(default=None, max_length=1000)


class ClauseCoverage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    clause_id: str = Field(pattern=r"^[A-Z0-9][A-Z0-9_.-]{0,63}$")
    clause_text: str = Field(min_length=5, max_length=1500)
    status: CoverageStatus
    rule_ids: list[str] = Field(default_factory=list, max_length=50)
    explanation: str = Field(min_length=5, max_length=1000)

    @model_validator(mode="after")
    def validate_status(self) -> ClauseCoverage:
        if self.status == "compiled" and not self.rule_ids:
            raise ValueError("compiled clause coverage must reference at least one rule")
        if self.status != "compiled" and self.rule_ids:
            raise ValueError("non-compiled clause coverage cannot reference executable rules")
        return self


class RuleProposal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=r"^[A-Z][A-Z0-9_-]{0,15}$")
    title: str = Field(min_length=3, max_length=120)
    description: str = Field(min_length=5, max_length=500)
    clause_text: str = Field(min_length=5, max_length=1000)
    operation: AllowedOperation
    parameters: dict[str, Any]
    evidence_required: list[str]
    priority: int = Field(ge=1, le=1000)
    consequence: AllowedConsequence

    @field_validator("evidence_required")
    @classmethod
    def evidence_names_are_safe(cls, value: list[str]) -> list[str]:
        if len(value) > 20 or any(not item or len(item) > 80 for item in value):
            raise ValueError("evidence_required contains invalid entries")
        return value

    @model_validator(mode="after")
    def validate_operation_parameters(self) -> RuleProposal:
        parameters = self.parameters
        required = _REQUIRED_PARAMETERS[self.operation]
        allowed = required | _OPTIONAL_PARAMETERS[self.operation]
        missing = required - parameters.keys()
        unknown = parameters.keys() - allowed
        if missing:
            raise ValueError(f"{self.operation} missing parameters: {sorted(missing)}")
        if unknown:
            raise ValueError(f"{self.operation} contains unsupported parameters: {sorted(unknown)}")

        for field_name in (
            "closure_event_type",
            "claim_field",
            "anchor_claim_field",
            "success_event_type",
            "failure_event_type",
            "event_type",
            "compare_event_value",
            "compare_claim_field",
            "normalization",
        ):
            if field_name in parameters:
                _require_string(parameters[field_name], field_name)

        for field_name in (
            "required_claim_fields",
            "event_types",
            "supporting_event_types",
            "group_by",
            "order_by",
            "applies_after",
        ):
            if field_name in parameters:
                _require_string_list(parameters[field_name], field_name)

        if "window_unit" in parameters and parameters["window_unit"] not in {"hours", "days"}:
            raise ValueError("window_unit must be hours or days")
        if "window_value" in parameters:
            value = parameters["window_value"]
            if not isinstance(value, int) or isinstance(value, bool) or value <= 0 or value > 365:
                raise ValueError("window_value must be an integer from 1 to 365")

        if self.operation == "claim_amount_equals":
            from decimal import Decimal, InvalidOperation

            try:
                expected = Decimal(str(parameters["expected_amount"]))
                tolerance = Decimal(str(parameters.get("tolerance", "0.00")))
            except InvalidOperation as exc:
                raise ValueError("expected_amount and tolerance must be decimal values") from exc
            if expected < 0 or tolerance < 0:
                raise ValueError("expected_amount and tolerance cannot be negative")

        if self.operation == "claim_datetime_in_range":
            start = datetime.fromisoformat(str(parameters["start"]))
            end = datetime.fromisoformat(str(parameters["end_exclusive"]))
            if end <= start:
                raise ValueError("end_exclusive must be later than start")

        if self.operation == "prohibit_field_mismatch_event":
            comparisons = parameters["comparisons"]
            if not isinstance(comparisons, list) or not comparisons:
                raise ValueError("comparisons must be a non-empty list")
            for comparison in comparisons:
                if not isinstance(comparison, dict) or set(comparison) != {
                    "event_field",
                    "claim_field",
                }:
                    raise ValueError(
                        "each comparison must contain exactly event_field and claim_field"
                    )
                _require_string(comparison["event_field"], "comparisons.event_field")
                _require_string(comparison["claim_field"], "comparisons.claim_field")

        if "normalizers" in parameters:
            normalizers = parameters["normalizers"]
            if not isinstance(normalizers, dict) or any(
                not isinstance(key, str)
                or not key.strip()
                or not isinstance(value, str)
                or not value.strip()
                for key, value in normalizers.items()
            ):
                raise ValueError("normalizers must map non-empty field names to normalizer names")
        return self


class CompilationProposal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    compiler_version: str
    contract_id: str
    model: str
    provider: str
    source_document: str
    rules: list[RuleProposal] = Field(min_length=1, max_length=50)
    diagnostics: list[CompilerDiagnostic] = Field(default_factory=list, max_length=100)
    clause_coverage: list[ClauseCoverage] = Field(default_factory=list, max_length=200)

    @model_validator(mode="after")
    def validate_compilation(self) -> CompilationProposal:
        ids = [rule.id for rule in self.rules]
        priorities = [rule.priority for rule in self.rules]
        if len(ids) != len(set(ids)):
            raise ValueError("rule IDs must be unique")
        if len(priorities) != len(set(priorities)):
            raise ValueError("rule priorities must be unique")

        if not self.clause_coverage:
            self.clause_coverage = [
                ClauseCoverage(
                    clause_id=f"RULE-{rule.id}",
                    clause_text=rule.clause_text,
                    status="compiled",
                    rule_ids=[rule.id],
                    explanation=(
                        "Legacy recorded proposal: source clause is represented by this rule."
                    ),
                )
                for rule in self.rules
            ]

        known_ids = set(ids)
        referenced_ids = {
            rule_id for coverage in self.clause_coverage for rule_id in coverage.rule_ids
        }
        unknown_ids = referenced_ids - known_ids
        if unknown_ids:
            raise ValueError(f"clause coverage references unknown rule IDs: {sorted(unknown_ids)}")
        uncovered = known_ids - referenced_ids
        if uncovered:
            raise ValueError(
                f"every executable rule must have clause coverage: {sorted(uncovered)}"
            )

        needs_review = [
            coverage for coverage in self.clause_coverage if coverage.status == "needs_review"
        ]
        blocking_clauses = {
            diagnostic.clause_text
            for diagnostic in self.diagnostics
            if diagnostic.severity == "blocking" and diagnostic.clause_text
        }
        for coverage in needs_review:
            if coverage.clause_text not in blocking_clauses:
                raise ValueError(
                    "every needs_review clause must have a blocking diagnostic "
                    "with the same clause_text"
                )
        return self

    @property
    def blocking_diagnostics(self) -> tuple[CompilerDiagnostic, ...]:
        return tuple(item for item in self.diagnostics if item.severity == "blocking")

    @property
    def approval_ready(self) -> bool:
        return not self.blocking_diagnostics and all(
            coverage.status != "needs_review" for coverage in self.clause_coverage
        )


@dataclass(frozen=True)
class CompilationResult:
    proposal: CompilationProposal
    source_hash: str
    prompt_hash: str
    raw_response: dict[str, Any]
    live_model_call: bool


def sha256_text(value: str) -> str:
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


def build_compiler_prompt(
    contract_text: str,
    contract_id: str,
    contract_metadata: dict[str, str] | None = None,
) -> str:
    operations = """
Supported deterministic operations:
- validate_evidence_envelope: required_claim_fields[], closure_event_type
- claim_datetime_in_range: claim_field, start ISO timestamp, end_exclusive ISO timestamp
- claim_amount_equals: claim_field, expected_amount decimal string; optional tolerance decimal string
- prohibit_event_within: event_types[], anchor_claim_field, window_value, window_unit; optional compare_event_value, compare_claim_field, normalization
- require_success_event_within: success_event_type, failure_event_type, anchor_claim_field, window_value, window_unit; optional supporting_event_types[]
- prohibit_field_mismatch_event: event_type, comparisons[{event_field, claim_field}]
- unique_first_claim_within: group_by[], order_by[], window_value, window_unit; optional normalizers{}, applies_after[]
""".strip()
    metadata = json.dumps(contract_metadata or {}, sort_keys=True, indent=2)
    return f"""You are a contract rule compiler, not an adjudicator.
Convert contractual billing eligibility terms into a proposed deterministic rule program using only the supported operations below.
Do not decide any invoice claim. Do not invent commercial terms, identifiers, event types, dates, rates, or consequences.
Use the supplied metadata for billing-period values instead of inferring them from unrelated prose.

You must account for every material billing, exclusion, evidence, timing, duplication, attribution, and pricing clause:
- For a supported clause, add a clause_coverage item with status=compiled and reference every generated rule ID.
- For an unsupported or ambiguous clause, do not approximate it. Add clause_coverage status=needs_review and a blocking diagnostic with the exact clause_text and a concrete suggested_action.
- Use status=not_applicable only for clearly non-billing administrative language and explain why.
- Never silently omit a material clause.
- Return exact source language in rule.clause_text and clause_coverage.clause_text.
- Return no parameters other than those documented for the selected operation.

Return only JSON matching the supplied schema.

Contract ID: {contract_id}
Contract metadata:
{metadata}

{operations}

CONTRACT TEXT
---
{contract_text}
---
"""


def _response_schema() -> dict[str, Any]:
    diagnostic = {
        "type": "object",
        "required": ["code", "severity", "message"],
        "properties": {
            "code": {"type": "string"},
            "severity": {"type": "string", "enum": ["info", "warning", "blocking"]},
            "message": {"type": "string"},
            "clause_text": {"type": "string", "nullable": True},
            "suggested_action": {"type": "string", "nullable": True},
        },
    }
    coverage = {
        "type": "object",
        "required": ["clause_id", "clause_text", "status", "rule_ids", "explanation"],
        "properties": {
            "clause_id": {"type": "string"},
            "clause_text": {"type": "string"},
            "status": {
                "type": "string",
                "enum": ["compiled", "needs_review", "not_applicable"],
            },
            "rule_ids": {"type": "array", "items": {"type": "string"}},
            "explanation": {"type": "string"},
        },
    }
    rule = {
        "type": "object",
        "required": [
            "id",
            "title",
            "description",
            "clause_text",
            "operation",
            "parameters",
            "evidence_required",
            "priority",
            "consequence",
        ],
        "properties": {
            "id": {"type": "string"},
            "title": {"type": "string"},
            "description": {"type": "string"},
            "clause_text": {"type": "string"},
            "operation": {
                "type": "string",
                "enum": [
                    "validate_evidence_envelope",
                    "claim_datetime_in_range",
                    "claim_amount_equals",
                    "prohibit_event_within",
                    "require_success_event_within",
                    "prohibit_field_mismatch_event",
                    "unique_first_claim_within",
                ],
            },
            "parameters": {"type": "object", "additionalProperties": True},
            "evidence_required": {"type": "array", "items": {"type": "string"}},
            "priority": {"type": "integer"},
            "consequence": {
                "type": "string",
                "enum": ["payable", "disputed", "needs_review"],
            },
        },
    }
    return {
        "type": "object",
        "required": [
            "compiler_version",
            "contract_id",
            "model",
            "provider",
            "source_document",
            "rules",
            "diagnostics",
            "clause_coverage",
        ],
        "properties": {
            "compiler_version": {"type": "string"},
            "contract_id": {"type": "string"},
            "model": {"type": "string"},
            "provider": {"type": "string"},
            "source_document": {"type": "string"},
            "rules": {"type": "array", "items": rule},
            "diagnostics": {"type": "array", "items": diagnostic},
            "clause_coverage": {"type": "array", "items": coverage},
        },
    }


def _extract_response_text(payload: dict[str, Any]) -> str:
    candidates = payload.get("candidates") or []
    if not candidates:
        raise ValueError("Gemini returned no candidates")
    parts = candidates[0].get("content", {}).get("parts", [])
    text = "".join(str(part.get("text", "")) for part in parts).strip()
    if not text:
        raise ValueError("Gemini returned an empty structured response")
    return text


def compile_with_gemini(
    contract_text: str,
    contract_id: str,
    source_document: str,
    *,
    contract_metadata: dict[str, str] | None = None,
    api_key: str | None = None,
    model: str | None = None,
    timeout_seconds: int = 45,
) -> CompilationResult:
    key = api_key or os.getenv("GEMINI_API_KEY")
    if not key:
        raise RuntimeError("GEMINI_API_KEY is not configured")
    selected_model = model or os.getenv("GEMINI_MODEL", DEFAULT_MODEL)
    prompt = build_compiler_prompt(contract_text, contract_id, contract_metadata)
    request_payload = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0,
            "responseMimeType": "application/json",
            "responseSchema": _response_schema(),
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
        raise RuntimeError(f"Gemini compilation failed ({exc.code}): {body[:500]}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Gemini compilation failed: {exc.reason}") from exc

    proposal_payload = json.loads(_extract_response_text(raw))
    proposal_payload["compiler_version"] = COMPILER_VERSION
    proposal_payload["contract_id"] = contract_id
    proposal_payload["model"] = selected_model
    proposal_payload["provider"] = "google-gemini"
    proposal_payload["source_document"] = source_document
    try:
        proposal = CompilationProposal.model_validate(proposal_payload)
    except ValidationError as exc:
        raise ValueError(f"Model output failed rule validation: {exc}") from exc
    return CompilationResult(
        proposal=proposal,
        source_hash=sha256_text(contract_text),
        prompt_hash=sha256_text(prompt),
        raw_response=raw,
        live_model_call=True,
    )


def load_recorded_proposal(contract_text: str | None = None) -> CompilationResult:
    text = contract_text if contract_text is not None else DEFAULT_CONTRACT_PATH.read_text()
    payload = json.loads(RECORDED_PROPOSAL_PATH.read_text())
    payload["compiler_version"] = COMPILER_VERSION
    proposal = CompilationProposal.model_validate(payload)
    prompt = build_compiler_prompt(text, proposal.contract_id)
    return CompilationResult(
        proposal=proposal,
        source_hash=sha256_text(text),
        prompt_hash=sha256_text(prompt),
        raw_response={
            "recorded_fixture": True,
            "note": "Validated recorded Gemini proposal used for an offline, repeatable demo.",
        },
        live_model_call=False,
    )


def _rule_program_from_proposal(
    proposal: CompilationProposal,
    *,
    compilation_id: str,
    version: int,
    source_hash: str,
) -> RuleProgram:
    rules = tuple(
        ExecutableRule(
            id=rule.id,
            title=rule.title,
            description=rule.description,
            clause_text=rule.clause_text,
            operation=rule.operation,
            parameters=rule.parameters,
            evidence_required=tuple(rule.evidence_required),
            priority=rule.priority,
            consequence=rule.consequence,
            compilation_id=compilation_id,
        )
        for rule in sorted(proposal.rules, key=lambda item: item.priority)
    )
    return RuleProgram(
        compilation_id=compilation_id,
        version=version,
        source_hash=source_hash,
        rules=rules,
    )


def to_rule_program(
    proposal: CompilationProposal,
    *,
    compilation_id: str,
    version: int,
    source_hash: str,
) -> RuleProgram:
    if not proposal.approval_ready:
        raise ValueError("Compilation contains blocking or unresolved contract diagnostics")
    return _rule_program_from_proposal(
        proposal,
        compilation_id=compilation_id,
        version=version,
        source_hash=source_hash,
    )


def agreement_artifacts_for_proposal(
    proposal: CompilationProposal,
    *,
    compilation_id: str,
    version: int,
    source_hash: str,
) -> tuple[AgreementIR, ConformanceReport]:
    """Translate a validated proposal into the contract-agnostic Agreement IR.

    This translation is intentionally available before approval so operators can inspect
    unsupported clauses and proof gaps. The legacy deterministic program remains the only
    component allowed to adjudicate invoice money during the migration.
    """

    program = _rule_program_from_proposal(
        proposal,
        compilation_id=compilation_id,
        version=version,
        source_hash=source_hash,
    )
    translated = legacy_rule_program_to_agreement_ir(program)
    norm_by_rule_id = {norm.legacy_rule_id: norm for norm in translated.norms}

    source_clauses: list[SourceClause] = []
    coverage_items: list[AgreementClauseCoverage] = []
    source_ids_by_rule: dict[str, list[str]] = {}
    source_ids_by_text: dict[str, list[str]] = {}
    for item in proposal.clause_coverage:
        source_id = f"SOURCE-{item.clause_id}"
        source_clauses.append(
            SourceClause(
                id=source_id,
                document_id=proposal.source_document,
                text=item.clause_text,
                material=item.status != "not_applicable",
            )
        )
        source_ids_by_text.setdefault(item.clause_text, []).append(source_id)
        norm_ids = [
            norm_by_rule_id[rule_id].id for rule_id in item.rule_ids if rule_id in norm_by_rule_id
        ]
        for rule_id in item.rule_ids:
            source_ids_by_rule.setdefault(rule_id, []).append(source_id)
        if item.status == "compiled":
            classifications = {
                norm_by_rule_id[rule_id].automation_class
                for rule_id in item.rule_ids
                if rule_id in norm_by_rule_id
            }
            classification = (
                AutomationClass.EXECUTABLE_IF_DATA_AVAILABLE
                if AutomationClass.EXECUTABLE_IF_DATA_AVAILABLE in classifications
                else AutomationClass.FULLY_EXECUTABLE
            )
        elif item.status == "not_applicable":
            classification = AutomationClass.NON_OPERATIONAL
        else:
            classification = AutomationClass.UNSUPPORTED
        coverage_items.append(
            AgreementClauseCoverage(
                clause_id=source_id,
                clause_text=item.clause_text,
                classification=classification,
                norm_ids=norm_ids,
                rationale=item.explanation,
                material=item.status != "not_applicable",
            )
        )

    norms = [
        norm.model_copy(
            update={
                "source_clause_ids": source_ids_by_rule.get(
                    str(norm.legacy_rule_id), norm.source_clause_ids
                )
            }
        )
        for norm in translated.norms
    ]
    diagnostics = [
        AgreementCompilerDiagnostic(
            code=item.code,
            severity=item.severity,
            message=item.message,
            clause_ids=source_ids_by_text.get(item.clause_text or "", []),
        )
        for item in proposal.diagnostics
    ]
    final_clauses = source_clauses or translated.clauses
    final_norms = norms
    norm_source_ids = {norm.id: norm.source_clause_ids for norm in final_norms}
    final_predicates = [
        predicate.model_copy(
            update={
                "source_clause_ids": norm_source_ids.get(
                    predicate.norm_id, predicate.source_clause_ids
                )
            }
        )
        for predicate in translated.predicates
    ]

    # Build a real settlement policy using the final clause/norm IDs.
    eligibility_norm_ids = [n.id for n in final_norms if n.condition.operator != "unique_by"]
    settlement_policies = [
        SettlementPolicy(
            id="SETTLEMENT-1",
            claim_type="outcome",
            eligibility_norm_ids=eligibility_norm_ids,
            amount_expression=AgreementExpression(
                operator="multiply",
                operands=[
                    AgreementExpression(operator="field", path="claim.billed_amount"),
                    AgreementExpression(
                        operator="rate_table",
                        path="settlement.eligible_flag",
                        parameters={"rates": {"true": "1", "false": "0"}, "default": "0"},
                    ),
                ],
            ),
            source_clause_ids=[c.id for c in final_clauses],
        ),
    ]

    agreement = translated.model_copy(
        update={
            "clauses": final_clauses,
            "norms": final_norms,
            "predicates": final_predicates,
            "settlement_policies": settlement_policies,
            "coverage": coverage_items or translated.coverage,
            "diagnostics": diagnostics,
        }
    )
    agreement = AgreementIR.model_validate(agreement.model_dump(mode="python"))
    return agreement, conformance_report(agreement)


def recorded_rule_program() -> RuleProgram:
    result = load_recorded_proposal()
    return to_rule_program(
        result.proposal,
        compilation_id="COMP-RECORDED-GEMINI-V1",
        version=1,
        source_hash=result.source_hash,
    )
