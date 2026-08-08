"""Cross-domain and safety tests for the generalized agreement runtime."""

from __future__ import annotations

from decimal import Decimal

import pytest
from app.agreements.compiler import lower_to_agreement_ir
from app.agreements.compiler_models import (
    AgreementCompilationProposal,
    ClauseAnalysisProposal,
    ConditionProposal,
    NormProposal,
    SettlementProposal,
    SourceDocumentRef,
)
from app.agreements.models import (
    CommercialClaim,
    Expression,
    Norm,
    NormType,
    ObligationStatus,
    TruthValue,
)
from app.agreements.native_compiler import bind_proposal_to_sources
from app.agreements.runtime import EvaluationContext, calculate_settlement, evaluate_norm
from app.agreements.semantic import (
    SemanticEvidenceSpan,
    SemanticFactRequest,
    SemanticFactResult,
    validate_semantic_result,
)


def _proposal(
    *,
    contract_id: str,
    pricing_text: str,
    settlement: SettlementProposal,
) -> AgreementCompilationProposal:
    performance_text = "Provider must complete the contracted service."
    document_text = f"{performance_text}\n{pricing_text}"
    return AgreementCompilationProposal(
        compiler_version="test-native",
        contract_id=contract_id,
        model="test",
        provider="test",
        source_documents=[SourceDocumentRef(document_id="DOC-1", title=document_text)],
        clauses=[
            ClauseAnalysisProposal(
                clause_id="PERF",
                source_document_id="DOC-1",
                source_text=performance_text,
                clause_type="performance",
                automation_classification="executable_if_data_available",
                norms=[
                    NormProposal(
                        id="N-PERF",
                        norm_type="obligation",
                        subject="provider",
                        condition=ConditionProposal(
                            condition_type="field_present",
                            parameters={"field": "service_completed"},
                            description="Service completion is evidenced",
                        ),
                        consequence="disputed",
                        indeterminate_consequence="needs_review",
                    )
                ],
            ),
            ClauseAnalysisProposal(
                clause_id="PRICE",
                source_document_id="DOC-1",
                source_text=pricing_text,
                clause_type="pricing",
                settlement_effects=[settlement],
            ),
        ],
    )


def test_source_binding_rejects_paraphrased_clause() -> None:
    proposal = AgreementCompilationProposal(
        compiler_version="test",
        contract_id="C1",
        model="test",
        provider="test",
        source_documents=[SourceDocumentRef(document_id="DOC-1", title="Contract")],
        clauses=[
            ClauseAnalysisProposal(
                clause_id="CL-1",
                source_document_id="DOC-1",
                source_text="Provider earns one dollar per outcome.",
                clause_type="pricing",
            )
        ],
    )
    with pytest.raises(ValueError, match="exact substring"):
        bind_proposal_to_sources(
            proposal,
            expected_contract_id="C1",
            source_documents={"DOC-1": ("Contract", "Provider earns $1.00 per outcome.")},
        )


def test_source_binding_attaches_exact_span_and_hash() -> None:
    clause_text = "Provider earns $1.00 per outcome."
    document = f"Heading\n{clause_text}\nEnd"
    proposal = AgreementCompilationProposal(
        compiler_version="test",
        contract_id="C1",
        model="test",
        provider="test",
        source_documents=[SourceDocumentRef(document_id="DOC-1", title="Contract")],
        clauses=[
            ClauseAnalysisProposal(
                clause_id="CL-1",
                source_document_id="DOC-1",
                source_text=clause_text,
                clause_type="pricing",
            )
        ],
    )
    bound = bind_proposal_to_sources(
        proposal,
        expected_contract_id="C1",
        source_documents={"DOC-1": ("Contract", document)},
    )
    clause = bound.clauses[0]
    assert clause.source_start == document.index(clause_text)
    assert clause.source_end == clause.source_start + len(clause_text)
    assert clause.source_text_hash is not None and len(clause.source_text_hash) == 64


def test_source_binding_accepts_layout_only_whitespace_and_canonicalizes() -> None:
    source_clause = "Provider earns $1.00\n\tper outcome."
    model_quote = "Provider earns $1.00 per outcome."
    document = f"Heading\n{source_clause}\nEnd"

    proposal = AgreementCompilationProposal(
        compiler_version="test",
        contract_id="C1",
        model="test",
        provider="test",
        source_documents=[SourceDocumentRef(document_id="DOC-1", title="Contract")],
        clauses=[
            ClauseAnalysisProposal(
                clause_id="CL-1",
                source_document_id="DOC-1",
                source_text=model_quote,
                clause_type="pricing",
            )
        ],
    )

    bound = bind_proposal_to_sources(
        proposal,
        expected_contract_id="C1",
        source_documents={"DOC-1": ("Contract", document)},
    )

    clause = bound.clauses[0]

    assert clause.source_text == source_clause
    assert clause.source_start == document.index(source_clause)
    assert clause.source_end == clause.source_start + len(source_clause)
    assert clause.source_text_hash is not None


def test_unknown_nested_parameters_are_rejected() -> None:
    with pytest.raises(ValueError, match="unsupported parameters"):
        ConditionProposal(
            condition_type="field_equals",
            parameters={"field": "status", "expected_value": "ok", "magic": True},
            description="bad parameter",
        )
    with pytest.raises(ValueError, match="unsupported parameters"):
        SettlementProposal(
            id="S1",
            settlement_type="fixed_per_unit",
            parameters={"unit_price": "1.50", "magic": "money"},
            source_clause_id="PRICE",
            description="bad settlement",
        )


def test_trigger_false_is_not_applicable_and_unknown_is_indeterminate() -> None:
    norm = Norm(
        id="N1",
        norm_type=NormType.OBLIGATION,
        subject="provider",
        trigger=Expression(operator="field", path="claim.triggered"),
        condition=Expression(operator="field", path="claim.performed"),
        consequence="disputed",
        source_clause_ids=["CL1"],
        automation_class="fully_executable",
    )
    assert (
        evaluate_norm(norm, EvaluationContext(fields={"claim": {"triggered": False}}))
        == ObligationStatus.NOT_APPLICABLE
    )
    assert (
        evaluate_norm(norm, EvaluationContext(fields={"claim": {}}))
        == ObligationStatus.INDETERMINATE
    )


def test_tiered_rate_executes_incrementally_with_decimal_money() -> None:
    claim = CommercialClaim(
        id="C",
        claim_type="usage",
        submitted_amount="25.00",
        fields={"units": 15},
    )
    expression = Expression(
        operator="tiered_rate",
        path="claim.units",
        parameters={
            "tiers": [
                {"up_to": "10", "unit_price": "1.00"},
                {"up_to": None, "unit_price": "2.00"},
            ]
        },
    )
    line = calculate_settlement(
        claim,
        expression,
        EvaluationContext(fields={"claim": claim.fields}),
    )
    assert line.payable_amount == "20.00"
    assert line.disputed_amount == "5.00"


def test_percentage_lowering_uses_decimal_ratio() -> None:
    proposal = _proposal(
        contract_id="PERCENT",
        pricing_text="Provider receives 12.5 percent of submitted revenue.",
        settlement=SettlementProposal(
            id="S-PERCENT",
            settlement_type="percentage",
            parameters={"percent": "12.5", "base_field": "submitted_amount"},
            source_clause_id="PRICE",
            description="12.5 percent revenue share",
        ),
    )
    air, report = lower_to_agreement_ir(
        proposal,
        compilation_id="AIR-PERCENT",
        version=1,
        source_hash="hash",
    )
    assert report.approvable
    multiplier = air.settlement_policies[0].amount_expression.operands[1].value
    assert multiplier == "0.125"
    assert Decimal(multiplier) == Decimal("0.125")


@pytest.mark.parametrize(
    ("contract_id", "settlement_type", "parameters"),
    [
        ("AI_OUTCOME", "fixed_per_unit", {"unit_price": "1.50"}),
        ("UPTIME_SLA", "percentage", {"percent": "10"}),
        ("QUALIFIED_MEETING", "fixed_per_unit", {"unit_price": "75"}),
        ("LOGISTICS", "deduction", {"amount": "20"}),
        ("MILESTONE", "fixed_per_unit", {"unit_price": "5000"}),
        (
            "USAGE_SAAS",
            "tiered_rate",
            {
                "quantity_field": "units",
                "tiers": [
                    {"up_to": "1000", "unit_price": "0.10"},
                    {"up_to": None, "unit_price": "0.05"},
                ],
            },
        ),
        (
            "BPO_SLA",
            "rate_table",
            {"lookup_field": "service_level", "rates": {"gold": "10", "silver": "5"}},
        ),
        ("REVENUE_SHARE", "percentage", {"percent": "15", "base_field": "revenue"}),
    ],
)
def test_cross_domain_settlement_compiles_without_contract_specific_code(
    contract_id: str,
    settlement_type: str,
    parameters: dict[str, object],
) -> None:
    pricing_text = f"Pricing clause for {contract_id}."
    proposal = _proposal(
        contract_id=contract_id,
        pricing_text=pricing_text,
        settlement=SettlementProposal(
            id=f"S-{contract_id}",
            settlement_type=settlement_type,  # type: ignore[arg-type]
            parameters=parameters,
            source_clause_id="PRICE",
            description="Cross-domain settlement",
        ),
    )
    air, report = lower_to_agreement_ir(
        proposal,
        compilation_id=f"AIR-{contract_id}",
        version=1,
        source_hash="fixture-hash",
    )
    assert report.approvable is True
    assert len(air.settlement_policies) == 1
    assert air.settlement_policies[0].source_clause_ids == ["NATIVE-PRICE"]


def test_semantic_fact_binds_exact_citations_and_low_confidence_abstains() -> None:
    request = SemanticFactRequest(
        fact_type="customer_requested_human",
        question="Did the customer explicitly request a human agent?",
        artifact_ids=["MSG-1"],
    )
    artifacts = {"MSG-1": "Please transfer me to a human agent."}
    result = SemanticFactResult(
        fact_type=request.fact_type,
        truth=TruthValue.TRUE,
        confidence=0.60,
        citations=[
            SemanticEvidenceSpan(
                artifact_id="MSG-1",
                span_id="MSG-1:0",
                quote="transfer me to a human agent",
            )
        ],
        explanation="Explicit request",
        model="test-model",
        prompt_version="test",
        input_hash="placeholder",
    )
    bound = validate_semantic_result(
        result,
        request=request,
        artifacts=artifacts,
        minimum_confidence=0.85,
    )
    assert bound.truth == TruthValue.UNKNOWN
    assert bound.requires_review is True
    assert bound.input_hash.startswith("sha256:")


def test_semantic_fact_rejects_invented_quote() -> None:
    request = SemanticFactRequest(
        fact_type="customer_requested_human",
        question="Did the customer explicitly request a human agent?",
        artifact_ids=["MSG-1"],
    )
    result = SemanticFactResult(
        fact_type=request.fact_type,
        truth=TruthValue.TRUE,
        confidence=0.99,
        citations=[SemanticEvidenceSpan(artifact_id="MSG-1", span_id="x", quote="invented")],
        explanation="bad",
        model="test",
        prompt_version="test",
        input_hash="x",
    )
    with pytest.raises(ValueError, match="exact span"):
        validate_semantic_result(
            result,
            request=request,
            artifacts={"MSG-1": "Actual message"},
            minimum_confidence=0.85,
        )


def test_absence_requirement_is_not_ready_without_absence_capability() -> None:
    from app.agreements.capabilities import (
        EvidenceCapability,
        EvidenceSourceDescriptor,
        ProofPlanStatus,
        build_verification_plan,
    )
    from app.agreements.models import EvidenceAuthority, ProofRequirement

    requirement = ProofRequirement(
        id="PR-ABSENCE",
        norm_id="N1",
        predicate_id="P1",
        description="Prove no reopening event occurred",
        acceptable_fact_types=["conversation_not_reopened"],
        preferred_authority=EvidenceAuthority.CUSTOMER_SYSTEM_OF_RECORD,
        acceptable_authorities=[EvidenceAuthority.CUSTOMER_SYSTEM_OF_RECORD],
        requires_absence_proof=True,
    )
    source = EvidenceSourceDescriptor(
        source_id="support",
        source_type="support",
        system="customer-support-system",
        capabilities=[
            EvidenceCapability(
                fact_type="conversation_not_reopened",
                entity_type="commercial_claim",
                authority=EvidenceAuthority.CUSTOMER_SYSTEM_OF_RECORD,
                absence_provable=False,
            )
        ],
    )
    plan = build_verification_plan("AIR-1", [requirement], [source])
    assert plan.items[0].status != ProofPlanStatus.READY
    assert "absence_proof" in plan.items[0].missing_capabilities


def test_agreement_bundle_rejects_relation_cycle() -> None:
    from datetime import datetime

    from app.agreements.bundle import (
        AgreementBundle,
        AgreementDocument,
        DocumentRelation,
        DocumentRelationType,
    )

    docs = [
        AgreementDocument(
            id="A",
            title="A",
            text="A",
            effective_from=datetime(2026, 1, 1),
            precedence=10,
            source_hash="a",
        ),
        AgreementDocument(
            id="B",
            title="B",
            text="B",
            effective_from=datetime(2026, 2, 1),
            precedence=20,
            source_hash="b",
        ),
    ]
    with pytest.raises(ValueError, match="circular"):
        AgreementBundle(
            id="BUNDLE",
            parties={"customer": "Buyer", "vendor": "Provider"},
            documents=docs,
            relations=[
                DocumentRelation(
                    source_document_id="A",
                    target_document_id="B",
                    relation=DocumentRelationType.INCORPORATES,
                ),
                DocumentRelation(
                    source_document_id="B",
                    target_document_id="A",
                    relation=DocumentRelationType.INCORPORATES,
                ),
            ],
        )
