"""Evidue core proof tests.

These tests prove the product's central architectural claims:
- Reconciliation works without any LLM
- Approved AIR is the financial authority
- Every dollar is traceable
- Financial conservation holds
- Golden scenarios produce exact expected results
- Contract mutations produce correct semantic changes
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from decimal import Decimal
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[2]


# ---------------------------------------------------------------------------
# PROOF 1: Reconciliation works without any LLM
# ---------------------------------------------------------------------------


def test_reconciliation_without_llm_credentials():
    """Disable every LLM credential. Reconciliation must still work.

    This is a first-class Evidue invariant: the LLM interprets the contract,
    but the LLM is never in the money path after AIR approval.
    """
    # Save and remove all LLM keys
    saved = {}
    for key in ("GEMINI_API_KEY", "OPENAI_API_KEY", "EVIDUE_LLM_PRIMARY"):
        saved[key] = os.environ.pop(key, None)

    try:
        import tempfile

        with tempfile.TemporaryDirectory(prefix="evidue-nollm-") as tmpdir:
            os.environ["EVIDUE_PILOT_TOKEN"] = "nollm-test-token-32-characters-ok"
            os.environ["EVIDUE_PILOT_DB_PATH"] = str(Path(tmpdir) / "nollm.db")
            os.environ.pop("EVIDUE_WORKSPACE_TOKENS", None)

            from app.main import app
            from fastapi.testclient import TestClient

            headers = {"Authorization": "Bearer nollm-test-token-32-characters-ok"}
            with TestClient(app) as client:
                # Seed sample workspace (uses recorded proposal, no LLM call)
                seed = client.post("/api/pilot/sample/seed", headers=headers)
                assert seed.status_code == 200, f"Seed failed: {seed.text}"

                data = seed.json()
                recon = data["reconciliation"]

                # Verify all three financial states are present
                assert recon["payable_outcomes"] == 1
                assert recon["disputed_outcomes"] == 1
                assert recon["needs_review_outcomes"] == 1

                # Verify financial conservation
                submitted = Decimal(recon["submitted_amount"])
                payable = Decimal(recon["confirmed_payable_amount"])
                disputed = Decimal(recon["recommended_deduction"])
                review = Decimal(recon["needs_review_amount"])
                assert submitted == payable + disputed + review

                detail_response = client.get(
                    "/api/pilot/reconciliation",
                    headers=headers,
                )
                assert detail_response.status_code == 200
                disputed_rows = [
                    item
                    for item in detail_response.json().get("determinations", [])
                    if item.get("status") == "disputed"
                ]
                assert disputed_rows
                assert all(item.get("trace", {}).get("complete") for item in disputed_rows)

                # Verify exports work without LLM
                for kind in (
                    "corrected-invoice.csv",
                    "disputes.csv",
                    "summary.json",
                    "evidence.json",
                ):
                    run_id = recon["reconciliation_id"]
                    resp = client.get(
                        f"/api/pilot/reconciliations/{run_id}/exports/{kind}", headers=headers
                    )
                    assert resp.status_code == 200, f"Export {kind} failed: {resp.status_code}"
                    assert resp.content
    finally:
        for key, value in saved.items():
            if value is not None:
                os.environ[key] = value


# ---------------------------------------------------------------------------
# PROOF 2: Provider change after approval doesn't alter results
# ---------------------------------------------------------------------------


def test_approved_air_independent_of_provider(monkeypatch):
    """Provider configuration cannot alter an already-approved AIR result."""
    from app.agreements.qualification import (
        compile_pack_proposal,
        load_pack,
        run_financial_scenarios,
    )

    pack_root = ROOT / "qualification" / "fixtures" / "outcome-pricing-e2e"
    pack = load_pack(pack_root)
    proposal = json.loads((pack_root / "proposal.json").read_text())
    approved_air = compile_pack_proposal(pack, proposal)

    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("EVIDUE_LLM_PRIMARY", "gemini")
    first = run_financial_scenarios(approved_air, pack.scenarios)

    monkeypatch.setenv("EVIDUE_LLM_PRIMARY", "openai")
    monkeypatch.setenv("EVIDUE_LLM_FALLBACK", "gemini")
    second = run_financial_scenarios(approved_air, pack.scenarios)

    assert first["passed"] is True
    assert second["passed"] is True
    assert first["totals"] == second["totals"]
    assert first["scenarios"] == second["scenarios"]


# ---------------------------------------------------------------------------
# PROOF 3: Financial conservation invariant
# ---------------------------------------------------------------------------


def test_financial_conservation_on_demo():
    """submitted = payable + disputed + needs_review for every claim."""
    from app.contracts.compiler import recorded_rule_program
    from app.domain.engine import reconcile
    from app.fixtures.demo import demo_fixture

    records = demo_fixture()
    claim_evidence = [(r.claim, list(r.events)) for r in records]
    program = recorded_rule_program()
    results = reconcile(claim_evidence, program=program)

    for det in results:
        submitted = det.claim.billed_amount
        total = (
            det.confirmed_payable_amount + det.confirmed_disputed_amount + det.needs_review_amount
        )
        assert submitted == total, (
            f"{det.claim.outcome_id}: {submitted} != {det.confirmed_payable_amount} + "
            f"{det.confirmed_disputed_amount} + {det.needs_review_amount}"
        )


# ---------------------------------------------------------------------------
# PROOF 4: Every disputed dollar is traceable
# ---------------------------------------------------------------------------


def test_disputed_claims_have_complete_provenance():
    """Every disputed controlled scenario reaches an approved rule and source clause."""
    from app.agreements.adjudication import evaluate_claim
    from app.agreements.qualification import compile_pack_proposal, load_pack
    from app.agreements.traceability import build_decision_trace
    from app.domain.models import OperationalEvent, OutcomeClaim

    pack_root = ROOT / "qualification" / "fixtures" / "outcome-pricing-e2e"
    pack = load_pack(pack_root)
    proposal = json.loads((pack_root / "proposal.json").read_text())
    air = compile_pack_proposal(pack, proposal)

    checked = 0
    for scenario in pack.scenarios.scenarios:
        if scenario.expected_status != "disputed":
            continue
        claim = OutcomeClaim(
            outcome_id=scenario.outcome_id,
            invoice_id=scenario.invoice_id,
            customer_id=scenario.customer_id,
            intent=scenario.intent,
            vendor_claim=scenario.vendor_claim,
            closed_at=datetime.fromisoformat(scenario.closed_at),
            expected_action=scenario.expected_action,
            account_id=scenario.account_id,
            billed_amount=Decimal(scenario.billed_amount),
        )
        events = [
            OperationalEvent(
                id=item.id,
                source_system=item.source_system,
                source_record_id=item.source_record_id,
                event_type=item.event_type,
                timestamp=datetime.fromisoformat(item.timestamp),
                customer_id=item.customer_id,
                outcome_id=item.outcome_id,
                values=item.values,
                ingested_at=datetime.fromisoformat(item.ingested_at or item.timestamp),
            )
            for item in scenario.events
        ]
        result = evaluate_claim(claim, events, air)
        event_by_id = {item.id: item for item in events}
        evidence = [
            {
                "event_id": reference.event_id,
                "source_system": event_by_id[reference.event_id].source_system,
                "source_record_id": event_by_id[reference.event_id].source_record_id,
                "event_type": event_by_id[reference.event_id].event_type,
                "timestamp": event_by_id[reference.event_id].timestamp.isoformat(),
                "purpose": reference.purpose,
            }
            for reference in result.evidence
        ]
        trace = build_decision_trace(
            air,
            outcome_id=claim.outcome_id,
            status=result.status,
            rule_id=result.rule_id,
            billed_amount=claim.billed_amount,
            payable_amount=result.confirmed_payable_amount,
            disputed_amount=result.confirmed_disputed_amount,
            needs_review_amount=result.needs_review_amount,
            evidence=evidence,
        )
        assert trace["complete"] is True, (scenario.id, trace["gaps"])
        assert trace["summary"]["source_clause_count"] >= 1
        source_nodes = [item for item in trace["nodes"] if item["type"] == "contract_source"]
        assert source_nodes and all(item["text_hash"] for item in source_nodes)
        checked += 1

    assert checked >= 1


# ---------------------------------------------------------------------------
# PROOF 5: Golden financial scenarios
# ---------------------------------------------------------------------------


def test_golden_financial_scenarios():
    """Source-bound native proposal → AIR → exact deterministic dollars."""
    from app.agreements.qualification import (
        compile_pack_proposal,
        load_pack,
        run_financial_scenarios,
        score_agreement,
    )

    pack_root = ROOT / "qualification" / "fixtures" / "outcome-pricing-e2e"
    pack = load_pack(pack_root)
    proposal = json.loads((pack_root / "proposal.json").read_text())
    air = compile_pack_proposal(pack, proposal)

    contract_score = score_agreement(air, pack.gold)
    financial = run_financial_scenarios(air, pack.scenarios)

    assert contract_score["qualification_passed"] is True
    assert contract_score["critical_financial_term_recall_percent"] == 100.0
    assert contract_score["hard_failures"] == []
    assert financial["passed"] is True
    assert financial["conservation_passed"] is True
    assert financial["totals"] == {
        "billed": "12.50",
        "payable": "1.50",
        "disputed": "8.00",
        "needs_review": "3.00",
    }
    assert all(item["passed"] for item in financial["scenarios"])


# ---------------------------------------------------------------------------
# PROOF 6: Provider abstraction works
# ---------------------------------------------------------------------------


def test_provider_registry_contains_gemini_and_openai():
    from app.agreements.providers import PROVIDERS, _resolve_provider

    assert "gemini" in PROVIDERS
    assert "openai" in PROVIDERS
    name, _ = _resolve_provider("google-gemini")
    assert name == "gemini"
    name, _ = _resolve_provider("openai")
    assert name == "openai"


def test_provider_error_without_key():
    from app.agreements.providers import ProviderError, call_provider

    # No keys configured
    saved = {}
    for key in ("GEMINI_API_KEY", "OPENAI_API_KEY"):
        saved[key] = os.environ.pop(key, None)
    try:
        with pytest.raises(ProviderError):
            call_provider("test", {}, provider="gemini", pin_provider=True)
    finally:
        for key, value in saved.items():
            if value is not None:
                os.environ[key] = value


def test_pin_provider_prevents_fallback():
    from app.agreements.providers import ProviderError, call_provider

    saved = {}
    for key in ("GEMINI_API_KEY", "OPENAI_API_KEY"):
        saved[key] = os.environ.pop(key, None)
    try:
        with pytest.raises(ProviderError, match="pin_provider"):
            call_provider("test", {}, provider="gemini", pin_provider=True)
    finally:
        for key, value in saved.items():
            if value is not None:
                os.environ[key] = value


# ---------------------------------------------------------------------------
# PROOF 7: Deterministic rule renderer
# ---------------------------------------------------------------------------


def test_rule_renderer_produces_readable_descriptions():
    """The deterministic renderer must produce human-readable rule descriptions
    from AIR parameters without calling any LLM."""
    from app.agreements.legacy import legacy_rule_program_to_agreement_ir
    from app.agreements.presentation import agreement_finance_view
    from app.contracts.compiler import recorded_rule_program

    program = recorded_rule_program()
    air = legacy_rule_program_to_agreement_ir(program)
    view = agreement_finance_view(air)

    rules = view.get("contract_rules", [])
    assert len(rules) > 0

    for rule in rules:
        desc = rule.get("description", "")
        assert len(desc) > 10, f"Rule {rule['id']} has no readable description"
        # Descriptions should not contain raw operator names
        assert "exists_event" not in desc
        assert "unique_by" not in desc
        assert "terminal_event_outcome" not in desc


# ---------------------------------------------------------------------------
# PROOF 8: Demo output unchanged
# ---------------------------------------------------------------------------


def test_demo_financial_result_exact():
    """The demo must produce exactly the expected financial result."""
    from app.contracts.compiler import recorded_rule_program
    from app.domain.engine import reconcile
    from app.fixtures.demo import demo_fixture

    records = demo_fixture()
    claim_evidence = [(r.claim, list(r.events)) for r in records]
    program = recorded_rule_program()
    results = reconcile(claim_evidence, program=program)

    assert len(results) == 10000
    payable = sum(d.confirmed_payable_amount for d in results)
    disputed = sum(d.confirmed_disputed_amount for d in results)
    review = sum(d.needs_review_amount for d in results)
    assert payable == Decimal("12480.00")
    assert disputed == Decimal("2520.00")
    assert review == Decimal("0.00")


# ---------------------------------------------------------------------------
# PROOF 9: Workspace access isolation
# ---------------------------------------------------------------------------


def test_workspace_access_tokens_resolve_to_distinct_workspaces(monkeypatch):
    """Server-owned workspace tokens select distinct request-local workspaces."""
    from app.upload.auth import _resolve_principal

    alpha = "alpha-workspace-token-that-is-long-enough"
    beta = "beta-workspace-token-that-is-long-enough"
    monkeypatch.setenv(
        "EVIDUE_WORKSPACE_TOKENS",
        json.dumps({"alpha": alpha, "beta": beta}),
    )
    monkeypatch.delenv("EVIDUE_PILOT_TOKEN", raising=False)

    assert _resolve_principal(alpha).workspace_id == "alpha"
    assert _resolve_principal(beta).workspace_id == "beta"
    assert _resolve_principal("not-a-real-workspace-token") is None


# ---------------------------------------------------------------------------
# PROOF 10: Mutation sensitivity
# ---------------------------------------------------------------------------


def test_rate_mutation_changes_only_settlement():
    """Changing the contract rate must change settlement but not eligibility rules."""
    from app.agreements.compiler import lower_to_agreement_ir
    from app.agreements.compiler_models import (
        AgreementCompilationProposal,
        ClauseAnalysisProposal,
        ConditionProposal,
        NormProposal,
        SettlementProposal,
        SourceDocumentRef,
    )

    def _make_proposal(rate: str) -> AgreementCompilationProposal:
        return AgreementCompilationProposal(
            compiler_version="mutation-test",
            contract_id="MUT-RATE",
            model="test",
            provider="test",
            source_documents=[SourceDocumentRef(document_id="DOC-1", title="Test")],
            clauses=[
                ClauseAnalysisProposal(
                    clause_id="CL-PRICE",
                    source_document_id="DOC-1",
                    source_text=f"${rate} per qualifying outcome",
                    clause_type="pricing",
                    settlement_effects=[
                        SettlementProposal(
                            id="S1",
                            settlement_type="fixed_per_unit",
                            parameters={"unit_price": rate},
                            source_clause_id="CL-PRICE",
                            description=f"${rate} per outcome",
                        )
                    ],
                ),
                ClauseAnalysisProposal(
                    clause_id="CL-RECONTACT",
                    source_document_id="DOC-1",
                    source_text="Not payable if customer recontacts within 7 days",
                    clause_type="performance",
                    norms=[
                        NormProposal(
                            id="N-RECONTACT",
                            norm_type="prohibition",
                            subject="vendor",
                            condition=ConditionProposal(
                                condition_type="event_within_window",
                                parameters={
                                    "event_types": ["customer_recontact"],
                                    "anchor_field": "closed_at",
                                    "window_value": 7,
                                    "window_unit": "days",
                                    "start_exclusive": True,
                                },
                                description="recontact within 7 days",
                            ),
                            consequence="disputed",
                        )
                    ],
                ),
            ],
        )

    air_150, _ = lower_to_agreement_ir(
        _make_proposal("1.50"), compilation_id="C-150", version=1, source_hash="h"
    )
    air_175, _ = lower_to_agreement_ir(
        _make_proposal("1.75"), compilation_id="C-175", version=1, source_hash="h"
    )

    # Settlement must change
    assert (
        air_150.settlement_policies[0].amount_expression
        != air_175.settlement_policies[0].amount_expression
    )

    # Eligibility norms must NOT change
    assert len(air_150.norms) == len(air_175.norms)
    for n1, n2 in zip(air_150.norms, air_175.norms):
        assert n1.condition.operator == n2.condition.operator
        if n1.condition.parameters and n2.condition.parameters:
            assert n1.condition.parameters.get("event_types") == n2.condition.parameters.get(
                "event_types"
            )


def test_window_mutation_changes_only_window():
    """Changing 7 days to 14 days must change only the relevant window."""
    from app.agreements.compiler import lower_to_agreement_ir
    from app.agreements.compiler_models import (
        AgreementCompilationProposal,
        ClauseAnalysisProposal,
        ConditionProposal,
        NormProposal,
        SourceDocumentRef,
    )

    def _make(days: int) -> AgreementCompilationProposal:
        return AgreementCompilationProposal(
            compiler_version="test",
            contract_id="MUT-WIN",
            model="test",
            provider="test",
            source_documents=[SourceDocumentRef(document_id="DOC-1", title="Test")],
            clauses=[
                ClauseAnalysisProposal(
                    clause_id="CL-1",
                    source_document_id="DOC-1",
                    source_text=f"Recontact within {days} days",
                    clause_type="performance",
                    norms=[
                        NormProposal(
                            id="N1",
                            norm_type="prohibition",
                            subject="vendor",
                            condition=ConditionProposal(
                                condition_type="event_within_window",
                                parameters={
                                    "event_types": ["customer_recontact"],
                                    "anchor_field": "closed_at",
                                    "window_value": days,
                                    "window_unit": "days",
                                    "start_exclusive": True,
                                },
                                description=f"recontact within {days} days",
                            ),
                            consequence="disputed",
                        )
                    ],
                )
            ],
        )

    air7, _ = lower_to_agreement_ir(_make(7), compilation_id="W7", version=1, source_hash="h")
    air14, _ = lower_to_agreement_ir(_make(14), compilation_id="W14", version=1, source_hash="h")

    # Window must change
    w7 = air7.norms[0].condition.parameters["window"]["value"]
    w14 = air14.norms[0].condition.parameters["window"]["value"]
    assert w7 == 7
    assert w14 == 14

    # Event types must not change
    assert (
        air7.norms[0].condition.parameters["event_types"]
        == air14.norms[0].condition.parameters["event_types"]
    )
