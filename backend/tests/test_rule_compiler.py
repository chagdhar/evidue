import json

import pytest
from app.contracts.compiler import (
    RECORDED_PROPOSAL_PATH,
    CompilationProposal,
    load_recorded_proposal,
    to_rule_program,
)
from app.db import repository
from pydantic import ValidationError


def test_recorded_llm_output_is_schema_valid_and_executable():
    result = load_recorded_proposal()
    program = to_rule_program(
        result.proposal,
        compilation_id="TEST-COMPILATION",
        version=9,
        source_hash=result.source_hash,
    )
    assert result.live_model_call is False
    assert len(program.rules) == 7
    assert [rule.operation for rule in program.rules] == [
        "validate_evidence_envelope",
        "claim_datetime_in_range",
        "prohibit_event_within",
        "prohibit_event_within",
        "require_success_event_within",
        "prohibit_field_mismatch_event",
        "unique_first_claim_within",
    ]


def test_unknown_llm_operation_is_rejected():
    payload = json.loads(RECORDED_PROPOSAL_PATH.read_text())
    payload["rules"][0]["operation"] = "execute_python"
    with pytest.raises(ValidationError):
        CompilationProposal.model_validate(payload)


def test_compile_approve_then_reconcile_uses_approved_version():
    repository.reset()
    proposal = repository.compile_contract_rules("recorded")
    assert proposal["status"] == "pending_approval"
    assert proposal["live_model_call"] is False

    approved = repository.approve_compilation(str(proposal["id"]))
    assert approved["status"] == "approved"
    contract = repository.contract()
    assert contract["compilation"]["id"] == proposal["id"]

    summary = repository.run_reconciliation()
    assert summary["confirmed_payable_amount"] == "12480.00"
    assert summary["recommended_deduction"] == "2520.00"


def test_custom_contract_requires_live_gemini(monkeypatch):
    repository.reset()
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    custom = "CUSTOM TERMS\n" + (
        "A supported outcome requires payment success within three hours. " * 4
    )
    with pytest.raises(ValueError, match="Custom contract text requires"):
        repository.compile_contract_rules("auto", contract_text=custom)


def test_compilation_history_preserves_exact_source_text():
    repository.reset()
    contract = repository.contract()
    proposal = repository.compile_contract_rules(
        "recorded",
        contract_text=str(contract["demo_contract_text"]),
        source_document="demo-order-form.txt",
    )
    history = repository.list_compilations()
    assert history[0]["id"] == proposal["id"]
    assert history[0]["source_document"] == "demo-order-form.txt"
    assert history[0]["source_text"] == contract["demo_contract_text"]
    assert history[0]["validation"]["schema_valid"] is True


def test_only_latest_pending_proposal_can_be_approved():
    repository.reset()
    older = repository.compile_contract_rules("recorded")
    newer = repository.compile_contract_rules("recorded")
    with pytest.raises(ValueError, match="superseded"):
        repository.approve_compilation(str(older["id"]))
    repository.approve_compilation(str(newer["id"]))
    statuses = {item["id"]: item["status"] for item in repository.list_compilations()}
    assert statuses[older["id"]] == "superseded"
    assert statuses[newer["id"]] == "approved"
    assert sum(status == "approved" for status in statuses.values()) == 1
