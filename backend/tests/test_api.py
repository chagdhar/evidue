import csv
import io
import json

import pytest
from app.db import repository
from app.main import (
    current_contract,
    current_invoice,
    current_reconciliation,
    demo_status,
    disputes_csv,
    evidence_json,
    health,
    outcome,
    outcomes,
    reconcile,
    reset,
    summary_json,
)


@pytest.fixture(scope="module", autouse=True)
def reconciled_demo():
    state = reset()
    assert state["seeded"] is True
    assert state["reconciled"] is False
    yield reconcile()


def test_health_reset_seed_and_reconciliation_lifecycle():
    assert health() == {"status": "ok"}
    state = demo_status()
    assert state["seeded"] is True
    assert state["reconciled"] is True
    assert state["claimed_outcomes"] == 10_000


def test_contract_and_invoice_are_persisted_inputs():
    contract = current_contract()
    invoice = current_invoice()
    assert contract["customer"] == "Acme Commerce"
    assert contract["vendor"] == "Nova Support AI"
    assert contract["price_per_outcome"] == "1.50"
    assert len(contract["clauses"]) == 7
    assert invoice["claimed_outcomes"] == 10_000
    assert invoice["submitted_amount"] == "15000.00"


def test_exact_reconciliation_summary():
    summary = current_reconciliation()
    assert summary["claimed_outcomes"] == 10_000
    assert summary["payable_outcomes"] == 8_320
    assert summary["disputed_outcomes"] == 1_680
    assert summary["payable_amount"] == "12480.00"
    assert summary["recommended_deduction"] == "2520.00"
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

    customer = outcomes(offset=0, limit=10, customer_id="CUST-004821")
    assert customer["total"] == 1

    intent = outcomes(offset=0, limit=10, intent="refund")
    assert intent["total"] == 1


def test_out_004821_detail_contains_rule_conversation_and_provenance():
    detail = outcome("OUT-004821")
    assert detail["vendor_claim"] == "resolved"
    assert detail["status"] == "disputed"
    assert detail["rule_id"] == "R3"
    assert detail["billed_amount"] == "1.50"
    assert detail["payable_amount"] == "0.00"
    assert detail["conversation"]["id"] == "CONV-004821"
    assert [event["event_type"] for event in detail["evidence"]] == [
        "ai_closed",
        "downstream_failed",
        "completion_window_expired",
        "human_refund_completed",
    ]
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


def test_csv_export_is_derived_from_all_disputed_determinations():
    response = disputes_csv()
    rows = list(csv.DictReader(io.StringIO(response.body.decode())))
    assert len(rows) == 1_680
    failed_refund = next(row for row in rows if row["outcome_id"] == "OUT-004821")
    assert failed_refund["billed_amount"] == "1.50"
    assert failed_refund["payable_amount"] == "0.00"
    assert failed_refund["rule_id"] == "R3"


def test_summary_export_exactly_matches_current_api():
    assert summary_json() == current_reconciliation()
    assert "No real customer or vendor data is shown" in summary_json()["synthetic_disclosure"]


def test_evidence_export_contains_every_dispute_and_matches_summary():
    package = evidence_json()
    assert package["reconciliation"] == current_reconciliation()
    assert len(package["outcomes"]) == 1_680
    assert all(item["status"] == "disputed" for item in package["outcomes"])


def test_json_exports_are_serializable():
    json.dumps(summary_json())
    json.dumps(repository.outcome_detail("OUT-004821"))
