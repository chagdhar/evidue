import csv
import io
import json
from decimal import Decimal
from pathlib import Path

import pytest
from app.api.schemas import (
    DataReadinessResponse,
    DataSourceSamplesResponse,
    OutcomeDetail,
    ReconciliationSummary,
)
from app.db import repository
from app.db.models import OutcomeDeterminationRow
from app.main import (
    app,
    current_contract,
    current_invoice,
    current_reconciliation,
    data_readiness,
    data_source_samples,
    demo_input,
    demo_scenarios,
    demo_status,
    disputes_csv,
    ensure_mutation_allowed,
    evaluate_public_outcome,
    evidence_json,
    health,
    outcome,
    outcomes,
    public_config,
    public_demo_enabled,
    reconcile,
    reset,
    run_public_reconciliation_sample,
    summary_json,
    validate_public_rules,
)
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import select


@pytest.fixture(scope="module", autouse=True)
def reconciled_demo():
    state = reset()
    assert state["seeded"] is True
    assert state["reconciled"] is False
    yield reconcile()


def test_every_data_source_exposes_an_inspectable_sample():
    readiness = data_readiness()
    source_ids = {source["id"] for source in readiness["sources"]}
    assert source_ids == {
        "vendor_claim_manifest",
        "vendor_agent_log",
        "support_desk",
        "payment_processor",
        "product_operations",
        "billing_ledger",
        "identity_map",
        "contract_documents",
    }

    for source_id in sorted(source_ids):
        samples = data_source_samples(source_id, limit=8)
        assert samples["source"]["id"] == source_id
        assert samples["records"], f"{source_id} must have an inspectable raw record"
        first = samples["records"][0]
        assert first["source_record_id"]
        assert first["schema_version"]
        assert first["payload_hash"].startswith("sha256:")
        assert isinstance(first["payload"], dict)
        assert isinstance(first["normalized_payload"], dict)


def test_health_reset_seed_and_reconciliation_lifecycle():
    assert health() == {"status": "ok"}
    state = demo_status()
    assert state == {
        "public_demo": False,
        "seeded": True,
        "reconciled": True,
        "claimed_outcomes": 10_000,
        "billing_period": "2026-06-01 through 2026-06-30",
        "scenario_id": "headline",
        "scenario_name": "Full invoice reconciliation",
        "scenario_description": (
            "10,000 claimed outcomes across all five confirmed dispute categories."
        ),
        "demo_outcome_id": "OUT-004821",
    }


@pytest.mark.parametrize(
    ("input_id", "filename", "media_type"),
    [
        ("contract", "evidue-demo-contract.txt", "text/plain"),
        ("invoice", "evidue-demo-vendor-invoice.csv", "text/csv"),
        ("support-events", "evidue-demo-support-events.jsonl", "application/x-ndjson"),
        ("payment-events", "evidue-demo-payment-events.jsonl", "application/x-ndjson"),
        ("rule-proposal", "evidue-approved-rule-proposal.json", "application/json"),
    ],
)
def test_demo_inputs_are_read_only_downloads(input_id, filename, media_type):
    response = demo_input(input_id)
    assert Path(response.path).is_file()
    assert response.filename == filename
    assert response.media_type == media_type


def test_unknown_demo_input_is_not_exposed():
    with pytest.raises(HTTPException) as error:
        demo_input("../../.env")
    assert error.value.status_code == 404


@pytest.mark.parametrize("value", ["1", "true", "TRUE", "yes", "On"])
def test_public_demo_configuration_is_case_insensitive(monkeypatch, value):
    monkeypatch.setenv("EVIDUE_PUBLIC_DEMO", value)
    assert public_demo_enabled() is True


def test_public_demo_mutations_are_blocked(monkeypatch):
    monkeypatch.setenv("EVIDUE_PUBLIC_DEMO", "on")
    with pytest.raises(HTTPException) as error:
        ensure_mutation_allowed()
    assert error.value.status_code == 403
    assert str(error.value.detail) == (
        "Public technical preview: shared state is read-only, but selected rule validation "
        "and deterministic evaluations can be rerun safely."
    )


def test_public_stateless_actions_use_the_bundled_program():
    validation = validate_public_rules()
    assert validation["valid"] is True
    assert validation["rule_ids"] == ["R7", "R0", "R6", "R1", "R2", "R3", "R5", "R4"]
    assert validation["live_model_call"] is False

    evaluation = evaluate_public_outcome("OUT-004821")
    assert evaluation["status"] == "disputed"
    assert evaluation["rule_id"] == "R3"
    assert evaluation["confirmed_disputed_amount"] == "1.50"

    sample = run_public_reconciliation_sample()
    assert sample["sample_size"] == 100
    assert sample["submitted_amount"] == "150.00"
    assert (
        sample["payable_outcomes"] + sample["disputed_outcomes"] + sample["needs_review_outcomes"]
        == 100
    )
    assert (sample["payable_outcomes"], sample["disputed_outcomes"]) == (83, 17)
    assert sample["compilation_id"] == "COMP-RECORDED-GEMINI-V1"
    assert [finding["rule_id"] for finding in sample["representative_findings"]] == [
        "R1",
        "R2",
        "R3",
        "R4",
        "R5",
    ]
    assert sample["representative_findings"][2]["outcome_id"] == "OUT-004821"


def test_public_http_routes_block_mutation_and_allow_safe_actions(monkeypatch):
    monkeypatch.setenv("EVIDUE_PUBLIC_DEMO", "true")
    with TestClient(app) as client:
        for path in (
            "/api/demo/reset",
            "/api/contracts/current/compile",
            "/api/contracts/current/compilations/COMP-RECORDED-GEMINI-V1/approve",
            "/api/reconciliations",
        ):
            response = client.post(path)
            assert response.status_code == 403
            assert "shared state is read-only" in response.json()["detail"]
        assert client.post("/api/public-demo/rules/validate").json()["valid"] is True
        evaluation = client.post("/api/public-demo/outcomes/OUT-004821/evaluate")
        assert evaluation.status_code == 200
        assert evaluation.json()["compilation_id"] == "COMP-RECORDED-GEMINI-V1"


def test_public_config_is_safe_without_google_credentials(monkeypatch):
    monkeypatch.setenv("EVIDUE_PUBLIC_DEMO", "true")
    monkeypatch.delenv("EVIDUE_BETA_FORM_URL", raising=False)
    monkeypatch.delenv("GOOGLE_APPLICATION_CREDENTIALS", raising=False)
    monkeypatch.delenv("EVIDUE_FIRESTORE_PROJECT_ID", raising=False)
    monkeypatch.delenv("EVIDUE_CONTACT_SHEET_WEBHOOK_URL", raising=False)
    monkeypatch.delenv("EVIDUE_CONTACT_SHEET_SECRET", raising=False)
    assert public_config() == {
        "beta_form_configured": False,
        "beta_form_url": None,
        "contact_form_configured": False,
    }
    with TestClient(app) as client:
        assert client.get("/api/demo/status").json()["public_demo"] is True
        assert client.get("/api/public-config").json() == {
            "beta_form_configured": False,
            "beta_form_url": None,
            "contact_form_configured": False,
        }


@pytest.mark.parametrize(
    "configured_url",
    [
        "http://tally.so/r/form",
        "https://example.com/r/form",
        "javascript:alert(1)",
        "https://127.0.0.1/r/form",
        "//tally.so/r/form",
        "https://tally.so.evil.example/r/form",
    ],
)
def test_public_config_rejects_unsafe_beta_urls(monkeypatch, configured_url):
    monkeypatch.setenv("EVIDUE_BETA_FORM_URL", configured_url)
    monkeypatch.delenv("EVIDUE_CONTACT_SHEET_WEBHOOK_URL", raising=False)
    monkeypatch.delenv("EVIDUE_CONTACT_SHEET_SECRET", raising=False)
    assert public_config() == {
        "beta_form_configured": False,
        "beta_form_url": None,
        "contact_form_configured": False,
    }


def test_public_config_allows_tally_https_url(monkeypatch):
    configured_url = "https://tally.so/r/test-form?source=hacker_news"
    monkeypatch.setenv("EVIDUE_BETA_FORM_URL", configured_url)
    monkeypatch.delenv("EVIDUE_CONTACT_SHEET_WEBHOOK_URL", raising=False)
    monkeypatch.delenv("EVIDUE_CONTACT_SHEET_SECRET", raising=False)
    assert public_config() == {
        "beta_form_configured": True,
        "beta_form_url": configured_url,
        "contact_form_configured": False,
    }


def test_production_shaped_ingestion_readiness_and_source_samples():
    readiness = data_readiness()
    DataReadinessResponse.model_validate(readiness)
    assert readiness["status"] == "ready"
    assert readiness["totals"]["claimed_outcomes"] == 10_000
    assert readiness["totals"]["direct_matches"] == 9_975
    assert readiness["totals"]["secondary_matches"] == 25
    assert readiness["totals"]["review_records"] == 0
    assert readiness["totals"]["claim_coverage_percent"] == 100.0
    assert readiness["totals"]["raw_records"] > 40_000
    assert [source["id"] for source in readiness["sources"]] == [
        "vendor_claim_manifest",
        "vendor_agent_log",
        "support_desk",
        "payment_processor",
        "product_operations",
        "billing_ledger",
        "identity_map",
        "contract_documents",
    ]

    payment = data_source_samples("payment_processor", limit=5, outcome_id="OUT-004821")
    DataSourceSamplesResponse.model_validate(payment)
    assert payment["source"]["authority"] == "Customer financial record"
    assert len(payment["records"]) == 1
    sample = payment["records"][0]
    assert sample["payload"]["result"] == "rejected"
    assert sample["matched_outcome_id"] == "OUT-004821"
    assert sample["match_method"] == "direct_outcome_id"
    assert sample["payload_hash"].startswith("sha256:")

    secondary = data_source_samples("product_operations", limit=5, outcome_id="OUT-009976")
    assert secondary["records"][0]["match_status"] == "secondary"
    assert secondary["records"][0]["match_method"] == ("conversation_id + customer_account_map")
    assert "outcome_id" not in secondary["records"][0]["payload"]


def test_contract_and_invoice_are_persisted_inputs():
    contract = current_contract()
    invoice = current_invoice()
    assert contract["customer"] == "Acme Commerce"
    assert contract["vendor"] == "Nova Support AI"
    assert contract["price_per_outcome"] == "1.50"
    assert len(contract["clauses"]) == 8
    r4 = next(clause for clause in contract["clauses"] if clause["rule"]["id"] == "R4")
    assert "claims that pass R1, R2, R3, R5, R6, and R7" in r4["text"]
    assert "otherwise-payable claims" in r4["rule"]["description"]
    assert r4["rule"]["parameters"]["applies_after"] == "R1,R2,R3,R5,R6,R7"
    assert invoice["claimed_outcomes"] == 10_000
    assert invoice["submitted_amount"] == "15000.00"


def test_exact_reconciliation_summary_and_typed_schema():
    summary = current_reconciliation()
    ReconciliationSummary.model_validate(summary)
    assert summary["reconciliation_id"] == "REC-2026-06-001"
    assert summary["claimed_outcomes"] == 10_000
    assert summary["scenario_id"] == "headline"
    assert summary["scenario_name"] == "Full invoice reconciliation"
    assert summary["payable_outcomes"] == 8_320
    assert summary["disputed_outcomes"] == 1_680
    assert summary["needs_review_outcomes"] == 0
    assert summary["submitted_amount"] == "15000.00"
    assert summary["confirmed_payable_amount"] == "12480.00"
    assert summary["recommended_deduction"] == "2520.00"
    assert summary["needs_review_amount"] == "0.00"
    assert {key: value["count"] for key, value in summary["categories"].items()} == {
        "R1": 720,
        "R2": 360,
        "R3": 300,
        "R4": 180,
        "R5": 120,
    }


def test_server_side_pagination_filters_search_and_stable_ordering():
    page = outcomes(offset=0, limit=25, status="disputed")
    assert page["total"] == 1_680
    assert len(page["items"]) == 25
    ids = [item["outcome_id"] for item in page["items"]]
    assert ids == sorted(ids)
    assert all(item["status"] == "disputed" for item in page["items"])

    recontacts = outcomes(offset=0, limit=10, reason="R1")
    assert recontacts["total"] == 720
    assert all(item["rule_id"] == "R1" for item in recontacts["items"])

    searched = outcomes(offset=0, limit=10, search="OUT-004821")
    assert searched["total"] == 1
    assert searched["items"][0]["outcome_id"] == "OUT-004821"

    assert outcomes(offset=0, limit=10, customer_id="CUST-004821")["total"] == 1
    assert outcomes(offset=0, limit=10, intent="refund")["total"] == 1


def test_out_004821_detail_has_decisive_evidence_and_computed_deadline():
    detail = outcome("OUT-004821")
    OutcomeDetail.model_validate(detail)
    assert detail["vendor_claim"] == "resolved"
    assert detail["status"] == "disputed"
    assert detail["rule_id"] == "R3"
    assert detail["rule"]["operation"] == "require_success_event_within"
    assert detail["rule"]["parameters"]["window_value"] == 2
    assert detail["rule"]["parameters"]["window_unit"] == "hours"
    assert detail["billed_amount"] == "1.50"
    assert detail["confirmed_payable_amount"] == "0.00"
    assert detail["confirmed_disputed_amount"] == "1.50"
    assert detail["needs_review_amount"] == "0.00"
    assert detail["conversation"]["id"] == "CONV-004821"
    assert [event["event_type"] for event in detail["evidence"]] == [
        "ai_closed",
        "downstream_failed",
        "human_refund_completed",
    ]
    assert detail["computed_timeline_markers"] == [
        {
            "id": "COMPUTED-OUT-004821-R3-DEADLINE",
            "marker_type": "completion_window_expired",
            "timestamp": "2026-06-04T19:21:00",
            "description": "Computed contractual two-hour completion deadline",
        }
    ]
    assert all(event["source_system"] != "evidue_engine" for event in detail["evidence"])
    assert detail["vendor_claim_id"] == "CLM-004821"
    assert detail["agent_version"] == "refund-v2.3"
    assert detail["claim_provenance"]["collection_method"] == "CSV upload"
    payment_event = next(
        event for event in detail["evidence"] if event["event_type"] == "downstream_failed"
    )
    assert payment_event["provenance"]["connector_name"] == "Payment processor"
    assert payment_event["provenance"]["match_method"] == "direct_outcome_id"
    assert payment_event["provenance"]["raw_payload"]["result"] == "rejected"
    required = {
        "source_system",
        "source_record_id",
        "event_type",
        "timestamp",
        "customer_id",
        "outcome_id",
        "values",
        "ingested_at",
    }
    assert required <= detail["evidence"][0].keys()


def test_duplicate_detail_references_winner_and_duplicate_claims():
    detail = outcome("OUT-001381")
    assert detail["rule_id"] == "R4"
    assert detail["duplicate_winner_outcome_id"] == "OUT-001081"
    assert "OUT-001381" in detail["reason"]
    assert "OUT-001081" in detail["reason"]
    assert {event["outcome_id"] for event in detail["evidence"]} == {
        "OUT-001081",
        "OUT-001381",
    }


def test_csv_export_uses_explicit_financial_buckets():
    response = disputes_csv()
    rows = list(csv.DictReader(io.StringIO(response.body.decode())))
    assert len(rows) == 1_680
    failed_refund = next(row for row in rows if row["outcome_id"] == "OUT-004821")
    assert failed_refund["billed_amount"] == "1.50"
    assert failed_refund["confirmed_payable_amount"] == "0.00"
    assert failed_refund["confirmed_disputed_amount"] == "1.50"
    assert failed_refund["needs_review_amount"] == "0.00"
    assert failed_refund["rule_id"] == "R3"


def test_summary_export_exactly_matches_current_api():
    assert summary_json() == current_reconciliation()
    assert "No real customer or vendor data is shown" in summary_json()["synthetic_disclosure"]


def test_evidence_export_contains_every_dispute_and_matches_summary():
    package = evidence_json()
    assert package["reconciliation"] == current_reconciliation()
    assert len(package["outcomes"]) == 1_680
    assert all(item["status"] == "disputed" for item in package["outcomes"])
    failed_refund = next(item for item in package["outcomes"] if item["outcome_id"] == "OUT-004821")
    assert failed_refund["computed_timeline_markers"][0]["marker_type"] == (
        "completion_window_expired"
    )


def test_persisted_needs_review_amount_does_not_increase_deduction():
    with repository.SessionLocal.begin() as session:
        row = session.scalar(
            select(OutcomeDeterminationRow).where(
                OutcomeDeterminationRow.outcome_id == "OUT-001860"
            )
        )
        assert row is not None
        row.status = "needs_review"
        row.confirmed_payable_amount = Decimal("0.00")
        row.confirmed_disputed_amount = Decimal("0.00")
        row.needs_review_amount = Decimal("1.50")

    adjusted = current_reconciliation()
    assert adjusted["confirmed_payable_amount"] == "12478.50"
    assert adjusted["recommended_deduction"] == "2520.00"
    assert adjusted["needs_review_amount"] == "1.50"
    assert adjusted["needs_review_outcomes"] == 1

    with repository.SessionLocal.begin() as session:
        row = session.scalar(
            select(OutcomeDeterminationRow).where(
                OutcomeDeterminationRow.outcome_id == "OUT-001860"
            )
        )
        assert row is not None
        row.status = "payable"
        row.confirmed_payable_amount = Decimal("1.50")
        row.confirmed_disputed_amount = Decimal("0.00")
        row.needs_review_amount = Decimal("0.00")

    assert current_reconciliation()["confirmed_payable_amount"] == "12480.00"


def test_json_exports_are_serializable():
    json.dumps(summary_json())
    json.dumps(repository.outcome_detail("OUT-004821"))


def test_scenario_catalog_and_focused_scenarios_use_real_reconciliation():
    catalog = demo_scenarios()
    assert [scenario["id"] for scenario in catalog] == [
        "headline",
        "evidence_review",
        "recovery",
        "duplicate_window",
    ]
    assert all(scenario["demo_outcome_id"] for scenario in catalog)

    review_state = reset("evidence_review")
    assert review_state["claimed_outcomes"] == 2
    assert review_state["reconciled"] is False
    review = reconcile()
    assert review == {
        "reconciliation_id": "REC-2026-06-EVIDENCE-REVIEW",
        "status": "completed",
        "scenario_id": "evidence_review",
        "scenario_name": "Contradictory evidence",
        "claimed_outcomes": 2,
        "payable_outcomes": 1,
        "disputed_outcomes": 0,
        "needs_review_outcomes": 1,
        "submitted_amount": "3.00",
        "confirmed_payable_amount": "1.50",
        "recommended_deduction": "0.00",
        "needs_review_amount": "1.50",
        "price_per_outcome": "1.50",
        "categories": {},
        "synthetic_disclosure": repository.DISCLOSURE,
    }
    review_detail = outcome("CASE-REVIEW-001")
    assert review_detail["status"] == "needs_review"
    assert {event["event_type"] for event in review_detail["evidence"]} == {
        "downstream_succeeded",
        "downstream_failed",
    }

    reset("recovery")
    recovery = reconcile()
    assert recovery["payable_outcomes"] == 1
    assert recovery["disputed_outcomes"] == 1
    assert recovery["categories"]["R3"]["count"] == 1
    assert outcome("CASE-RECOVERY-001")["rule_id"] == "R3"
    assert outcome("CASE-RECOVERY-002")["status"] == "payable"

    reset("duplicate_window")
    duplicate = reconcile()
    assert duplicate["payable_outcomes"] == 1
    assert duplicate["disputed_outcomes"] == 2
    assert duplicate["categories"]["R4"] == {
        "label": "Duplicate charges",
        "count": 2,
        "amount": "3.00",
    }
    assert outcome("CASE-DUP-002")["duplicate_winner_outcome_id"] == "CASE-DUP-001"
    assert outcome("CASE-DUP-003")["duplicate_winner_outcome_id"] == "CASE-DUP-001"

    reset()
    reconcile()
