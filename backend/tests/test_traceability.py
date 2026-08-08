from __future__ import annotations

import json
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from app.agreements.adjudication import evaluate_claim
from app.agreements.qualification import compile_pack_proposal, load_pack
from app.agreements.traceability import build_decision_trace
from app.domain.models import OperationalEvent, OutcomeClaim

ROOT = Path(__file__).parents[2]
PACK_ROOT = ROOT / "qualification" / "fixtures" / "outcome-pricing-e2e"


def _agreement_and_scenario(scenario_id: str):
    pack = load_pack(PACK_ROOT)
    proposal = json.loads((PACK_ROOT / "proposal.json").read_text())
    agreement = compile_pack_proposal(pack, proposal)
    scenario = next(item for item in pack.scenarios.scenarios if item.id == scenario_id)
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
    return agreement, claim, events


def test_disputed_dollar_trace_reaches_approved_contract_source() -> None:
    agreement, claim, events = _agreement_and_scenario("SCENARIO-02-RECONTACT")
    result = evaluate_claim(claim, events, agreement)
    assert result.status == "disputed"

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
        agreement,
        outcome_id=claim.outcome_id,
        status=result.status,
        rule_id=result.rule_id,
        billed_amount=claim.billed_amount,
        payable_amount=result.confirmed_payable_amount,
        disputed_amount=result.confirmed_disputed_amount,
        needs_review_amount=result.needs_review_amount,
        evidence=evidence,
    )

    assert trace["complete"] is True
    assert Decimal(trace["financial_amount"]) == Decimal("1.50")
    assert trace["summary"]["contractual_rule_found"] is True
    assert trace["summary"]["source_clause_count"] >= 1
    source_nodes = [item for item in trace["nodes"] if item["type"] == "contract_source"]
    assert source_nodes
    assert all(item["text_hash"] for item in source_nodes)
    assert any(edge["relation"] == "grounded_in" for edge in trace["edges"])


def test_unmapped_dispute_is_explicitly_incomplete() -> None:
    agreement, claim, _ = _agreement_and_scenario("SCENARIO-02-RECONTACT")
    trace = build_decision_trace(
        agreement,
        outcome_id=claim.outcome_id,
        status="disputed",
        rule_id="NONEXISTENT-RULE",
        billed_amount="1.50",
        payable_amount="0.00",
        disputed_amount="1.50",
        needs_review_amount="0.00",
        evidence=[],
    )
    assert trace["complete"] is False
    assert set(trace["gaps"]) == {"approved_rule", "contract_source"}
