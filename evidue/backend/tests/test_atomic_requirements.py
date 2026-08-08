from __future__ import annotations

from copy import deepcopy

from app.agreements import native_compiler
from app.agreements.compiler import lower_to_agreement_ir
from app.agreements.compiler_models import (
    AgreementCompilationProposal,
    AtomicRequirementProposal,
    ClauseAnalysisProposal,
    ConditionProposal,
    NormProposal,
    ProofRequirementProposal,
    RequirementLedgerProposal,
    SettlementProposal,
    SourceDocumentRef,
)
from app.agreements.legacy import conformance_report
from app.agreements.native_compiler import bind_requirement_ledger_to_sources
from app.agreements.providers import ProviderResult


def _requirement(
    requirement_id: str,
    *,
    statement: str,
    disposition: str = "norm",
    dependencies: list[str] | None = None,
    source_text: str = "Provider must satisfy the contractual condition.",
) -> AtomicRequirementProposal:
    return AtomicRequirementProposal(
        id=requirement_id,
        statement=statement,
        kind="performance" if disposition == "norm" else "pricing",
        materiality="financial",
        data_dependencies=dependencies or ["claim"],
        disposition=disposition,
        source_document_id="DOC-1",
        source_text=source_text,
    )


def _proposal(
    *,
    requirements: list[AtomicRequirementProposal],
    norms: list[NormProposal],
    source_text: str = "Provider must satisfy the contractual condition.",
    settlements: list[SettlementProposal] | None = None,
) -> AgreementCompilationProposal:
    return AgreementCompilationProposal(
        compiler_version="test",
        contract_id="C-1",
        model="test",
        provider="test",
        source_documents=[SourceDocumentRef(document_id="DOC-1", title="Agreement")],
        requirements=requirements,
        clauses=[
            ClauseAnalysisProposal(
                clause_id="C1",
                source_document_id="DOC-1",
                source_text=source_text,
                clause_type="performance",
                norms=norms,
                settlement_effects=settlements or [],
                automation_classification="executable_if_data_available",
            )
        ],
    )


def _lower(proposal: AgreementCompilationProposal):
    return lower_to_agreement_ir(
        proposal,
        compilation_id="COMP-1",
        version=1,
        source_hash="sha256:test",
    )


def test_unmapped_material_atomic_requirement_blocks_approval() -> None:
    proposal = _proposal(
        requirements=[
            _requirement("R-A", statement="The claim must contain a service identifier.")
        ],
        norms=[],
    )

    agreement, report = _lower(proposal)

    assert agreement.requirements[0].binding_status == "unmapped"
    assert any(d.code == "ATOMIC_REQUIREMENT_UNMAPPED" for d in agreement.diagnostics)
    assert report.approvable is False


def test_multiple_atomic_requirements_cannot_collapse_into_one_norm() -> None:
    requirements = [
        _requirement("R-A", statement="Condition A must hold."),
        _requirement("R-B", statement="Condition B must hold."),
    ]
    norm = NormProposal(
        id="N-AB",
        norm_type="obligation",
        subject="vendor",
        condition=ConditionProposal(
            condition_type="field_present",
            parameters={"field": "outcome_id"},
            description="Generic combined condition",
        ),
        consequence="disputed",
        requirement_ids=["R-A", "R-B"],
    )

    agreement, report = _lower(_proposal(requirements=requirements, norms=[norm]))

    assert any(d.code == "ATOMIC_REQUIREMENTS_COLLAPSED" for d in agreement.diagnostics)
    assert report.approvable is False


def test_direct_claim_condition_must_not_depend_on_external_proof() -> None:
    requirement = _requirement(
        "R-DIRECT",
        statement="The claim must contain an outcome identifier.",
        dependencies=["claim"],
    )
    norm = NormProposal(
        id="N-DIRECT",
        norm_type="obligation",
        subject="vendor",
        condition=ConditionProposal(
            condition_type="field_present",
            parameters={"field": "outcome_id"},
            description="Outcome ID is present",
        ),
        consequence="disputed",
        requirement_ids=["R-DIRECT"],
        proof_requirements=[
            ProofRequirementProposal(
                description="External system confirms the identifier",
                fact_types=["outcome_identifier"],
                requirement_ids=["R-DIRECT"],
            )
        ],
    )

    agreement, report = _lower(_proposal(requirements=[requirement], norms=[norm]))

    assert any(
        d.code == "DIRECT_DATA_REQUIREMENT_HAS_EXTERNAL_PROOF" for d in agreement.diagnostics
    )
    assert report.approvable is False


def test_customer_evidence_condition_requires_proof_plan() -> None:
    requirement = _requirement(
        "R-EVIDENCE",
        statement="A downstream success event must exist.",
        dependencies=["customer_evidence"],
    )
    norm = NormProposal(
        id="N-EVIDENCE",
        norm_type="obligation",
        subject="vendor",
        condition=ConditionProposal(
            condition_type="event_exists",
            parameters={"event_types": ["downstream_succeeded"]},
            description="Downstream success exists",
        ),
        consequence="disputed",
        requirement_ids=["R-EVIDENCE"],
    )

    agreement, report = _lower(_proposal(requirements=[requirement], norms=[norm]))

    assert any(d.code == "EVIDENCE_REQUIREMENT_MISSING_PROOF" for d in agreement.diagnostics)
    assert report.approvable is False


def test_batch_uniqueness_does_not_require_external_proof() -> None:
    source = "Only the earliest same-customer claim inside 24 hours is billable."
    requirement = _requirement(
        "R-UNIQUE",
        statement="Only the earliest same-customer claim inside 24 hours is billable.",
        dependencies=["batch_claims", "contract_constant"],
        source_text=source,
    )
    norm = NormProposal(
        id="N-UNIQUE",
        norm_type="obligation",
        subject="vendor",
        condition=ConditionProposal(
            condition_type="duplicate_in_window",
            parameters={
                "group_by": ["customer_id"],
                "order_by": ["closed_at", "outcome_id"],
                "window_value": 24,
                "window_unit": "hours",
            },
            description="Claim is first in the duplicate window",
        ),
        consequence="disputed",
        requirement_ids=["R-UNIQUE"],
    )

    agreement, report = _lower(
        _proposal(requirements=[requirement], norms=[norm], source_text=source)
    )

    blocking_codes = {d.code for d in agreement.diagnostics if d.severity == "blocking"}
    assert "EVIDENCE_REQUIREMENT_MISSING_PROOF" not in blocking_codes
    assert "DIRECT_DATA_REQUIREMENT_HAS_EXTERNAL_PROOF" not in blocking_codes
    assert report.approvable is True


def test_material_clause_without_atomic_requirement_is_blocking() -> None:
    covered_source = "Provider must satisfy condition A."
    uncovered_source = "Provider must also satisfy condition B."
    requirement = _requirement(
        "R-A",
        statement="Condition A must hold.",
        source_text=covered_source,
    )
    norm = NormProposal(
        id="N-A",
        norm_type="obligation",
        subject="vendor",
        condition=ConditionProposal(
            condition_type="field_present",
            parameters={"field": "outcome_id"},
            description="Outcome ID is present",
        ),
        consequence="disputed",
        requirement_ids=["R-A"],
    )
    proposal = _proposal(requirements=[requirement], norms=[norm], source_text=covered_source)
    proposal.clauses.append(
        ClauseAnalysisProposal(
            clause_id="C2",
            source_document_id="DOC-1",
            source_text=uncovered_source,
            clause_type="performance",
            material=True,
            automation_classification="human_attestation_required",
        )
    )

    agreement, report = _lower(proposal)

    assert any(
        d.code == "MATERIAL_CLAUSE_WITHOUT_ATOMIC_REQUIREMENT" for d in agreement.diagnostics
    )
    assert report.approvable is False


def test_requirement_source_binding_uses_immutable_source_bytes() -> None:
    source = "Heading. Price: $1.50 per supported outcome. End."
    ledger = RequirementLedgerProposal(
        ledger_version="test",
        contract_id="C-1",
        requirements=[
            AtomicRequirementProposal(
                id="PRICE",
                statement="The unit price is $1.50.",
                kind="pricing",
                materiality="financial",
                data_dependencies=["contract_constant"],
                disposition="settlement",
                source_document_id="DOC-1",
                source_span_ids=["SPAN-000002"],
                source_text="model paraphrase",
            )
        ],
    )

    bound = bind_requirement_ledger_to_sources(
        ledger,
        expected_contract_id="C-1",
        source_documents={"DOC-1": ("Agreement", source)},
        require_source_spans=True,
    )

    requirement = bound.requirements[0]
    assert requirement.source_text == "Price: $1.50 per supported outcome."
    assert source[requirement.source_start : requirement.source_end] == requirement.source_text
    assert requirement.source_text_hash is not None


def test_native_compiler_runs_independent_requirement_pass_before_air_pass(monkeypatch) -> None:
    source = "Price: $1.50 per supported outcome."
    ledger_payload = {
        "ledger_version": "model-ledger",
        "contract_id": "ignored",
        "requirements": [
            {
                "id": "PRICE",
                "statement": "The unit price is $1.50 per supported outcome.",
                "kind": "pricing",
                "materiality": "financial",
                "data_dependencies": ["contract_constant"],
                "disposition": "settlement",
                "parameters": {"unit_price": "1.50"},
                "source_document_id": "DOC-1",
                "source_span_ids": ["SPAN-000001"],
                "source_text": "model text",
                "review_notes": [],
            }
        ],
    }
    proposal_payload = {
        "compiler_version": "model",
        "contract_id": "ignored",
        "model": "model",
        "provider": "model",
        "source_documents": [{"document_id": "DOC-1", "title": "Agreement"}],
        "definitions": [],
        "requirements": [],
        "clauses": [
            {
                "clause_id": "PRICE",
                "source_document_id": "DOC-1",
                "source_span_ids": ["SPAN-000001"],
                "source_text": "model text",
                "material": True,
                "clause_type": "pricing",
                "norms": [],
                "settlement_effects": [
                    {
                        "id": "PRICE",
                        "settlement_type": "fixed_per_unit",
                        "parameters": {"unit_price": "1.50"},
                        "source_clause_id": "PRICE",
                        "description": "Unit price",
                        "requirement_ids": ["PRICE"],
                    }
                ],
                "automation_classification": "fully_executable",
                "unsupported_concepts": [],
                "diagnostics": [],
            }
        ],
        "global_diagnostics": [],
    }
    results = [
        ProviderResult(
            payload=deepcopy(ledger_payload),
            provider="google-gemini",
            model="test-model",
            prompt_hash="sha256:ledger",
            response_text="ledger",
        ),
        ProviderResult(
            payload=deepcopy(proposal_payload),
            provider="google-gemini",
            model="test-model",
            prompt_hash="sha256:proposal",
            response_text="proposal",
        ),
    ]
    prompts: list[str] = []

    def fake_call_provider(prompt, response_schema, **kwargs):
        prompts.append(prompt)
        return results.pop(0)

    monkeypatch.setattr(native_compiler, "call_provider", fake_call_provider)

    result = native_compiler.compile_native(
        contract_id="C-1",
        source_documents={"DOC-1": ("Agreement", source)},
        metadata={},
        provider="gemini",
        api_key="test-key",
        pin_provider=True,
    )

    assert len(prompts) == 2
    assert "independent atomic-contract-requirement analyzer" in prompts[0]
    assert "AUTHORITATIVE ATOMIC REQUIREMENT LEDGER" in prompts[1]
    assert result.provenance["requirement_count"] == 1
    assert result.proposal.requirements[0].id == "PRICE"
    assert result.proposal.clauses[0].settlement_effects[0].requirement_ids == ["PRICE"]


def test_conformance_blocks_unmapped_material_requirement_even_without_diagnostic() -> None:
    from app.agreements.legacy import conformance_report

    proposal = _proposal(
        requirements=[
            _requirement("R-A", statement="The claim must contain a service identifier.")
        ],
        norms=[],
    )
    agreement, _ = _lower(proposal)
    agreement = agreement.model_copy(update={"diagnostics": []})

    report = conformance_report(agreement)

    assert report.unmapped_material_requirement_count == 1
    assert report.approvable is False


def test_unresolved_material_requirement_blocks_approval() -> None:
    requirement = _requirement(
        "MISSING-RATE",
        statement="The rate is defined by a missing order form.",
        disposition="unresolved_dependency",
        dependencies=["external_document"],
    )
    proposal = _proposal(requirements=[requirement], norms=[])

    air, report = lower_to_agreement_ir(
        proposal,
        compilation_id="AIR-UNRESOLVED",
        version=1,
        source_hash="sha256:test",
    )

    assert report.approvable is False
    assert air.requirements[0].binding_status == "unresolved_dependency"
    assert any(
        diagnostic.code == "MATERIAL_REQUIREMENT_UNRESOLVED" for diagnostic in air.diagnostics
    )


def test_conformance_blocks_unresolved_material_requirement_without_diagnostic() -> None:
    requirement = _requirement(
        "MISSING-RATE",
        statement="The rate is defined by a missing order form.",
        disposition="unresolved_dependency",
        dependencies=["external_document"],
    )
    proposal = _proposal(requirements=[requirement], norms=[])
    air, _ = lower_to_agreement_ir(
        proposal,
        compilation_id="AIR-UNRESOLVED-DEFENSE",
        version=1,
        source_hash="sha256:test",
    )
    air_without_diagnostic = air.model_copy(
        update={
            "diagnostics": [
                diagnostic
                for diagnostic in air.diagnostics
                if diagnostic.code != "MATERIAL_REQUIREMENT_UNRESOLVED"
            ]
        }
    )

    report = conformance_report(air_without_diagnostic)
    assert report.approvable is False
    assert report.unmapped_material_requirement_count == 1
