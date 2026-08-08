"""Tests for the isolated, authenticated pilot path."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
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
    PilotVerificationPlanRow,
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

    native = client.post(
        f"/api/pilot/contracts/{contract_id}/compile-native",
        params={"mode": "recorded"},
        headers=AUTH,
    )
    assert native.status_code == 200, native.text
    air_version_id = native.json()["air_version_id"]
    air_approved = client.post(
        f"/api/pilot/air-versions/{air_version_id}/approve",
        headers=AUTH,
    )
    assert air_approved.status_code == 200, air_approved.text

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


def test_pilot_approval_blocks_unresolved_compiler_diagnostics(pilot_client):
    from app.upload.models import PilotRuleCompilationRow

    client, sessions = pilot_client
    contract_text = (
        ROOT / "demo-data/contract/acme-nova-outcome-pricing-order-form.txt"
    ).read_bytes()
    uploaded = client.post(
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
    contract_id = uploaded.json()["contract"]["id"]
    compiled = client.post(
        f"/api/pilot/contracts/{contract_id}/compile",
        params={"mode": "recorded"},
        headers=AUTH,
    )
    compilation_id = compiled.json()["id"]
    with sessions.begin() as session:
        row = session.get(PilotRuleCompilationRow, compilation_id)
        assert row is not None
        row.raw_response = {
            **row.raw_response,
            "approval_ready": False,
            "compiler_diagnostics": [
                {
                    "code": "UNSUPPORTED_TERM",
                    "severity": "blocking",
                    "message": "A material contract term is not represented.",
                }
            ],
        }
    response = client.post(
        f"/api/pilot/compilations/{compilation_id}/approve",
        headers=AUTH,
    )
    assert response.status_code == 409
    assert "cannot be approved" in response.json()["detail"]


def test_dual_run_comparison_is_persisted_and_protected(prepared_pilot, monkeypatch):
    client, _, _ = prepared_pilot
    monkeypatch.setenv("EVIDUE_AGREEMENT_RUNTIME_DUAL_RUN", "true")
    uploaded = client.post(
        "/api/pilot/evidence",
        params={"invoice_id": "INV-TEST-001", "source_type": "support"},
        files={"file": ("evidence.jsonl", PAYABLE_EVIDENCE, "application/x-ndjson")},
        headers=AUTH,
    )
    assert uploaded.status_code == 200, uploaded.text
    matched = client.post(
        "/api/pilot/match",
        params={"invoice_id": "INV-TEST-001"},
        headers=AUTH,
    )
    assert matched.status_code == 200, matched.text
    reconciled = client.post(
        "/api/pilot/reconcile",
        params={"invoice_id": "INV-TEST-001"},
        headers=AUTH,
    )
    assert reconciled.status_code == 200, reconciled.text
    run_id = reconciled.json()["reconciliation_id"]

    assert (
        client.get(f"/api/pilot/reconciliations/{run_id}/agreement-comparison").status_code == 401
    )
    response = client.get(
        f"/api/pilot/reconciliations/{run_id}/agreement-comparison",
        headers=AUTH,
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["exact_match"] is True
    assert payload["mismatch_count"] == 0
    assert payload["report"]["amounts_match"] is True
    assert payload["report"]["exact_mismatches"] == 0


# Generalized agreement runtime persistence ---------------------------------


def _approved_air_version(client: TestClient, contract_id: str) -> dict[str, object]:
    response = client.get(
        "/api/pilot/air-versions",
        params={"contract_id": contract_id},
        headers=AUTH,
    )
    assert response.status_code == 200, response.text
    approved = [item for item in response.json()["versions"] if item["approved_at"]]
    assert len(approved) == 1
    return approved[0]


def test_native_air_conformance_is_version_specific(prepared_pilot):
    client, _, contract_id = prepared_pilot
    version = _approved_air_version(client, contract_id)
    response = client.get(
        f"/api/pilot/air-versions/{version['id']}/conformance",
        headers=AUTH,
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["approvable"] is True
    assert payload["blocking_diagnostic_count"] == 0


def test_verification_plan_is_persisted_and_versioned(prepared_pilot):
    client, sessions, contract_id = prepared_pilot
    air_id = str(_approved_air_version(client, contract_id)["id"])

    first = client.post(
        f"/api/pilot/air-versions/{air_id}/verification-plan",
        json={"sources": []},
        headers=AUTH,
    )
    second = client.post(
        f"/api/pilot/air-versions/{air_id}/verification-plan",
        json={"sources": []},
        headers=AUTH,
    )
    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text
    assert first.json()["version"] == 1
    assert second.json()["version"] == 2

    latest = client.get(
        f"/api/pilot/air-versions/{air_id}/verification-plan",
        headers=AUTH,
    )
    assert latest.status_code == 200, latest.text
    assert latest.json()["version"] == 2
    assert latest.json()["plan"]["items"]

    with sessions() as session:
        count = session.scalar(
            select(func.count())
            .select_from(PilotVerificationPlanRow)
            .where(PilotVerificationPlanRow.air_version_id == air_id)
        )
        assert count == 2


def test_deterministic_facts_are_persisted_and_human_review_is_separate(prepared_pilot):
    client, _, contract_id = prepared_pilot
    air_id = str(_approved_air_version(client, contract_id)["id"])

    derived = client.post(
        "/api/pilot/invoices/INV-TEST-001/facts/derive",
        params={"air_version_id": air_id},
        headers=AUTH,
    )
    assert derived.status_code == 200, derived.text
    facts = derived.json()["facts"]
    assert facts
    assert all(item["input_hash"].startswith("sha256:") for item in facts)
    assert all(item["derivation_method"] == "deterministic_air_expression" for item in facts)

    unknown = next((item for item in facts if item["truth"] == "unknown"), None)
    assert unknown is not None
    reviewed = client.post(
        f"/api/pilot/facts/{unknown['id']}/review",
        json={
            "truth": "true",
            "rationale": "Operator verified the source evidence manually.",
            "reviewed_by": "Finance Operator",
        },
        headers=AUTH,
    )
    assert reviewed.status_code == 200, reviewed.text
    reviewed_fact = reviewed.json()["fact"]
    assert reviewed_fact["truth"] == "unknown"
    assert reviewed_fact["reviewed_truth"] == "true"
    assert reviewed_fact["review_status"] == "reviewed"

    fetched = client.get(
        "/api/pilot/invoices/INV-TEST-001/facts",
        params={"air_version_id": air_id},
        headers=AUTH,
    )
    assert fetched.status_code == 200
    assert any(item["id"] == unknown["id"] for item in fetched.json()["facts"])


def test_semantic_fact_extraction_is_feature_flagged(prepared_pilot, monkeypatch):
    client, sessions, contract_id = prepared_pilot
    monkeypatch.setenv("EVIDUE_SEMANTIC_FACT_ENABLED", "false")
    air_id = str(_approved_air_version(client, contract_id)["id"])
    with sessions() as session:
        claim_id = session.scalar(
            select(PilotClaimRow.id).where(PilotClaimRow.invoice_id == "INV-TEST-001")
        )
        raw_id = session.scalar(
            select(PilotRawRecordRow.id).where(PilotRawRecordRow.invoice_id == "INV-TEST-001")
        )
    response = client.post(
        "/api/pilot/invoices/INV-TEST-001/semantic-facts/extract",
        json={
            "air_version_id": air_id,
            "claim_id": claim_id,
            "fact_type": "customer_requested_human",
            "question": "Did the customer explicitly request a human agent?",
            "raw_record_ids": [raw_id],
        },
        headers=AUTH,
    )
    assert response.status_code == 409
    assert "disabled" in response.json()["detail"].lower()


def test_agreement_bundle_persists_documents_and_rejects_relation_cycles(prepared_pilot):
    client, _, contract_id = prepared_pilot
    initial = client.get(
        f"/api/pilot/contracts/{contract_id}/agreement-bundle",
        headers=AUTH,
    )
    assert initial.status_code == 200, initial.text
    original_document = initial.json()["documents"][0]
    original_id = original_document["id"]
    assert original_document["document_type"] == "primary_agreement"
    assert original_document["filename"]

    amendment = client.post(
        f"/api/pilot/contracts/{contract_id}/agreement-bundle/documents",
        params={
            "title": "Amendment 1",
            "document_type": "amendment",
            "effective_from": "2026-06-01T00:00:00Z",
            "precedence": 200,
        },
        files={
            "file": (
                "amendment.txt",
                "This amendment modifies the agreement and updates the controlling commercial terms for the pilot period.",
                "text/plain",
            )
        },
        headers=AUTH,
    )
    assert amendment.status_code == 200, amendment.text
    documents = amendment.json()["documents"]
    amendment_id = next(item["id"] for item in documents if item["title"] == "Amendment 1")

    relation = client.post(
        f"/api/pilot/contracts/{contract_id}/agreement-bundle/relations",
        json={
            "source_document_id": amendment_id,
            "target_document_id": original_id,
            "relation": "amends",
        },
        headers=AUTH,
    )
    assert relation.status_code == 200, relation.text

    cycle = client.post(
        f"/api/pilot/contracts/{contract_id}/agreement-bundle/relations",
        json={
            "source_document_id": original_id,
            "target_document_id": amendment_id,
            "relation": "incorporates",
        },
        headers=AUTH,
    )
    assert cycle.status_code == 422
    assert "circular" in cycle.json()["detail"].lower()


def test_approved_rules_become_stale_when_governing_documents_change(prepared_pilot):
    client, _, contract_id = prepared_pilot

    before = client.get("/api/pilot/status", headers=AUTH)
    assert before.status_code == 200
    assert before.json()["contract_approved"] is True
    assert before.json()["approved_rules_current"] is True

    changed = client.post(
        f"/api/pilot/contracts/{contract_id}/agreement-bundle/documents",
        params={
            "title": "Commercial Amendment",
            "document_type": "amendment",
            "effective_from": "2026-06-01T00:00:00Z",
            "precedence": 400,
        },
        files={
            "file": (
                "commercial-amendment.txt",
                "Effective June 15, 2026, the charge for each verified outcome is $1.75 and this amendment controls over conflicting pricing terms.",
                "text/plain",
            )
        },
        headers=AUTH,
    )
    assert changed.status_code == 200, changed.text

    after = client.get("/api/pilot/status", headers=AUTH)
    assert after.status_code == 200
    assert after.json()["contract_approved"] is False
    assert after.json()["approved_rules_current"] is False
    assert after.json()["approved_rules_stale"] is True
    assert after.json()["active_air_version_id"] is None

    reconciliation = client.post(
        "/api/pilot/reconcile",
        params={"invoice_id": "INV-TEST-001"},
        headers=AUTH,
    )
    assert reconciliation.status_code == 422
    assert "governing agreement documents changed" in reconciliation.json()["detail"].lower()


def test_mid_period_governing_change_fails_closed(prepared_pilot):
    client, _, contract_id = prepared_pilot
    changed = client.post(
        f"/api/pilot/contracts/{contract_id}/agreement-bundle/documents",
        params={
            "title": "Mid-month Amendment",
            "document_type": "amendment",
            "effective_from": "2026-06-15T00:00:00Z",
            "precedence": 400,
        },
        files={
            "file": (
                "mid-month-amendment.txt",
                "Effective June 15, 2026, the verified-outcome rate changes to $1.75 per outcome.",
                "text/plain",
            )
        },
        headers=AUTH,
    )
    assert changed.status_code == 200, changed.text
    assert changed.json()["internal_effective_boundaries"][0]["boundary"].startswith("2026-06-15")

    compiled = client.post(
        f"/api/pilot/contracts/{contract_id}/compile-native",
        params={"mode": "recorded"},
        headers=AUTH,
    )
    assert compiled.status_code == 409
    assert "changes inside the configured agreement period" in compiled.json()["detail"].lower()

    reconciliation = client.post(
        "/api/pilot/reconcile",
        params={"invoice_id": "INV-TEST-001"},
        headers=AUTH,
    )
    assert reconciliation.status_code == 422
    assert "fails closed" in reconciliation.json()["detail"].lower()


# Product workflow and usability hardening ----------------------------------


def test_sample_workspace_is_one_click_end_to_end(pilot_client):
    (
        client,
        _,
    ) = pilot_client
    response = client.post("/api/pilot/sample/seed", headers=AUTH)
    assert response.status_code == 200, response.text
    payload = response.json()
    reconciliation = payload["reconciliation"]
    assert reconciliation["claimed_outcomes"] == 3
    assert reconciliation["payable_outcomes"] == 1
    assert reconciliation["disputed_outcomes"] == 1
    assert reconciliation["needs_review_outcomes"] == 1
    assert reconciliation["submitted_amount"] == "4.50"
    assert reconciliation["confirmed_payable_amount"] == "1.50"
    assert reconciliation["recommended_deduction"] == "1.50"
    assert reconciliation["needs_review_amount"] == "1.50"

    status = client.get("/api/pilot/status", headers=AUTH)
    assert status.status_code == 200
    assert status.json()["contract_approved"] is True
    assert status.json()["accepted_match_rate"] == "100.0"

    detail = client.get("/api/pilot/reconciliation", headers=AUTH)
    assert detail.status_code == 200
    rows = detail.json()["determinations"]
    assert {row["status"] for row in rows} == {"payable", "disputed", "needs_review"}
    disputed = next(row for row in rows if row["status"] == "disputed")
    assert disputed["contract_clauses"]
    assert disputed["contract_clauses"][0]["text"]
    assert disputed["evidence"]

    corrected = client.get(
        f"/api/pilot/reconciliations/{reconciliation['reconciliation_id']}/exports/corrected-invoice.csv",
        headers=AUTH,
    )
    assert corrected.status_code == 200
    assert "outcome_id,billed_amount,decision,payable_amount" in corrected.text
    assert "OUT-SAMPLE-002,1.50,disputed,0.00,1.50,0.00" in corrected.text

    report = client.get(
        f"/api/pilot/reconciliations/{reconciliation['reconciliation_id']}/exports/review-report.html",
        headers=AUTH,
    )
    assert report.status_code == 200
    assert "Evidue reconciliation review" in report.text
    assert "Contract source" in report.text
    assert "Evidence timeline" in report.text

    audit = client.get("/api/pilot/audit-log", headers=AUTH)
    assert audit.status_code == 200
    export_events = [
        item for item in audit.json()["events"] if item["action"] == "export.generated"
    ]
    assert {item["details"]["kind"] for item in export_events} >= {
        "corrected-invoice.csv",
        "review-report.html",
    }


def test_reconciliation_never_calls_llm_after_air_approval(prepared_pilot, monkeypatch):
    client, _, _ = prepared_pilot
    import app.contracts.compiler as legacy_compiler
    from app.agreements import native_compiler

    def forbidden(*args, **kwargs):
        raise AssertionError("LLM compiler must not run during reconciliation")

    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setattr(native_compiler, "compile_native_with_gemini", forbidden)
    monkeypatch.setattr(legacy_compiler, "compile_with_gemini", forbidden)

    uploaded = client.post(
        "/api/pilot/evidence",
        params={"invoice_id": "INV-TEST-001", "source_type": "support", "complete_export": True},
        files={"file": ("evidence.jsonl", PAYABLE_EVIDENCE, "application/x-ndjson")},
        headers=AUTH,
    )
    assert uploaded.status_code == 200, uploaded.text
    assert (
        client.post(
            "/api/pilot/match", params={"invoice_id": "INV-TEST-001"}, headers=AUTH
        ).status_code
        == 200
    )
    reconciled = client.post(
        "/api/pilot/reconcile", params={"invoice_id": "INV-TEST-001"}, headers=AUTH
    )
    assert reconciled.status_code == 200, reconciled.text
    assert reconciled.json()["engine_version"].startswith("air-generic-")


def test_pasted_contract_and_invoice_mapping_preview_are_product_friendly(pilot_client):
    (
        client,
        _,
    ) = pilot_client
    source = (
        "Vendor earns $2.00 for each eligible completed outcome. "
        "An outcome is not billable when a human completes the promised work within 24 hours."
    )
    contract = client.post(
        "/api/pilot/contract/text",
        headers=AUTH,
        json={
            "customer": "Customer Co",
            "vendor": "Agent Vendor",
            "period_start": "2026-06-01T00:00:00Z",
            "period_end": "2026-07-01T00:00:00Z",
            "price_per_outcome": "2.00",
            "source_document": "agreement-paste.txt",
            "source_text": source,
        },
    )
    assert contract.status_code == 200, contract.text
    assert contract.json()["contract"]["source_document"] == "agreement-paste.txt"

    custom_csv = (
        "Resolution,Buyer,Topic,Finished,Charge\n"
        "OUT-MAP-1,CUST-MAP-1,refund,2026-06-05T12:00:00Z,$2.00\n"
    )
    preview = client.post(
        "/api/pilot/invoice/preview",
        headers=AUTH,
        files={"file": ("vendor-export.csv", custom_csv, "text/csv")},
    )
    assert preview.status_code == 200, preview.text
    assert preview.json()["headers"] == ["Resolution", "Buyer", "Topic", "Finished", "Charge"]
    assert preview.json()["missing_required_fields"]

    contract_id = contract.json()["contract"]["id"]
    uploaded = client.post(
        "/api/pilot/invoice",
        headers=AUTH,
        params={
            "contract_id": contract_id,
            "invoice_id": "INV-MAPPED-1",
            "billing_period_start": "2026-06-01T00:00:00Z",
            "billing_period_end": "2026-07-01T00:00:00Z",
            "column_mapping": '{"outcome_id":"Resolution","customer_id":"Buyer","intent":"Topic","closed_at":"Finished","billed_amount":"Charge"}',
        },
        files={"file": ("vendor-export.csv", custom_csv, "text/csv")},
    )
    assert uploaded.status_code == 200, uploaded.text
    assert uploaded.json()["claims_ingested"] == 1


def test_docx_contract_ingestion_without_office_runtime(pilot_client):
    import io
    import zipfile

    (
        client,
        _,
    ) = pilot_client
    contract_text = (
        "Vendor earns $1.50 for each supported outcome. "
        "A human completion within 24 hours makes the outcome non-billable."
    )
    xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        "<w:body><w:p><w:r><w:t>" + contract_text + "</w:t></w:r></w:p></w:body></w:document>"
    )
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("word/document.xml", xml)
    response = client.post(
        "/api/pilot/contract",
        headers=AUTH,
        params={
            "customer": "Acme",
            "vendor": "Nova",
            "period_start": "2026-06-01T00:00:00Z",
            "period_end": "2026-07-01T00:00:00Z",
            "price_per_outcome": "1.50",
        },
        files={
            "file": (
                "agreement.docx",
                buffer.getvalue(),
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["contract"]["source_document"] == "agreement.docx"


def test_workspace_tokens_enforce_database_isolation(monkeypatch, tmp_path):
    import json

    from app.main import app
    from app.upload import pilot_db

    alpha_token = "alpha-workspace-token-that-is-long-enough"
    beta_token = "beta-workspace-token-that-is-long-enough"
    monkeypatch.setenv(
        "EVIDUE_WORKSPACE_TOKENS",
        json.dumps({"alpha": alpha_token, "beta": beta_token}),
    )
    monkeypatch.setattr(pilot_db, "PILOT_DB_DIR", tmp_path / "workspaces")
    pilot_db._engines.pop("alpha", None)
    pilot_db._engines.pop("beta", None)
    pilot_db._factories.pop("alpha", None)
    pilot_db._factories.pop("beta", None)
    pilot_db._initialized.discard("alpha")
    pilot_db._initialized.discard("beta")

    alpha = {"Authorization": f"Bearer {alpha_token}"}
    beta = {"Authorization": f"Bearer {beta_token}"}
    with TestClient(app) as client:
        seeded = client.post("/api/pilot/sample/seed", headers=alpha)
        assert seeded.status_code == 200, seeded.text
        alpha_status = client.get("/api/pilot/status", headers=alpha)
        beta_status = client.get("/api/pilot/status", headers=beta)

    assert alpha_status.json()["workspace_id"] == "alpha"
    assert alpha_status.json()["claims"] == 3
    assert beta_status.json()["workspace_id"] == "beta"
    assert beta_status.json()["claims"] == 0
    assert beta_status.json()["active_contract_id"] is None
    assert (tmp_path / "workspaces" / "alpha.db").exists()
    assert (tmp_path / "workspaces" / "beta.db").exists()


def test_invalid_contract_documents_return_recoverable_422(pilot_client):
    client, _ = pilot_client
    params = {
        "customer": "Acme",
        "vendor": "Nova",
        "period_start": "2026-06-01T00:00:00Z",
        "period_end": "2026-07-01T00:00:00Z",
        "price_per_outcome": "1.50",
    }

    invalid_pdf = client.post(
        "/api/pilot/contract",
        headers=AUTH,
        params=params,
        files={"file": ("broken.pdf", b"not-a-pdf", "application/pdf")},
    )
    assert invalid_pdf.status_code == 422
    assert "PDF file is invalid" in invalid_pdf.text

    invalid_docx = client.post(
        "/api/pilot/contract",
        headers=AUTH,
        params=params,
        files={
            "file": (
                "broken.docx",
                b"not-a-docx",
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
    )
    assert invalid_docx.status_code == 422
    assert "DOCX file is invalid" in invalid_docx.text


def test_workspace_configuration_is_persisted_without_exposing_secrets(pilot_client):
    client, _ = pilot_client
    initial = client.get("/api/pilot/config", headers=AUTH)
    assert initial.status_code == 200, initial.text
    assert "GEMINI_API_KEY" not in initial.text
    assert "EVIDUE_PILOT_TOKEN" not in initial.text

    payload = {
        "company_name": "Acme Finance",
        "default_vendor": "Zendesk",
        "default_currency": "USD",
        "timezone": "America/New_York",
        "date_locale": "en-US",
        "default_contract_rate": "1.50",
        "preferred_support_system": "Zendesk",
        "preferred_payment_system": "Stripe",
        "preferred_crm_system": "Salesforce",
    }
    saved = client.put("/api/pilot/config", headers=AUTH, json=payload)
    assert saved.status_code == 200, saved.text
    assert saved.json()["company_name"] == "Acme Finance"
    assert saved.json()["preferred_support_system"] == "Zendesk"
    assert saved.json()["integrations"]["contract_ai"]["secret_location"] == "server_environment"

    # Clearing transactional pilot data intentionally preserves workspace preferences.
    cleared = client.post("/api/pilot/clear", headers=AUTH)
    assert cleared.status_code == 200, cleared.text
    again = client.get("/api/pilot/config", headers=AUTH)
    assert again.status_code == 200
    assert again.json()["company_name"] == "Acme Finance"


def test_workspace_configuration_rejects_invalid_finance_defaults(pilot_client):
    client, _ = pilot_client
    invalid_timezone = client.put(
        "/api/pilot/config",
        headers=AUTH,
        json={"timezone": "Not/A-Timezone"},
    )
    assert invalid_timezone.status_code == 422
    assert "valid IANA timezone" in invalid_timezone.json()["detail"]

    invalid_rate = client.put(
        "/api/pilot/config",
        headers=AUTH,
        json={"default_contract_rate": "-1.00"},
    )
    assert invalid_rate.status_code == 422
    assert "non-negative number" in invalid_rate.json()["detail"]


def test_invoice_preview_provides_finance_control_totals(pilot_client):
    client, _ = pilot_client
    csv = (
        "Outcome,Customer,Intent,Closed,Amount\n"
        "OUT-1,CUST-1,order_support,2026-06-02T08:00:00Z,1.50\n"
        "OUT-2,CUST-2,refund,2026-06-03T09:00:00Z,2.50\n"
        "OUT-3,CUST-1,order_support,2026-06-04T10:00:00Z,3.00\n"
    )
    mapping = {
        "outcome_id": "Outcome",
        "customer_id": "Customer",
        "intent": "Intent",
        "closed_at": "Closed",
        "billed_amount": "Amount",
    }
    response = client.post(
        "/api/pilot/invoice/preview",
        params={"column_mapping": __import__("json").dumps(mapping)},
        files={"file": ("vendor.csv", csv, "text/csv")},
        headers=AUTH,
    )
    assert response.status_code == 200, response.text
    totals = response.json()["control_totals"]
    assert totals["total_rows"] == 3
    assert totals["accepted_rows"] == 3
    assert totals["rejected_rows"] == 0
    assert totals["total_billed"] == "7.00"
    assert totals["unique_customers"] == 2
    assert totals["period_start"].startswith("2026-06-02")
    assert totals["period_end"].startswith("2026-06-04")
    mix = {item["name"]: item for item in totals["outcome_mix"]}
    assert mix["order_support"]["count"] == 2
    assert mix["refund"]["count"] == 1


def test_sample_air_and_exports_have_finance_facing_language(pilot_client):
    client, _ = pilot_client
    seeded = client.post("/api/pilot/sample/seed", headers=AUTH)
    assert seeded.status_code == 200, seeded.text
    payload = seeded.json()
    air_id = payload["air_version_id"]
    run_id = payload["reconciliation"]["reconciliation_id"]

    version = client.get(f"/api/pilot/air-versions/{air_id}", headers=AUTH)
    assert version.status_code == 200, version.text
    finance = version.json()["finance_view"]
    assert finance["contract_rules"]
    assert all(item["description"] for item in finance["contract_rules"])
    assert any(
        item["description"].startswith("Not payable if") for item in finance["contract_rules"]
    )
    assert finance["evidence_needed"]
    assert all(item["rule_description"] for item in finance["evidence_needed"])

    detail = client.get("/api/pilot/reconciliation", headers=AUTH)
    assert detail.status_code == 200, detail.text
    disputed = next(
        item for item in detail.json()["determinations"] if item["status"] == "disputed"
    )
    assert disputed["rule_description"]
    assert disputed["rule_description"].startswith("Not payable if")

    email = client.get(
        f"/api/pilot/reconciliations/{run_id}/exports/vendor-email.txt",
        headers=AUTH,
    )
    assert email.status_code == 200, email.text
    assert "Charges identified for dispute" in email.text
    assert "We reconciled" in email.text

    vendor_report = client.get(
        f"/api/pilot/reconciliations/{run_id}/exports/vendor-dispute.html",
        headers=AUTH,
    )
    assert vendor_report.status_code == 200, vendor_report.text
    assert "Invoice dispute report" in vendor_report.text
    assert "Charges identified for dispute" in vendor_report.text
    assert disputed["rule_description"] in vendor_report.text


def test_historical_replay_is_non_persistent_analysis(prepared_pilot):
    client, sessions, contract_id = prepared_pilot

    with sessions() as session:
        before = session.scalar(select(func.count()).select_from(PilotReconciliationRunRow))

    response = client.get(
        f"/api/pilot/contracts/{contract_id}/historical-replay",
        headers=AUTH,
    )
    assert response.status_code == 200, response.text
    payload = response.json()

    assert payload["historical_replay"] is True
    assert payload["simulation_only"] is True
    assert payload["financial_authority"] == "approved_air"
    assert payload["invoices_total"] == 1
    assert payload["invoices_replayed"] == 1
    assert payload["invoices_not_ready"] == 0
    assert payload["totals"]["billed"] == "1.50"
    assert payload["totals"]["conservation_passed"] is True
    assert Decimal(payload["totals"]["billed"]) == (
        Decimal(payload["totals"]["payable"])
        + Decimal(payload["totals"]["disputed"])
        + Decimal(payload["totals"]["needs_review"])
    )
    assert "recovered savings" in payload["warning"]

    with sessions() as session:
        after = session.scalar(select(func.count()).select_from(PilotReconciliationRunRow))
    assert after == before


def test_historical_replay_rejects_stale_approved_air(prepared_pilot):
    client, _sessions, contract_id = prepared_pilot

    changed = client.post(
        f"/api/pilot/contracts/{contract_id}/agreement-bundle/documents",
        params={
            "title": "Replay Commercial Amendment",
            "document_type": "amendment",
            "effective_from": "2026-06-01T00:00:00Z",
            "precedence": 400,
        },
        files={
            "file": (
                "replay-amendment.txt",
                "Effective June 1, 2026, the charge for each verified outcome is $1.75.",
                "text/plain",
            )
        },
        headers=AUTH,
    )
    assert changed.status_code == 200, changed.text

    replay = client.get(
        f"/api/pilot/contracts/{contract_id}/historical-replay",
        headers=AUTH,
    )
    assert replay.status_code == 409, replay.text
    assert "stale" in replay.json()["detail"].lower()


def test_candidate_air_financial_impact_is_simulation_only(prepared_pilot):
    client, _sessions, contract_id = prepared_pilot

    candidate = client.post(
        f"/api/pilot/contracts/{contract_id}/compile-native",
        params={"mode": "recorded"},
        headers=AUTH,
    )
    assert candidate.status_code == 200, candidate.text
    candidate_id = candidate.json()["air_version_id"]

    impact = client.get(
        f"/api/pilot/air-versions/{candidate_id}/financial-impact",
        params={"invoice_id": "INV-TEST-001"},
        headers=AUTH,
    )
    assert impact.status_code == 200, impact.text
    payload = impact.json()

    assert payload["simulation_only"] is True
    assert payload["financial_authority_changed"] is False
    assert payload["candidate_air_version"]["id"] == candidate_id
    assert payload["financial_authority_air_version_id"] != candidate_id
    assert payload["financial"]["affected_line_count"] == 0
    assert payload["financial"]["delta"] == {
        "payable": "0.00",
        "disputed": "0.00",
        "needs_review": "0.00",
    }


def test_independent_compiler_disagreement_blocks_air_approval(
    prepared_pilot,
    monkeypatch,
):
    import app.agreements.native_compiler as native_module
    from app.agreements.compiler_models import AgreementCompilationProposal
    from app.agreements.native_compiler import NativeCompilationResult, recorded_native_proposal

    client, _sessions, contract_id = prepared_pilot
    monkeypatch.setenv("EVIDUE_LLM_PRIMARY", "gemini")
    monkeypatch.setenv("EVIDUE_LLM_ASSURANCE_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_MODEL", "test-assurance-model")

    def replace_exact(value):
        if isinstance(value, dict):
            return {key: replace_exact(item) for key, item in value.items()}
        if isinstance(value, list):
            return [replace_exact(item) for item in value]
        return "1.75" if value == "1.50" else value

    def fake_compile_native(**kwargs):
        document_id, (title, text) = next(iter(kwargs["source_documents"].items()))
        recorded = recorded_native_proposal(
            contract_id=kwargs["contract_id"],
            document_id=document_id,
            title=title,
            contract_text=text,
        )
        provider = kwargs.get("provider") or "gemini"
        proposal = recorded.proposal
        if provider == "openai":
            proposal = AgreementCompilationProposal.model_validate(
                replace_exact(proposal.model_dump(mode="json"))
            )
        return NativeCompilationResult(
            proposal=proposal,
            prompt_hash=f"sha256:test-{provider}",
            raw_response={"test": True},
            live_model_call=True,
            model=f"test-{provider}",
            provider="openai" if provider == "openai" else "google-gemini",
            provenance={"provider": provider, "model": f"test-{provider}"},
        )

    monkeypatch.setattr(native_module, "compile_native", fake_compile_native)

    compiled = client.post(
        f"/api/pilot/contracts/{contract_id}/compile-native",
        params={"mode": "live"},
        headers=AUTH,
    )
    assert compiled.status_code == 200, compiled.text
    payload = compiled.json()

    assert payload["approval_ready"] is False
    assert payload["compiler_consensus"]["status"] == "material_disagreement"
    assert payload["compiler_consensus"]["approval_blocked"] is True
    assert any(
        item["code"] == "INDEPENDENT_COMPILER_DISAGREEMENT" and item["severity"] == "blocking"
        for item in payload["diagnostics"]
    )

    approved = client.post(
        f"/api/pilot/air-versions/{payload['air_version_id']}/approve",
        headers=AUTH,
    )
    assert approved.status_code == 409
    assert "assurance" in approved.text.lower() or "approvable" in approved.text.lower()
