from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from app.agreements.impact import simulate_agreement_financial_impact
from app.agreements.qualification import apply_mutation, compile_pack_proposal, load_pack
from app.domain.models import OperationalEvent, OutcomeClaim

PACK_ROOT = Path("qualification/fixtures/outcome-pricing-e2e")


def _dt(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is not None:
        return parsed.astimezone(UTC).replace(tzinfo=None)
    return parsed


def _claim_evidence(pack):
    assert pack.scenarios is not None
    rows = []
    for scenario in pack.scenarios.scenarios:
        claim = OutcomeClaim(
            outcome_id=scenario.outcome_id,
            invoice_id=scenario.invoice_id,
            customer_id=scenario.customer_id,
            intent=scenario.intent,
            vendor_claim=scenario.vendor_claim,
            closed_at=_dt(scenario.closed_at),
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
                timestamp=_dt(item.timestamp),
                customer_id=item.customer_id,
                outcome_id=item.outcome_id,
                values=item.values,
                ingested_at=_dt(item.ingested_at or item.timestamp),
            )
            for item in scenario.events
        ]
        rows.append((claim, events))
    return rows


def _replace_value(value, old: str, new: str):
    if isinstance(value, dict):
        return {key: _replace_value(item, old, new) for key, item in value.items()}
    if isinstance(value, list):
        return [_replace_value(item, old, new) for item in value]
    if value == old:
        return new
    if isinstance(value, str):
        return value.replace(f"${old}", f"${new}")
    return value


def test_contract_change_impact_replays_same_invoice_without_llm() -> None:
    pack = load_pack(PACK_ROOT)
    proposal = json.loads((PACK_ROOT / "proposal.json").read_text())
    baseline = compile_pack_proposal(pack, proposal, run_number=1)

    rate_mutation = pack.manifest.mutations[0]
    mutated_pack = apply_mutation(pack, rate_mutation)
    mutated_proposal = _replace_value(proposal, "1.50", "1.75")
    candidate = compile_pack_proposal(mutated_pack, mutated_proposal, run_number=2)

    impact = simulate_agreement_financial_impact(
        _claim_evidence(pack),
        baseline,
        candidate,
    )

    assert impact["simulation_only"] is True
    assert impact["financial_authority_changed"] is False
    assert set(impact["semantic_delta"]["changed_sections"]) == {"pricing", "rules"}
    assert set(impact["semantic_delta"]["unchanged_sections"]) == {"coverage", "evidence"}

    financial = impact["financial"]
    assert financial["baseline"]["billed"] == financial["candidate"]["billed"] == "12.50"
    assert financial["baseline"]["conservation_passed"] is True
    assert financial["candidate"]["conservation_passed"] is True
    assert financial["affected_line_count"] > 0
    assert financial["delta"]["payable"] != "0.00"


def test_contract_change_impact_is_zero_for_identical_air() -> None:
    pack = load_pack(PACK_ROOT)
    proposal = json.loads((PACK_ROOT / "proposal.json").read_text())
    agreement = compile_pack_proposal(pack, proposal, run_number=1)

    impact = simulate_agreement_financial_impact(
        _claim_evidence(pack),
        agreement,
        agreement,
    )

    assert impact["semantic_delta"]["changed_sections"] == []
    assert impact["financial"]["affected_line_count"] == 0
    assert impact["financial"]["delta"] == {
        "payable": "0.00",
        "disputed": "0.00",
        "needs_review": "0.00",
    }
