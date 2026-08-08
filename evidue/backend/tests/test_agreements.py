from __future__ import annotations

from datetime import datetime

from app.agreements import (
    AgreementBundle,
    AgreementDocument,
    AutomationClass,
    CommercialClaim,
    DocumentRelation,
    DocumentRelationType,
    EvaluationContext,
    EvidenceAuthority,
    EvidenceCapability,
    EvidenceSourceDescriptor,
    Expression,
    Fact,
    Norm,
    NormType,
    ObligationStatus,
    TruthValue,
    applicable_documents,
    build_verification_plan,
    calculate_settlement,
    evaluate_expression,
    evaluate_norm,
)
from app.agreements.capabilities import ProofPlanStatus
from app.contracts.compiler import (
    ClauseCoverage,
    CompilerDiagnostic,
    agreement_artifacts_for_proposal,
    load_recorded_proposal,
)


def test_agreement_bundle_resolves_superseded_documents() -> None:
    bundle = AgreementBundle(
        id="BUNDLE-1",
        parties={"customer": "Acme", "provider": "Nova"},
        documents=[
            AgreementDocument(
                id="MSA",
                title="Master agreement",
                text="Original terms",
                effective_from=datetime(2026, 1, 1),
                precedence=10,
                source_hash="sha256:msa",
            ),
            AgreementDocument(
                id="AMENDMENT-1",
                title="Amendment",
                text="Replacement terms",
                effective_from=datetime(2026, 6, 1),
                precedence=20,
                source_hash="sha256:amendment",
            ),
        ],
        relations=[
            DocumentRelation(
                source_document_id="AMENDMENT-1",
                target_document_id="MSA",
                relation=DocumentRelationType.SUPERSEDES,
            )
        ],
    )

    effective = applicable_documents(bundle, datetime(2026, 7, 1))

    assert [document.id for document in effective] == ["AMENDMENT-1"]


def test_four_valued_logic_preserves_conflicting_facts() -> None:
    expression = Expression(
        operator="and",
        operands=[
            Expression(operator="fact", path="work.completed"),
            Expression(operator="fact", path="work.accepted"),
        ],
    )
    context = EvaluationContext(
        fields={},
        facts={
            "work.completed": Fact(
                id="F1",
                fact_type="work.completed",
                truth=TruthValue.TRUE,
                authority=EvidenceAuthority.CUSTOMER_SYSTEM_OF_RECORD,
            ),
            "work.accepted": Fact(
                id="F2",
                fact_type="work.accepted",
                truth=TruthValue.CONFLICTING,
                authority=EvidenceAuthority.CUSTOMER_SYSTEM_OF_RECORD,
            ),
        },
    )

    assert evaluate_expression(expression, context).truth == TruthValue.CONFLICTING


def test_norm_evaluation_distinguishes_unknown_from_not_applicable() -> None:
    norm = Norm(
        id="N1",
        norm_type=NormType.OBLIGATION,
        subject="provider",
        trigger=Expression(operator="fact", path="claim.in_scope"),
        condition=Expression(operator="fact", path="work.completed"),
        consequence="withhold payment",
        source_clause_ids=["C1"],
        automation_class=AutomationClass.EXECUTABLE_IF_DATA_AVAILABLE,
    )
    out_of_scope = EvaluationContext(
        fields={},
        facts={
            "claim.in_scope": Fact(
                id="F1",
                fact_type="claim.in_scope",
                truth=TruthValue.FALSE,
                authority=EvidenceAuthority.CUSTOMER_SYSTEM_OF_RECORD,
            )
        },
    )
    missing_work_fact = EvaluationContext(
        fields={},
        facts={
            "claim.in_scope": Fact(
                id="F2",
                fact_type="claim.in_scope",
                truth=TruthValue.TRUE,
                authority=EvidenceAuthority.CUSTOMER_SYSTEM_OF_RECORD,
            )
        },
    )

    assert evaluate_norm(norm, out_of_scope) == ObligationStatus.NOT_APPLICABLE
    assert evaluate_norm(norm, missing_work_fact) == ObligationStatus.INDETERMINATE


def test_generic_rate_table_calculates_without_vendor_specific_code() -> None:
    claim = CommercialClaim(
        id="CLAIM-1",
        claim_type="service_unit",
        submitted_amount="15.00",
        fields={"outcome_type": "qualified", "units": 2},
    )
    expression = Expression(
        operator="cap",
        operands=[
            Expression(
                operator="multiply",
                operands=[
                    Expression(
                        operator="rate_table",
                        path="claim.outcome_type",
                        parameters={"rates": {"qualified": "9.00", "resolved": "1.00"}},
                    ),
                    Expression(operator="field", path="claim.units"),
                ],
            ),
            Expression(operator="constant", value="15.00"),
        ],
    )

    result = calculate_settlement(
        claim,
        expression,
        EvaluationContext(fields={"claim": claim.fields}),
    )

    assert result.payable_amount == "15.00"
    assert result.disputed_amount == "0.00"


def test_recorded_compilation_produces_approvable_agreement_ir() -> None:
    result = load_recorded_proposal()

    agreement, report = agreement_artifacts_for_proposal(
        result.proposal,
        compilation_id="COMP-AIR-TEST",
        version=1,
        source_hash=result.source_hash,
    )

    assert len(agreement.norms) == len(result.proposal.rules)
    assert len(agreement.proof_requirements) == len(result.proposal.rules)
    assert report.approvable is True
    assert report.coverage_percent == 100.0


def test_unresolved_material_clause_blocks_agreement_conformance() -> None:
    result = load_recorded_proposal()
    unresolved_text = "Provider will use commercially reasonable efforts."
    proposal = result.proposal.model_copy(
        update={
            "clause_coverage": [
                *result.proposal.clause_coverage,
                ClauseCoverage(
                    clause_id="UNSUPPORTED-1",
                    clause_text=unresolved_text,
                    status="needs_review",
                    explanation="The contract does not define an objective standard.",
                ),
            ],
            "diagnostics": [
                CompilerDiagnostic(
                    code="UNSUPPORTED_STANDARD",
                    severity="blocking",
                    message="Commercially reasonable efforts requires human resolution.",
                    clause_text=unresolved_text,
                    suggested_action="Add measurable acceptance criteria.",
                )
            ],
        }
    )

    _, report = agreement_artifacts_for_proposal(
        proposal,
        compilation_id="COMP-AIR-BLOCKED",
        version=1,
        source_hash=result.source_hash,
    )

    assert report.approvable is False
    assert report.unsupported_count == 1
    assert report.blocking_diagnostic_count == 1


def test_capability_registry_plans_by_fact_type_not_connector_name() -> None:
    result = load_recorded_proposal()
    agreement, _ = agreement_artifacts_for_proposal(
        result.proposal,
        compilation_id="COMP-AIR-PLAN",
        version=1,
        source_hash=result.source_hash,
    )
    requirement = agreement.proof_requirements[0]
    fact_type = requirement.acceptable_fact_types[0]

    plan = build_verification_plan(
        agreement.agreement_id,
        [requirement],
        [
            EvidenceSourceDescriptor(
                source_id="SOURCE-1",
                source_type="customer_system",
                system="any-compatible-system",
                capabilities=[
                    EvidenceCapability(
                        fact_type=fact_type,
                        entity_type="commercial_claim",
                        authority=EvidenceAuthority.CUSTOMER_SYSTEM_OF_RECORD,
                        identity_keys=["outcome_id"],
                    )
                ],
            )
        ],
    )

    assert plan.items[0].status == ProofPlanStatus.READY
    assert plan.items[0].selected_source_ids == ["SOURCE-1"]


def test_air_dual_run_produces_exact_equivalence_on_10k_demo_fixture() -> None:
    """The Agreement IR runtime must produce identical determinations to the
    legacy deterministic engine on the full 10,000-claim demo fixture.

    This is the gate for switching the financial authority to AIR.
    """
    from app.agreements.evaluation import dual_run
    from app.agreements.legacy import legacy_rule_program_to_agreement_ir
    from app.contracts.compiler import recorded_rule_program
    from app.fixtures.demo import demo_fixture

    records = demo_fixture()
    claim_evidence = [(r.claim, list(r.events)) for r in records]
    program = recorded_rule_program()
    air = legacy_rule_program_to_agreement_ir(program)

    result = dual_run(claim_evidence, air, program)

    assert result["total_claims"] == 10000
    assert result["status_matches"] == 10000
    assert result["status_mismatches"] == 0
    assert result["amounts_match"] is True
    assert result["legacy_payable"] == "12480.00"
    assert result["legacy_disputed"] == "2520.00"
    assert result["legacy_review"] == "0.00"
    assert result["air_payable"] == "12480.00"
    assert result["air_disputed"] == "2520.00"
    assert result["air_review"] == "0.00"


def test_air_settlement_policy_is_present_and_traceable() -> None:
    """Settlement policy must exist, reference eligibility norms, and trace to clauses."""
    from app.contracts.compiler import agreement_artifacts_for_proposal, load_recorded_proposal

    result = load_recorded_proposal()
    agreement, report = agreement_artifacts_for_proposal(
        result.proposal,
        compilation_id="COMP-SETTLE-TEST",
        version=1,
        source_hash=result.source_hash,
    )

    assert len(agreement.settlement_policies) == 1
    policy = agreement.settlement_policies[0]
    assert policy.id == "SETTLEMENT-1"
    assert policy.claim_type == "outcome"
    assert len(policy.eligibility_norm_ids) > 0
    assert len(policy.source_clause_ids) > 0
    # Eligibility norms should not include the duplicate-attribution norm
    norm_ids = {n.id for n in agreement.norms}
    for eid in policy.eligibility_norm_ids:
        assert eid in norm_ids
    # Source clauses should all exist
    clause_ids = {c.id for c in agreement.clauses}
    for cid in policy.source_clause_ids:
        assert cid in clause_ids
    assert report.settlement_policy_count == 1


def test_air_field_mismatch_norm_requires_evidence_availability() -> None:
    """R5 logic is executable, but it still requires operational evidence."""
    from app.agreements.legacy import legacy_rule_program_to_agreement_ir
    from app.contracts.compiler import recorded_rule_program

    program = recorded_rule_program()
    air = legacy_rule_program_to_agreement_ir(program)

    r5_norm = next(n for n in air.norms if n.legacy_rule_id == "R5")
    assert r5_norm.automation_class == "executable_if_data_available"
    assert r5_norm.condition.operator == "exists_event"
    assert "dynamic_field_equals" in r5_norm.condition.parameters


def test_air_missing_terminal_evidence_matches_legacy_needs_review() -> None:
    from app.agreements.evaluation import dual_run
    from app.agreements.legacy import legacy_rule_program_to_agreement_ir
    from app.contracts.compiler import recorded_rule_program
    from app.fixtures.demo import demo_fixture

    record = next(
        item
        for item in demo_fixture()
        if any(event.event_type == "downstream_succeeded" for event in item.events)
    )
    events = [
        event
        for event in record.events
        if event.event_type not in {"downstream_succeeded", "downstream_failed"}
    ]
    program = recorded_rule_program()
    report = dual_run(
        [(record.claim, events)],
        legacy_rule_program_to_agreement_ir(program),
        program,
    )

    assert report["exact_mismatches"] == 0
    assert report["air_review"] == "1.50"
    assert report["air_disputed"] == "0.00"


def test_rate_table_normalizes_boolean_keys() -> None:
    expression = Expression(
        operator="rate_table",
        path="settlement.eligible_flag",
        parameters={"rates": {"true": "1", "false": "0"}},
    )

    true_result = evaluate_expression(
        expression,
        EvaluationContext(fields={"settlement": {"eligible_flag": True}}),
    )
    false_result = evaluate_expression(
        expression,
        EvaluationContext(fields={"settlement": {"eligible_flag": False}}),
    )

    assert str(true_result.value) == "1"
    assert str(false_result.value) == "0"


def test_terminal_event_outcome_is_unknown_when_evidence_is_absent() -> None:
    expression = Expression(
        operator="terminal_event_outcome",
        parameters={
            "success_event_types": ["completed"],
            "failure_event_types": ["failed"],
            "window": {
                "anchor_path": "claim.started_at",
                "value": 2,
                "unit": "hours",
            },
        },
    )
    result = evaluate_expression(
        expression,
        EvaluationContext(fields={"claim": {"started_at": datetime(2026, 1, 1, 12)}}),
    )

    assert result.truth == TruthValue.UNKNOWN
