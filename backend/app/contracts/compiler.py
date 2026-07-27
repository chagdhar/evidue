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

from app.domain.models import ExecutableRule, RuleProgram

ROOT = Path(__file__).parents[3]
RECORDED_PROPOSAL_PATH = ROOT / "demo-data" / "contract" / "recorded-gemini-rule-proposal.json"
DEFAULT_CONTRACT_PATH = ROOT / "demo-data" / "contract" / "acme-nova-outcome-pricing-order-form.txt"
COMPILER_VERSION = "1.0"
DEFAULT_MODEL = "gemini-2.5-flash-lite"

AllowedOperation = Literal[
    "validate_evidence_envelope",
    "claim_datetime_in_range",
    "prohibit_event_within",
    "require_success_event_within",
    "prohibit_field_mismatch_event",
    "unique_first_claim_within",
]
AllowedConsequence = Literal["payable", "disputed", "needs_review"]


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
        p = self.parameters
        required: dict[str, set[str]] = {
            "validate_evidence_envelope": {"required_claim_fields", "closure_event_type"},
            "claim_datetime_in_range": {"claim_field", "start", "end_exclusive"},
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
        missing = required[self.operation] - p.keys()
        if missing:
            raise ValueError(f"{self.operation} missing parameters: {sorted(missing)}")
        if "window_unit" in p and p["window_unit"] not in {"hours", "days"}:
            raise ValueError("window_unit must be hours or days")
        if "window_value" in p:
            value = p["window_value"]
            if not isinstance(value, int) or isinstance(value, bool) or value <= 0 or value > 365:
                raise ValueError("window_value must be an integer from 1 to 365")
        if self.operation == "claim_datetime_in_range":
            datetime.fromisoformat(str(p["start"]))
            datetime.fromisoformat(str(p["end_exclusive"]))
        return self


class CompilationProposal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    compiler_version: str
    contract_id: str
    model: str
    provider: str
    source_document: str
    rules: list[RuleProposal] = Field(min_length=1, max_length=50)

    @model_validator(mode="after")
    def unique_rules(self) -> CompilationProposal:
        ids = [rule.id for rule in self.rules]
        priorities = [rule.priority for rule in self.rules]
        if len(ids) != len(set(ids)):
            raise ValueError("rule IDs must be unique")
        if len(priorities) != len(set(priorities)):
            raise ValueError("rule priorities must be unique")
        return self


@dataclass(frozen=True)
class CompilationResult:
    proposal: CompilationProposal
    source_hash: str
    prompt_hash: str
    raw_response: dict[str, Any]
    live_model_call: bool


def sha256_text(value: str) -> str:
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


def build_compiler_prompt(contract_text: str, contract_id: str) -> str:
    operations = """
Supported deterministic operations:
- validate_evidence_envelope: required_claim_fields[], closure_event_type
- claim_datetime_in_range: claim_field, start ISO timestamp, end_exclusive ISO timestamp
- prohibit_event_within: event_types[], anchor_claim_field, window_value, window_unit; optional compare_event_value, compare_claim_field, normalization
- require_success_event_within: success_event_type, failure_event_type, anchor_claim_field, window_value, window_unit; optional supporting_event_types[]
- prohibit_field_mismatch_event: event_type, comparisons[{event_field, claim_field}]
- unique_first_claim_within: group_by[], order_by[], window_value, window_unit; optional normalizers{}, applies_after[]
""".strip()
    return f"""You are a contract rule compiler, not an adjudicator.
Convert the contract into a proposed list of executable billing rules using only the supported operations below.
Do not decide any invoice claim. Do not invent commercial terms. Preserve exact numeric windows and consequences.
Create review rules for missing identifiers/evidence and a billing-period rule when the contract metadata supplies a period.
Return only JSON matching the supplied schema.

Contract ID: {contract_id}
{operations}

CONTRACT TEXT
---
{contract_text}
---
"""


def _response_schema() -> dict[str, Any]:
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
        ],
        "properties": {
            "compiler_version": {"type": "string"},
            "contract_id": {"type": "string"},
            "model": {"type": "string"},
            "provider": {"type": "string"},
            "source_document": {"type": "string"},
            "rules": {"type": "array", "items": rule},
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
    api_key: str | None = None,
    model: str | None = None,
    timeout_seconds: int = 45,
) -> CompilationResult:
    key = api_key or os.getenv("GEMINI_API_KEY")
    if not key:
        raise RuntimeError("GEMINI_API_KEY is not configured")
    selected_model = model or os.getenv("GEMINI_MODEL", DEFAULT_MODEL)
    prompt = build_compiler_prompt(contract_text, contract_id)
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


def to_rule_program(
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


def recorded_rule_program() -> RuleProgram:
    result = load_recorded_proposal()
    return to_rule_program(
        result.proposal,
        compilation_id="COMP-RECORDED-GEMINI-V1",
        version=1,
        source_hash=result.source_hash,
    )
