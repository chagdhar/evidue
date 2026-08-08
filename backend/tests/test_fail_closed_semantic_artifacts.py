from __future__ import annotations

from copy import deepcopy

from app.agreements import native_compiler
from app.agreements.compiler_models import (
    AtomicRequirementProposal,
    RequirementLedgerProposal,
)
from app.agreements.providers import ProviderResult


def _requirement_ledger() -> RequirementLedgerProposal:
    return RequirementLedgerProposal(
        ledger_version="test-ledger",
        contract_id="C-1",
        requirements=[
            AtomicRequirementProposal(
                id="PRICE-RATE",
                statement="Supported outcomes are priced at $1.50 per outcome.",
                kind="pricing",
                materiality="financial",
                data_dependencies=["contract_constant"],
                disposition="settlement",
                parameters={"unit_price": "1.50"},
                source_document_id="DOC-1",
                source_span_ids=["SPAN-000001"],
                source_text="Price: $1.50 per supported outcome",
            )
        ],
    )


def _payload(*, unit_price: str | None) -> dict:
    parameters = {} if unit_price is None else {"unit_price": unit_price}
    return {
        "compiler_version": "model-value-overridden",
        "contract_id": "model-value-overridden",
        "model": "model-value-overridden",
        "provider": "model-value-overridden",
        "source_documents": [{"document_id": "DOC-1", "title": "Order Form"}],
        "requirements": [
            {
                "id": "PRICE-RATE",
                "statement": "Supported outcomes are priced at $1.50 per outcome.",
                "kind": "pricing",
                "materiality": "financial",
                "data_dependencies": ["contract_constant"],
                "disposition": "settlement",
                "parameters": {"unit_price": "1.50"},
                "source_document_id": "DOC-1",
                "source_span_ids": ["SPAN-000001"],
                "source_text": "Price: $1.50 per supported outcome",
                "source_start": None,
                "source_end": None,
                "source_text_hash": None,
                "review_notes": [],
            }
        ],
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
                        "requirement_ids": ["PRICE-RATE"],
                    }
                ],
                "automation_classification": "fully_executable",
                "unsupported_concepts": [],
                "diagnostics": [],
            }
        ],
        "global_diagnostics": [],
    }


def test_exhausted_settlement_repair_fails_closed(monkeypatch) -> None:
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

    result = native_compiler.compile_native(
        contract_id="C-1",
        source_documents={"DOC-1": ("Order Form", "Price: $1.50 per supported outcome")},
        metadata={},
        provider="gemini",
        api_key="test-key",
        pin_provider=True,
        max_semantic_repairs=1,
        requirement_ledger=_requirement_ledger(),
    )

    assert calls == 2
    clause = result.proposal.clauses[0]
    assert clause.settlement_effects == []
    assert clause.automation_classification == "human_attestation_required"
    assert clause.diagnostics[-1].code == "SEMANTIC_COMPILER_ARTIFACT_REJECTED"
    assert result.provenance["degraded_after_semantic_repair"] is True
    assert result.provenance["degraded_artifacts"][0]["artifact_kind"] == "settlement_effects"


def test_invalid_norm_is_removed_without_inventing_replacement_semantics() -> None:
    payload = _payload(unit_price="1.50")
    payload["clauses"][0]["norms"] = [
        {
            "id": "N-BAD",
            "norm_type": "prohibition",
            "subject": "Vendor",
            "beneficiary": "Customer",
            "trigger": None,
            "condition": {
                "condition_type": "all_of",
                "parameters": {},
                "description": "Malformed composite condition",
            },
            "exceptions": [],
            "consequence": "disputed",
            "indeterminate_consequence": "needs_review",
            "proof_requirements": [],
            "violation_reason_code": "BAD",
            "violation_reason": "Bad",
            "indeterminate_reason_code": "BAD_REVIEW",
            "indeterminate_reason": "Review",
            "confidence": 1.0,
            "ambiguity_notes": [],
        }
    ]

    degraded = native_compiler._degrade_invalid_executable_artifacts(
        payload=payload,
        issues=[
            {
                "location": "clauses.0.norms.0.condition",
                "type": "value_error",
                "message": "Value error, all_of requires 'conditions'",
            }
        ],
    )

    assert degraded is not None
    proposal, artifacts = degraded
    clause = proposal.clauses[0]
    assert clause.norms == []
    assert clause.automation_classification == "human_attestation_required"
    assert artifacts == [
        {
            "clause_index": 0,
            "clause_id": "PRICE-1",
            "artifact_kind": "norms",
            "artifact_index": 0,
            "artifact_id": "N-BAD",
        }
    ]
    assert clause.diagnostics[-1].code == "SEMANTIC_COMPILER_ARTIFACT_REJECTED"
    assert clause.diagnostics[-1].severity == "blocking"
