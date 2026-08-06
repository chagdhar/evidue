"""Tests for the isolated, authenticated pilot path."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest
from app.db.models import Base
from app.upload.match import ClaimIdentity, IdentityMapping, MatchCandidate, run_matching
from app.upload.models import (
    PilotClaimRow,
    PilotEventRow,
    PilotRawRecordRow,
    PilotReconciliationRunRow,
    PilotUploadRow,
)
from app.upload.parsers import (
    parse_evidence_csv,
    parse_evidence_json,
    parse_evidence_jsonl,
    parse_identity_map_csv,
    parse_invoice_csv,
)
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

TOKEN = "test-pilot-token-that-is-long-enough"
AUTH = {"Authorization": f"Bearer {TOKEN}"}
ROOT = Path(__file__).parents[2]

INVOICE_CSV = (
    "outcome_id,customer_reference,account_reference,claimed_outcome_type,"
    "claimed_completion_time,billed_amount,vendor_claim_id,vendor_disposition,"
    "conversation_id,agent_version\n"
    "OUT-001,CUST-001,ACC-001,order_support,2026-06-02T08:01:00,1.50,"
    "CLM-001,resolved,CONV-001,v4.2\n"
)

PAYABLE_EVIDENCE = (
    '{"event_id":"EV-CLOSE","event_type":"ai_closed",'
    '"occurred_at":"2026-06-02T08:01:00Z","customer_id":"CUST-001",'
    '"outcome_id":"OUT-001"}\n'
    '{"event_id":"EV-SUCCESS","event_type":"downstream_succeeded",'
    '"occurred_at":"2026-06-02T08:31:00Z","customer_id":"CUST-001",'
    '"outcome_id":"OUT-001","account_id":"ACC-001",'
    '"action":"order_support"}\n'
)


@pytest.fixture()
def pilot_client(monkeypatch):
    import app.upload.router as router_module

    engine = create_engine(
        "sqlite://",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(router_module, "PilotSessionLocal", session_factory)
    monkeypatch.setenv("EVIDUE_PILOT_TOKEN", TOKEN)

    from app.main import app

    with TestClient(app) as client:
        yield client, session_factory


@pytest.fixture()
def prepared_pilot(pilot_client):
    client, sessions = pilot_client
    contract_text = (
        ROOT / "demo-data/contract/acme-nova-outcome-pricing-order-form.txt"
    ).read_bytes()
    response = client.post(
        "/api/pilot/contract",
        params={
            "customer": "Acme",
            "vendor": "Nova",
            "period_start": "2026-06-01T00:00:00Z",
            "period_end": "2026-07-01T00:00:00Z",
            "price_per_outcome": "1.50",
        },
        files={"file": ("contract.txt", contract_text, "text/plain")},
        headers=AUTH,
    )
    assert response.status_code == 200, response.text
    contract_id = response.json()["contract"]["id"]

    compiled = client.post(
        f"/api/pilot/contracts/{contract_id}/compile",
        params={"mode": "recorded"},
        headers=AUTH,
    )
    assert compiled.status_code == 200, compiled.text
    compilation_id = compiled.json()["id"]
    approved = client.post(
        f"/api/pilot/compilations/{compilation_id}/approve",
        headers=AUTH,
    )
    assert approved.status_code == 200, approved.text

    invoice = client.post(
        "/api/pilot/invoice",
        params={
            "contract_id": contract_id,
            "invoice_id": "INV-TEST-001",
            "billing_period_start": "2026-06-01T00:00:00Z",
            "billing_period_end": "2026-07-01T00:00:00Z",
        },
        files={"file": ("invoice.csv", INVOICE_CSV, "text/csv")},
        headers=AUTH,
    )
    assert invoice.status_code == 200, invoice.text
    return client, sessions, contract_id


# Parser correctness ---------------------------------------------------------


def test_invoice_parser_requires_amount():
    result = parse_invoice_csv(
        "outcome_id,customer_reference,claimed_outcome_type,claimed_completion_time\n"
        "OUT-1,CUST-1,refund,2026-06-01T00:00:00\n"
    )
    assert not result.accepted
    assert "Missing billed_amount" in result.rejected[0].reason


def test_invoice_parser_accepts_alternate_columns_without_inventing_resolved():
    result = parse_invoice_csv(
        "Outcome ID,Customer ID,Account ID,Intent,Closed At,Amount,Claim ID\n"
        "OUT-100,CUST-100,ACC-100,billing_dispute,2026-07-01T12:00:00,3.50,CLM-100\n"
    )
    assert len(result.accepted) == 1
    assert result.accepted[0].data["vendor_claim"] == "claimed"


def test_timezone_timestamp_is_converted_to_utc():
    result = parse_evidence_json(
        '[{"event_id":"EV-1","event_type":"ai_closed",'
        '"occurred_at":"2026-06-03T10:00:00+05:30","customer_id":"C-1"}]',
        "support",
    )
    assert result.accepted[0].data["timestamp"] == datetime(2026, 6, 3, 4, 30)


def test_evidence_parsers_and_identity_map():
    csv_result = parse_evidence_csv(
        "event_id,event_type,occurred_at,customer_id,outcome_id\n"
        "EV-1,ai_closed,2026-06-01T00:00:00,C-1,O-1\n",
        "support",
    )
    jsonl_result = parse_evidence_jsonl(
        '{"event_type":"ai_closed","occurred_at":"2026-06-01T00:00:00","customer_id":"C-1"}\n',
        "support",
    )
    mapping_result = parse_identity_map_csv(
        "conversation_id,customer_id,customer_account_id,outcome_id\nCONV-1,C-1,A-1,O-1\n"
    )
    assert len(csv_result.accepted) == 1
    assert len(jsonl_result.accepted) == 1
    assert len(mapping_result.accepted) == 1
    assert len(jsonl_result.accepted[0].data["source_record_id"]) == 64


# Matching policy ------------------------------------------------------------


def _claims():
    return [ClaimIdentity("OUT-1", "CUST-1", "CONV-1", "ACC-1", "2026-06-02T08:00:00", "refund")]


def test_direct_and_identity_map_matches_are_authoritative():
    direct, direct_summary = run_matching(
        [MatchCandidate("E1", "OUT-1", "CUST-1", "2026-06-02T08:01:00", "ai_closed", {})],
        _claims(),
    )
    mapped, map_summary = run_matching(
        [
            MatchCandidate(
                "E2",
                None,
                "CUST-1",
                "2026-06-02T08:01:00",
                "ai_closed",
                {"conversation_id": "CONV-1"},
            )
        ],
        _claims(),
        [IdentityMapping("CONV-1", "CUST-1", "ACC-1", "OUT-1")],
    )
    assert direct[0].method == "direct_outcome_id"
    assert direct_summary.direct_matches == 1
    assert mapped[0].method == "identity_map_conversation"
    assert map_summary.identity_map_matches == 1


def test_customer_only_identity_is_not_authoritative():
    results, summary = run_matching(
        [MatchCandidate("E1", None, "CUST-1", "2026-06-10T08:00:00", "ai_closed", {})],
        _claims(),
        [IdentityMapping(None, "CUST-1", None, "OUT-1")],
    )
    assert results[0].outcome_id is None
    assert summary.unresolved == 1


def test_composite_match_is_only_a_suggestion_at_store_layer(prepared_pilot):
    client, sessions, _ = prepared_pilot
    evidence = (
        '{"event_id":"EV-SUGGEST","event_type":"ai_closed",'
        '"occurred_at":"2026-06-02T08:20:00Z","customer_id":"CUST-001"}\n'
    )
    uploaded = client.post(
        "/api/pilot/evidence",
        params={"invoice_id": "INV-TEST-001", "source_type": "support"},
        files={"file": ("evidence.jsonl", evidence, "application/x-ndjson")},
        headers=AUTH,
    )
    assert uploaded.status_code == 200, uploaded.text
    matched = client.post("/api/pilot/match", params={"invoice_id": "INV-TEST-001"}, headers=AUTH)
    assert matched.status_code == 200
    assert matched.json()["suggested_composite_matches"] == 1
    with sessions() as session:
        event = session.scalar(
            select(PilotEventRow).where(PilotEventRow.source_record_id == "EV-SUGGEST")
        )
        assert event.match_status == "suggested"
        assert event.matched_claim_id is None


# API security/isolation -----------------------------------------------------


def test_every_pilot_route_requires_token(pilot_client):
    client, _ = pilot_client
    assert client.get("/api/pilot/status").status_code == 401
    assert client.post("/api/pilot/clear").status_code == 401


def test_pilot_clear_cannot_delete_demo_data(pilot_client):
    from app.db import repository

    client, _ = pilot_client
    repository.reset("headline")
    before = repository.demo_status()["claimed_outcomes"]
    response = client.post("/api/pilot/clear", headers=AUTH)
    assert response.status_code == 200
    after = repository.demo_status()["claimed_outcomes"]
    assert before == 10000
    assert after == before


def test_failed_upload_is_recorded(pilot_client):
    client, sessions = pilot_client
    response = client.post(
        "/api/pilot/invoice",
        params={
            "contract_id": "missing",
            "billing_period_start": "2026-06-01T00:00:00Z",
            "billing_period_end": "2026-07-01T00:00:00Z",
        },
        files={
            "file": (
                "bad.csv",
                (
                    "outcome_id,customer_reference,claimed_outcome_type,"
                    "claimed_completion_time,billed_amount\n"
                ),
                "text/csv",
            )
        },
        headers=AUTH,
    )
    assert response.status_code == 422
    with sessions() as session:
        upload = session.scalar(select(PilotUploadRow).order_by(PilotUploadRow.uploaded_at.desc()))
        assert upload.status == "failed"


# Complete pilot flow --------------------------------------------------------


def test_contract_invoice_evidence_reconciliation_is_real_and_append_only(prepared_pilot):
    client, sessions, _ = prepared_pilot
    uploaded = client.post(
        "/api/pilot/evidence",
        params={"invoice_id": "INV-TEST-001", "source_type": "support"},
        files={"file": ("evidence.jsonl", PAYABLE_EVIDENCE, "application/x-ndjson")},
        headers=AUTH,
    )
    assert uploaded.status_code == 200, uploaded.text
    matched = client.post("/api/pilot/match", params={"invoice_id": "INV-TEST-001"}, headers=AUTH)
    assert matched.status_code == 200
    assert matched.json()["direct_matches"] == 2

    first = client.post("/api/pilot/reconcile", params={"invoice_id": "INV-TEST-001"}, headers=AUTH)
    second = client.post(
        "/api/pilot/reconcile", params={"invoice_id": "INV-TEST-001"}, headers=AUTH
    )
    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text
    assert first.json()["run_number"] == 1
    assert second.json()["run_number"] == 2
    assert second.json()["supersedes_run_id"] == first.json()["reconciliation_id"]
    comparison = client.get(
        f"/api/pilot/reconciliations/{second.json()['reconciliation_id']}/compare/"
        f"{first.json()['reconciliation_id']}",
        headers=AUTH,
    )
    assert comparison.status_code == 200
    assert comparison.json()["changed_outcomes"] == 0

    customer_review = client.post(
        f"/api/pilot/reconciliations/{second.json()['reconciliation_id']}/customer-review",
        headers=AUTH,
        json={
            "reviewed_by": "Finance Lead",
            "claims_sampled": 1,
            "confirmed_disputes": 0,
            "rejected_disputes": 0,
            "missing_disputes": 0,
            "estimated_overpayment_prevented": "0.00",
            "estimated_hours_saved": "1.50",
            "would_use_next_month": True,
            "willingness_to_pay": "$500/month",
            "permission_to_quote": False,
            "notes": "Pilot result reviewed.",
        },
    )
    assert customer_review.status_code == 200, customer_review.text
    fetched_review = client.get(
        f"/api/pilot/reconciliations/{second.json()['reconciliation_id']}/customer-review",
        headers=AUTH,
    )
    assert fetched_review.status_code == 200
    assert fetched_review.json()["would_use_next_month"] is True

    assert "synthetic_disclosure" not in first.json()
    assert "real_data_disclosure" in first.json()
    assert first.json()["invoice_id"] == "INV-TEST-001"

    with sessions() as session:
        assert session.scalar(select(func.count()).select_from(PilotReconciliationRunRow)) == 2
        raw_rows = session.scalars(select(PilotRawRecordRow)).all()
        assert len(raw_rows) == 3
        assert all(row.raw_payload for row in raw_rows)
        assert all(row.normalized_payload for row in raw_rows)
        assert all(len(row.payload_hash.removeprefix("sha256:")) == 64 for row in raw_rows)

    evidence_export = client.get(
        f"/api/pilot/reconciliations/{first.json()['reconciliation_id']}/exports/evidence.json",
        headers=AUTH,
    )
    assert evidence_export.status_code == 200
    payload = evidence_export.json()
    assert payload["determinations"][0]["evidence"][0]["raw_payload"]
    assert payload["determinations"][0]["evidence"][0]["parser_version"] == "upload-v2"


def test_same_external_outcome_id_is_allowed_on_second_invoice(prepared_pilot):
    client, sessions, contract_id = prepared_pilot
    response = client.post(
        "/api/pilot/invoice",
        params={
            "contract_id": contract_id,
            "invoice_id": "INV-TEST-002",
            "billing_period_start": "2026-06-01T00:00:00Z",
            "billing_period_end": "2026-07-01T00:00:00Z",
        },
        files={"file": ("invoice.csv", INVOICE_CSV, "text/csv")},
        headers=AUTH,
    )
    assert response.status_code == 200, response.text
    with sessions() as session:
        claims = session.scalars(
            select(PilotClaimRow).where(PilotClaimRow.external_outcome_id == "OUT-001")
        ).all()
        assert {claim.invoice_id for claim in claims} == {"INV-TEST-001", "INV-TEST-002"}


def test_raw_record_endpoint_is_protected_and_returns_lineage(prepared_pilot):
    client, sessions, _ = prepared_pilot
    with sessions() as session:
        raw_id = session.scalar(select(PilotRawRecordRow.id))
    assert client.get(f"/api/pilot/raw-records/{raw_id}").status_code == 401
    response = client.get(f"/api/pilot/raw-records/{raw_id}", headers=AUTH)
    assert response.status_code == 200
    assert response.json()["raw_payload"]
    assert response.json()["normalized_payload"]
