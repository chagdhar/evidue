from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from hashlib import sha256

from app.agreements.adjudication import evaluate_claim
from app.agreements.models import (
    AgreementIR,
    AutomationClass,
    ClauseCoverage,
    Expression,
    Norm,
    NormType,
    SettlementPolicy,
    SourceClause,
)
from app.agreements.presentation import agreement_finance_view, render_norm, render_settlement
from app.agreements.qualification import (
    QualificationFinancialScenario,
    QualificationGold,
    QualificationGoldTerm,
    QualificationScenarioEvent,
    QualificationScenarioSet,
    run_financial_scenarios,
    score_agreement,
)
from app.domain.models import OutcomeClaim


def _clause(clause_id: str, document_id: str, text: str) -> SourceClause:
    return SourceClause(
        id=clause_id,
        document_id=document_id,
        text=text,
        source_start=0,
        source_end=len(text),
        text_hash=sha256(text.encode()).hexdigest(),
    )


def _agreement(*, rate: str = "1.50") -> AgreementIR:
    exclusion_text = (
        "A resolution is not payable if the customer contacts support again within 7 days."
    )
    pricing_text = f"Each eligible resolution is charged at USD {rate}."
    exclusion = _clause("CLAUSE-1", "order-form", exclusion_text)
    pricing = _clause("CLAUSE-2", "order-form", pricing_text)
    norm = Norm(
        id="NORM-1",
        norm_type=NormType.PROHIBITION,
        subject="outcome",
        condition=Expression(
            operator="exists_event",
            parameters={
                "event_types": ["customer_recontact"],
                "window": {"anchor_path": "claim.closed_at", "value": 7, "unit": "days"},
            },
        ),
        consequence="disputed",
        source_clause_ids=["CLAUSE-1"],
        automation_class=AutomationClass.EXECUTABLE_IF_DATA_AVAILABLE,
    )
    policy = SettlementPolicy(
        id="PRICE-1",
        claim_type="outcome",
        amount_expression=Expression(operator="constant", value=rate),
        source_clause_ids=["CLAUSE-2"],
        currency="USD",
    )
    return AgreementIR(
        agreement_id="QUAL-AGREEMENT",
        source_hash="sha256:test",
        clauses=[exclusion, pricing],
        norms=[norm],
        predicates=[],
        proof_requirements=[],
        settlement_policies=[policy],
        coverage=[
            ClauseCoverage(
                clause_id="CLAUSE-1",
                clause_text=exclusion_text,
                classification=AutomationClass.EXECUTABLE_IF_DATA_AVAILABLE,
                norm_ids=["NORM-1"],
                rationale="Executable with support-event evidence.",
            ),
            ClauseCoverage(
                clause_id="CLAUSE-2",
                clause_text=pricing_text,
                classification=AutomationClass.FULLY_EXECUTABLE,
                norm_ids=[],
                rationale="Pricing term represented by settlement policy.",
            ),
        ],
    )


def test_finance_renderer_is_derived_from_executable_semantics():
    agreement = _agreement()
    rule = render_norm(agreement.norms[0])
    price = render_settlement(agreement.settlement_policies[0])
    assert rule == "Not payable if a customer recontact event occurs within 7 days."
    assert price == "Pay USD 1.50 per eligible claim."
    view = agreement_finance_view(agreement)
    assert view["contract_rules"][0]["description"] == rule
    assert view["pricing_terms"][0]["description"] == price


def test_qualification_scores_financial_materiality_and_exact_parameters():
    agreement = _agreement()
    gold = QualificationGold(
        pack_id="qual-pack",
        review_status="human_reviewed",
        exhaustive_financial_terms=True,
        terms=[
            QualificationGoldTerm(
                id="GOLD-EXCLUSION",
                description="Seven-day recontact exclusion",
                source_document_id="order-form",
                source_phrase="not payable if the customer contacts support again within 7 days",
                expected_kind="norm",
                expected_norm_type="prohibition",
                expected_consequence="disputed",
                expected_automation="executable_if_data_available",
                expected_numeric_values=["7"],
            ),
            QualificationGoldTerm(
                id="GOLD-PRICE",
                description="Per-resolution rate",
                source_document_id="order-form",
                source_phrase="charged at USD 1.50",
                expected_kind="settlement",
                expected_numeric_values=["1.50"],
            ),
        ],
    )
    result = score_agreement(agreement, gold)
    assert result["critical_financial_term_recall_percent"] == 100.0
    assert result["unsupported_executable_financial_rules"] == []
    assert result["critical_numeric_parameter_mismatches"] == []
    assert result["qualification_passed"] is True

    changed = _agreement(rate="1.75")
    # Updating source text to contain 1.50 would mask the semantic mismatch. Instead,
    # create a gold label that expects the actual clause but a different financial parameter.
    changed_gold = gold.model_copy(deep=True)
    changed_gold.terms[1].source_phrase = "charged at USD 1.75"
    result = score_agreement(changed, changed_gold)
    assert result["qualification_passed"] is False
    assert result["critical_numeric_parameter_mismatches"] == [
        {"id": "GOLD-PRICE", "values": ["1.50"]}
    ]


def test_qualification_fails_closed_on_subjective_automatic_rule():
    text = "Vendor will use commercially reasonable efforts to provide satisfactory assistance."
    clause = _clause("CLAUSE-S", "msa", text)
    agreement = AgreementIR(
        agreement_id="SUBJECTIVE",
        source_hash="sha256:test",
        clauses=[clause],
        norms=[
            Norm(
                id="NORM-S",
                norm_type=NormType.OBLIGATION,
                subject="vendor",
                condition=Expression(operator="constant", value=True),
                consequence="payable",
                source_clause_ids=["CLAUSE-S"],
                automation_class=AutomationClass.FULLY_EXECUTABLE,
            )
        ],
        predicates=[],
        proof_requirements=[],
        settlement_policies=[],
        coverage=[
            ClauseCoverage(
                clause_id="CLAUSE-S",
                clause_text=text,
                classification=AutomationClass.FULLY_EXECUTABLE,
                norm_ids=["NORM-S"],
                rationale="Incorrectly automated for test purposes.",
            )
        ],
    )
    gold = QualificationGold(
        pack_id="subjective",
        review_status="human_reviewed",
        terms=[
            QualificationGoldTerm(
                id="GOLD-S",
                description="Subjective reasonable-efforts clause",
                source_document_id="msa",
                source_phrase="commercially reasonable efforts",
                expected_kind="manual_or_unsupported",
            )
        ],
    )
    result = score_agreement(agreement, gold)
    assert result["qualification_passed"] is False
    assert result["silent_subjective_automation"] == ["GOLD-S"]


def test_provisional_or_non_exhaustive_gold_cannot_claim_release_qualification():
    agreement = _agreement()
    provisional = QualificationGold(
        pack_id="qual-pack",
        review_status="provisional_engineering_gold",
        exhaustive_financial_terms=True,
        terms=[
            QualificationGoldTerm(
                id="GOLD-EXCLUSION",
                description="Seven-day recontact exclusion",
                source_document_id="order-form",
                source_phrase="not payable if the customer contacts support again within 7 days",
                expected_kind="norm",
                expected_numeric_values=["7"],
            ),
            QualificationGoldTerm(
                id="GOLD-PRICE",
                description="Per-resolution rate",
                source_document_id="order-form",
                source_phrase="charged at USD 1.50",
                expected_kind="settlement",
                expected_numeric_values=["1.50"],
            ),
        ],
    )
    result = score_agreement(agreement, provisional)
    assert result["metric_gate_passed"] is True
    assert result["qualification_passed"] is False
    assert result["qualification_status"] == "review_required"

    human_but_partial = provisional.model_copy(deep=True)
    human_but_partial.review_status = "human_reviewed"
    human_but_partial.exhaustive_financial_terms = False
    result = score_agreement(agreement, human_but_partial)
    assert result["metric_gate_passed"] is True
    assert result["qualification_passed"] is False
    assert result["qualification_status"] == "review_required"


def test_qualification_without_reviewed_gold_never_reports_pass():
    result = score_agreement(_agreement(), None)
    assert result["structural_validation_passed"] is True
    assert result["qualification_passed"] is False
    assert result["qualification_status"] == "review_required"
    assert "unqualified" in result["warning"]


def test_qualification_rejects_ungrounded_pricing_policy():
    agreement = _agreement().model_copy(deep=True)
    agreement.settlement_policies[0].source_clause_ids = ["MISSING-CLAUSE"]
    gold = QualificationGold(
        pack_id="qual-pack",
        review_status="human_reviewed",
        exhaustive_financial_terms=False,
        terms=[
            QualificationGoldTerm(
                id="GOLD-EXCLUSION",
                description="Seven-day recontact exclusion",
                source_document_id="order-form",
                source_phrase="not payable if the customer contacts support again within 7 days",
                expected_kind="norm",
                expected_numeric_values=["7"],
            )
        ],
    )
    result = score_agreement(agreement, gold)
    assert result["qualification_passed"] is False
    assert result["ungrounded_pricing_policies"] == ["PRICE-1"]


def test_reviewed_financial_scenarios_validate_contract_to_dollars():
    agreement = _agreement()
    scenarios = QualificationScenarioSet(
        pack_id="qual-pack",
        review_status="human_reviewed",
        scenarios=[
            QualificationFinancialScenario(
                id="SCENARIO-PAYABLE",
                description="No disqualifying recontact",
                outcome_id="OUT-PAY",
                customer_id="CUST-PAY",
                intent="support",
                closed_at="2026-06-01T00:00:00Z",
                expected_action="support",
                account_id="ACC-PAY",
                billed_amount="1.50",
                expected_status="payable",
                expected_payable_amount="1.50",
                expected_disputed_amount="0.00",
                expected_needs_review_amount="0.00",
            ),
            QualificationFinancialScenario(
                id="SCENARIO-DISPUTED",
                description="Customer recontacts inside the contractual window",
                outcome_id="OUT-DISPUTE",
                customer_id="CUST-DISPUTE",
                intent="support",
                closed_at="2026-06-01T00:00:00Z",
                expected_action="support",
                account_id="ACC-DISPUTE",
                billed_amount="1.50",
                events=[
                    QualificationScenarioEvent(
                        id="EV-1",
                        source_system="support",
                        source_record_id="TICKET-1",
                        event_type="customer_recontact",
                        timestamp="2026-06-03T00:00:00Z",
                        customer_id="CUST-DISPUTE",
                        outcome_id="OUT-DISPUTE",
                    )
                ],
                expected_status="disputed",
                expected_payable_amount="0.00",
                expected_disputed_amount="1.50",
                expected_needs_review_amount="0.00",
            ),
        ],
    )
    report = run_financial_scenarios(agreement, scenarios)
    assert report["passed"] is True
    assert all(item["passed"] for item in report["scenarios"])

    provisional = scenarios.model_copy(deep=True)
    provisional.review_status = "provisional_engineering_gold"
    report = run_financial_scenarios(agreement, provisional)
    assert report["metric_gate_passed"] is True
    assert report["passed"] is False
    assert report["status"] == "review_required"


def test_multiple_contract_currencies_fail_closed_to_needs_review():
    agreement = _agreement()
    agreement = agreement.model_copy(
        update={
            "settlement_policies": [
                agreement.settlement_policies[0],
                SettlementPolicy(
                    id="PRICE-EUR",
                    claim_type="outcome",
                    amount_expression=Expression(operator="constant", value="1.25"),
                    source_clause_ids=["CLAUSE-2"],
                    currency="EUR",
                ),
            ]
        }
    )
    claim = OutcomeClaim(
        outcome_id="OUT-1",
        invoice_id="INV-1",
        customer_id="CUST-1",
        intent="support",
        vendor_claim="claimed",
        closed_at=datetime(2026, 6, 1),
        expected_action="support",
        account_id="ACC-1",
        billed_amount=Decimal("1.50"),
    )
    result = evaluate_claim(claim, [], agreement)
    assert result.status == "needs_review"
    assert "multiple currencies" in result.reason


def test_redacted_critical_parameter_cannot_be_invented_or_executed():
    text = "Customer will pay the Annual Fee of [***] per year."
    clause = _clause("CLAUSE-REDACTED", "order-form", text)
    agreement = AgreementIR(
        agreement_id="REDACTED",
        source_hash="sha256:test",
        clauses=[clause],
        norms=[],
        predicates=[],
        proof_requirements=[],
        settlement_policies=[
            SettlementPolicy(
                id="PRICE-INVENTED",
                claim_type="outcome",
                amount_expression=Expression(operator="constant", value="30"),
                source_clause_ids=["CLAUSE-REDACTED"],
                currency="USD",
            )
        ],
        coverage=[
            ClauseCoverage(
                clause_id="CLAUSE-REDACTED",
                clause_text=text,
                classification=AutomationClass.FULLY_EXECUTABLE,
                norm_ids=[],
                rationale="Incorrectly invented for test purposes.",
            )
        ],
    )
    gold = QualificationGold(
        pack_id="redacted",
        review_status="human_reviewed",
        exhaustive_financial_terms=True,
        terms=[
            QualificationGoldTerm(
                id="GOLD-REDACTED",
                description="Annual fee amount is redacted and must remain unknown",
                materiality="critical_financial",
                source_document_id="order-form",
                source_phrase="Annual Fee of [***] per year",
                expected_kind="manual_or_unsupported",
                numeric_parameter_must_be_unknown=True,
                must_not_be_executable=True,
                forbidden_numeric_values=["30"],
            )
        ],
    )
    result = score_agreement(agreement, gold)
    assert result["qualification_passed"] is False
    assert result["hard_failures"]
    issues = result["terms"][0]["issues"]
    assert any("redacted/unknown parameter" in issue for issue in issues)
    assert any("remain non-executable" in issue for issue in issues)


def test_sec_pack_gold_loads_against_real_decoded_contract():
    from pathlib import Path

    from app.agreements.qualification import load_pack

    root = Path(__file__).parents[2] / "qualification" / "downloaded" / "sec-demandtec-target-2010"
    pack = load_pack(root)
    assert pack.gold is not None
    assert pack.gold.review_status == "provisional_engineering_gold"
    assert pack.gold.exhaustive_financial_terms is False
    source = pack.documents["DEMANDTEC-TARGET-AGREEMENT"][1]
    assert "No other amounts will be owed by Customer to DemandTec" in source
    assert "[***]" in source
    normalized_source = " ".join(source.split())
    for term in pack.gold.terms:
        assert " ".join(term.source_phrase.split()) in normalized_source, term.id


def test_requirement_aware_scoring_does_not_cross_credit_same_source_clause() -> None:
    import json
    from pathlib import Path

    from app.agreements.qualification import compile_pack_proposal, load_pack

    pack_root = (
        Path(__file__).resolve().parents[2] / "qualification" / "fixtures" / "outcome-pricing-e2e"
    )
    pack = load_pack(pack_root)
    proposal = json.loads((pack_root / "proposal.json").read_text())
    agreement = compile_pack_proposal(pack, proposal).model_copy(deep=True)

    identity_norm = next(norm for norm in agreement.norms if norm.id == "NORM-R5")
    identity_norm.consequence = "payable"

    scored = score_agreement(agreement, pack.gold)
    terms = {item["id"]: item for item in scored["terms"]}

    identity = terms["GOLD-SYN-IDENTITY"]
    evidence_envelope = terms["GOLD-SYN-EVIDENCE-ENVELOPE"]

    assert identity["source_covered"] is True
    assert identity["atomic_requirement_covered"] is True
    assert identity["semantic_match"] is False
    assert identity["found"] is False
    assert identity["requirement_ids"] == ["REQ-IDENTITY-MATCH"]
    assert "consequence mismatch (expected disputed)" in identity["issues"]

    # The separate R7 evidence-envelope norm shares the same source sentence but
    # must not mask the identity rule's semantic failure.
    assert evidence_envelope["semantic_match"] is True
    assert evidence_envelope["requirement_ids"] == ["REQ-EVIDENCE-ENVELOPE"]
