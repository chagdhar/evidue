from __future__ import annotations

from copy import deepcopy

import pytest
from app.agreements import native_compiler
from app.agreements.compiler_models import ConditionProposal
from app.agreements.providers import ProviderResult
from pydantic import ValidationError


def _payload(*, unit_price: str | None) -> dict:
    parameters = {} if unit_price is None else {"unit_price": unit_price}
    return {
        "compiler_version": "model-value-overridden",
        "contract_id": "model-value-overridden",
        "model": "model-value-overridden",
        "provider": "model-value-overridden",
        "source_documents": [{"document_id": "DOC-1", "title": "Order Form"}],
        "definitions": [],
        "clauses": [
            {
                "clause_id": "PRICE-1",
                "source_document_id": "DOC-1",
                "source_span_ids": ["SPAN-000001"],
                "source_text": "model-authored text is not authoritative",
                "source_start": None,
                "source_end": None,
                "source_text_hash": None,
                "material": True,
                "clause_type": "pricing",
                "parties": [],
                "defined_terms_used": [],
                "references": [],
                "norms": [],
                "settlement_effects": [
                    {
                        "id": "PRICE",
                        "settlement_type": "fixed_per_unit",
                        "parameters": parameters,
                        "source_clause_id": "PRICE-1",
                        "description": "Explicit per-outcome price",
                    }
                ],
                "automation_classification": "fully_executable",
                "unsupported_concepts": [],
                "diagnostics": [],
            }
        ],
        "global_diagnostics": [],
    }


def test_nested_condition_type_error_becomes_validation_error() -> None:
    with pytest.raises(ValidationError):
        ConditionProposal.model_validate(
            {
                "condition_type": "all_of",
                "parameters": {"conditions": ["not-an-object"]},
                "description": "invalid composite",
            }
        )


def test_compile_native_repairs_semantically_invalid_structured_output(monkeypatch) -> None:
    results = [
        ProviderResult(
            payload=_payload(unit_price=None),
            provider="google-gemini",
            model="test-model",
            prompt_hash="sha256:first",
            response_text="first",
        ),
        ProviderResult(
            payload=_payload(unit_price="1.50"),
            provider="google-gemini",
            model="test-model",
            prompt_hash="sha256:repair",
            response_text="repair",
        ),
    ]
    calls: list[str] = []

    def fake_call_provider(prompt, response_schema, **kwargs):
        calls.append(prompt)
        return results.pop(0)

    monkeypatch.setattr(native_compiler, "call_provider", fake_call_provider)

    result = native_compiler.compile_native(
        contract_id="C-1",
        source_documents={"DOC-1": ("Order Form", "Price: $1.50 per supported outcome")},
        metadata={},
        provider="gemini",
        api_key="test-key",
        pin_provider=True,
        max_semantic_repairs=1,
    )

    settlement = result.proposal.clauses[0].settlement_effects[0]
    assert settlement.parameters["unit_price"] == "1.50"
    assert result.proposal.clauses[0].source_text == "Price: $1.50 per supported outcome"
    assert result.provenance["first_pass_semantically_valid"] is False
    assert result.provenance["semantic_repair_attempts"] == 1
    assert len(result.provenance["semantic_validation_history"]) == 1
    assert len(calls) == 2
    assert "SEMANTIC VALIDATION REPAIR 1" in calls[1]
    assert "DO NOT create a partially parameterized settlement effect" in calls[1]


def test_semantic_repair_is_bounded(monkeypatch) -> None:
    invalid = ProviderResult(
        payload=_payload(unit_price=None),
        provider="google-gemini",
        model="test-model",
        prompt_hash="sha256:invalid",
        response_text="invalid",
    )
    calls = 0

    def fake_call_provider(prompt, response_schema, **kwargs):
        nonlocal calls
        calls += 1
        return deepcopy(invalid)

    monkeypatch.setattr(native_compiler, "call_provider", fake_call_provider)

    with pytest.raises(ValueError, match="semantic validation after 1 repair attempt"):
        native_compiler.compile_native(
            contract_id="C-1",
            source_documents={"DOC-1": ("Order Form", "Price: $1.50 per supported outcome")},
            metadata={},
            provider="gemini",
            api_key="test-key",
            pin_provider=True,
            max_semantic_repairs=1,
        )

    assert calls == 2


def test_proof_requirement_rejects_unknown_evidence_authority() -> None:
    from app.agreements.compiler_models import ProofRequirementProposal

    with pytest.raises(ValidationError):
        ProofRequirementProposal(
            description="Audit trail proves the contractual event",
            fact_types=["audit_event_exists"],
            preferred_authority="system_audit_log",
        )


@pytest.mark.parametrize(
    "authority",
    [
        "customer_system_of_record",
        "independent_third_party",
        "signed_execution_log",
        "vendor_tool_trace",
    ],
)
def test_proof_requirement_accepts_supported_evidence_authority(
    authority: str,
) -> None:
    from app.agreements.compiler_models import ProofRequirementProposal

    proof = ProofRequirementProposal(
        description="Authoritative evidence proves the contractual fact",
        fact_types=["contractual_fact"],
        preferred_authority=authority,
    )

    assert proof.preferred_authority == authority
