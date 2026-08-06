"""Tests for the pilot upload path: parsers, matching, and API."""

from decimal import Decimal

import pytest
from app.upload.match import (
    ClaimIdentity,
    IdentityMapping,
    MatchCandidate,
    run_matching,
)
from app.upload.parsers import (
    parse_evidence_csv,
    parse_evidence_json,
    parse_evidence_jsonl,
    parse_identity_map_csv,
    parse_invoice_csv,
)

# -----------------------------------------------------------------------
# Invoice CSV parser
# -----------------------------------------------------------------------


INVOICE_CSV_STANDARD = """\
outcome_id,customer_reference,account_reference,claimed_outcome_type,claimed_completion_time,billed_amount,vendor_claim_id,vendor_disposition,conversation_id,agent_version
OUT-001,CUST-001,ACC-001,order_support,2026-06-02T08:01:00,1.50,CLM-001,resolved,CONV-001,v4.2
OUT-002,CUST-002,ACC-002,refund,2026-06-03T10:00:00,2.00,CLM-002,resolved,CONV-002,v4.2
"""

INVOICE_CSV_ALTERNATE_COLUMNS = """\
Outcome ID,Customer ID,Account ID,Intent,Closed At,Amount,Claim ID
OUT-100,CUST-100,ACC-100,billing_dispute,2026-07-01T12:00:00,3.50,CLM-100
"""

INVOICE_CSV_MISSING_REQUIRED = """\
outcome_id,customer_reference,billed_amount
,CUST-001,1.50
OUT-002,,1.50
"""

INVOICE_CSV_BAD_TIMESTAMP = """\
outcome_id,customer_reference,claimed_completion_time,billed_amount
OUT-001,CUST-001,not-a-date,1.50
"""


def test_parse_invoice_csv_standard():
    result = parse_invoice_csv(INVOICE_CSV_STANDARD)
    assert len(result.accepted) == 2
    assert len(result.rejected) == 0

    claim = result.accepted[0].data
    assert claim["outcome_id"] == "OUT-001"
    assert claim["customer_id"] == "CUST-001"
    assert claim["account_id"] == "ACC-001"
    assert claim["intent"] == "order_support"
    assert claim["billed_amount"] == Decimal("1.50")
    assert claim["vendor_claim_id"] == "CLM-001"


def test_parse_invoice_csv_alternate_columns():
    result = parse_invoice_csv(INVOICE_CSV_ALTERNATE_COLUMNS)
    assert len(result.accepted) == 1
    assert result.accepted[0].data["outcome_id"] == "OUT-100"
    assert result.accepted[0].data["customer_id"] == "CUST-100"
    assert result.accepted[0].data["billed_amount"] == Decimal("3.50")


def test_parse_invoice_csv_missing_required():
    result = parse_invoice_csv(INVOICE_CSV_MISSING_REQUIRED)
    assert len(result.accepted) == 0
    assert len(result.rejected) == 2
    assert "Missing outcome_id" in result.rejected[0].reason
    # Second row has outcome_id but no timestamp column, so it fails on timestamp
    assert result.rejected[1].reason != ""


def test_parse_invoice_csv_bad_timestamp():
    result = parse_invoice_csv(INVOICE_CSV_BAD_TIMESTAMP)
    assert len(result.rejected) == 1
    assert "Unparseable timestamp" in result.rejected[0].reason


def test_parse_invoice_csv_empty():
    result = parse_invoice_csv("")
    assert len(result.accepted) == 0
    assert len(result.rejected) == 1
    assert "Empty" in result.rejected[0].reason


def test_parse_invoice_csv_no_outcome_column():
    result = parse_invoice_csv("foo,bar\n1,2\n")
    assert len(result.accepted) == 0
    assert "Missing required column" in result.rejected[0].reason


# -----------------------------------------------------------------------
# Evidence parsers
# -----------------------------------------------------------------------


EVIDENCE_CSV = """\
event_id,event_type,occurred_at,customer_id,outcome_id,account_id,action
EV-001,customer_recontact,2026-06-03T09:00:00,CUST-001,OUT-001,ACC-001,
EV-002,downstream_failed,2026-06-03T10:00:00,CUST-002,OUT-002,ACC-002,refund
"""

EVIDENCE_JSONL = """\
{"event_id": "EV-001", "event_type": "ai_closed", "occurred_at": "2026-06-02T08:01:00", "customer_id": "CUST-001", "outcome_id": "OUT-001"}
{"event_id": "EV-002", "event_type": "downstream_succeeded", "occurred_at": "2026-06-02T08:30:00", "customer_id": "CUST-001", "outcome_id": "OUT-001", "account_id": "ACC-001", "action": "order_update"}
"""

EVIDENCE_JSON = """\
[
  {"event_id": "EV-010", "event_type": "human_completion", "occurred_at": "2026-06-05T14:00:00", "customer_id": "CUST-010", "outcome_id": "OUT-010"},
  {"event_id": "EV-011", "event_type": "downstream_succeeded", "occurred_at": "2026-06-05T15:00:00", "customer_id": "CUST-011"}
]
"""


def test_parse_evidence_csv():
    result = parse_evidence_csv(EVIDENCE_CSV, "acme_support")
    assert len(result.accepted) == 2
    ev = result.accepted[0].data
    assert ev["event_type"] == "customer_recontact"
    assert ev["customer_id"] == "CUST-001"
    assert ev["outcome_id"] == "OUT-001"
    assert ev["source_system"] == "acme_support"


def test_parse_evidence_jsonl():
    result = parse_evidence_jsonl(EVIDENCE_JSONL, "nova_agent")
    assert len(result.accepted) == 2
    assert result.accepted[0].data["event_type"] == "ai_closed"
    assert result.accepted[1].data["values"]["action"] == "order_update"


def test_parse_evidence_json():
    result = parse_evidence_json(EVIDENCE_JSON, "acme_support")
    assert len(result.accepted) == 2
    # Second record has no outcome_id — it should still parse
    assert result.accepted[1].data["outcome_id"] is None


def test_parse_evidence_csv_missing_timestamp():
    csv_data = "event_id,event_type,customer_id\nEV-001,test,CUST-001\n"
    result = parse_evidence_csv(csv_data, "test")
    assert len(result.rejected) == 1
    assert "timestamp" in result.rejected[0].reason.lower()


def test_parse_evidence_jsonl_bad_json():
    result = parse_evidence_jsonl("not json\n", "test")
    assert len(result.rejected) == 1
    assert "Invalid JSON" in result.rejected[0].reason


# -----------------------------------------------------------------------
# Identity map parser
# -----------------------------------------------------------------------


IDENTITY_MAP_CSV = """\
conversation_id,customer_id,customer_account_id
CONV-001,CUST-001,ACC-001
CONV-002,CUST-002,ACC-002
"""


def test_parse_identity_map():
    result = parse_identity_map_csv(IDENTITY_MAP_CSV)
    assert len(result.accepted) == 2
    mapping = result.accepted[0].data
    assert mapping["conversation_id"] == "CONV-001"
    assert mapping["customer_id"] == "CUST-001"
    assert mapping["account_id"] == "ACC-001"


def test_parse_identity_map_too_few_columns():
    result = parse_identity_map_csv("foo\nbar\n")
    assert len(result.accepted) == 0
    assert "2 recognized identity columns" in result.rejected[0].reason


# -----------------------------------------------------------------------
# Matching pipeline
# -----------------------------------------------------------------------


def _make_claims() -> list[ClaimIdentity]:
    return [
        ClaimIdentity("OUT-001", "CUST-001", "CONV-001", "ACC-001", "2026-06-02T08:01:00", "order_support"),
        ClaimIdentity("OUT-002", "CUST-002", "CONV-002", "ACC-002", "2026-06-03T10:00:00", "refund"),
    ]


def test_direct_match():
    claims = _make_claims()
    events = [
        MatchCandidate("EV-001", "OUT-001", "CUST-001", "2026-06-02T09:00:00", "recontact", {}),
    ]
    results, summary = run_matching(events, claims)
    assert len(results) == 1
    assert results[0].outcome_id == "OUT-001"
    assert results[0].method == "direct_outcome_id"
    assert summary.direct_matches == 1
    assert summary.unresolved == 0


def test_identity_map_match():
    claims = _make_claims()
    events = [
        MatchCandidate("EV-010", None, "CUST-001", "2026-06-02T09:00:00", "recontact", {"conversation_id": "CONV-001"}),
    ]
    mappings = [
        IdentityMapping(conversation_id="CONV-001", customer_id="CUST-001", account_id="ACC-001", outcome_id="OUT-001"),
    ]
    results, summary = run_matching(events, claims, mappings)
    assert results[0].outcome_id == "OUT-001"
    assert results[0].method == "identity_map_conversation"
    assert summary.identity_map_matches == 1


def test_composite_match():
    claims = _make_claims()
    events = [
        MatchCandidate("EV-020", None, "CUST-002", "2026-06-03T10:30:00", "refund", {}),
    ]
    results, summary = run_matching(events, claims)
    assert results[0].outcome_id == "OUT-002"
    assert results[0].method == "composite_customer_time"
    assert summary.composite_matches == 1


def test_unresolved_match():
    claims = _make_claims()
    events = [
        MatchCandidate("EV-030", None, "CUST-999", "2026-06-03T10:00:00", "unknown", {}),
    ]
    results, summary = run_matching(events, claims)
    assert results[0].outcome_id is None
    assert results[0].method == "unresolved"
    assert summary.unresolved == 1


def test_matching_empty_inputs():
    _results, summary = run_matching([], [])
    assert summary.total_events == 0
    assert summary.unresolved == 0


# -----------------------------------------------------------------------
# API integration tests (using TestClient)
# -----------------------------------------------------------------------


@pytest.fixture(scope="module")
def test_db():
    """Set up a fresh in-memory DB for integration tests."""
    import app.db.repository as repo_mod
    from app.db.models import Base
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    old_engine = repo_mod.engine
    old_session = repo_mod.SessionLocal

    test_engine = create_engine("sqlite:///:memory:", future=True)
    test_session = sessionmaker(test_engine, expire_on_commit=False)
    Base.metadata.create_all(test_engine)

    repo_mod.engine = test_engine
    repo_mod.SessionLocal = test_session

    yield test_session

    repo_mod.engine = old_engine
    repo_mod.SessionLocal = old_session


def test_store_ingest_invoice(test_db):
    """Ingest invoice claims via the store layer."""
    from app.upload.store import (
        create_upload,
        ensure_pilot_state,
        finalize_upload,
        ingest_invoice_claims,
        pilot_status,
    )

    invoice_csv = (
        "outcome_id,customer_reference,account_reference,claimed_outcome_type,"
        "claimed_completion_time,billed_amount,vendor_claim_id,vendor_disposition\n"
        "OUT-S01,CUST-S01,ACC-S01,order_support,2026-06-02T08:01:00,1.50,CLM-S01,resolved\n"
        "OUT-S02,CUST-S02,ACC-S02,refund,2026-06-03T10:00:00,2.00,CLM-S02,resolved\n"
    )
    result = parse_invoice_csv(invoice_csv)
    assert len(result.accepted) == 2

    with test_db.begin() as session:
        state = ensure_pilot_state(session)

        # Create a minimal invoice row
        from datetime import datetime

        from app.db.models import ContractRow, InvoiceRow
        session.add(ContractRow(
            id="C-TEST", customer="Test", vendor="Test",
            period_start=datetime(2026, 1, 1), period_end=datetime(2026, 12, 31),
            price_per_outcome=Decimal("1.50"),
        ))
        session.add(InvoiceRow(
            id="INV-TEST", contract_id="C-TEST",
            billing_period_start=datetime(2026, 6, 1),
            billing_period_end=datetime(2026, 6, 30),
            submitted_at=datetime(2026, 7, 1),
        ))

        upload = create_upload(session, "invoice", "test.csv")
        count = ingest_invoice_claims(session, upload, result, "INV-TEST")
        finalize_upload(session, upload, result)
        state.invoice_uploaded = True

    assert count == 2

    with test_db() as session:
        status = pilot_status(session)
        assert status["claims"] == 2
        assert status["invoice_uploaded"] is True


def test_store_ingest_evidence_and_match(test_db):
    """Ingest evidence and run matching."""
    from app.upload.store import (
        create_upload,
        ensure_pilot_state,
        finalize_upload,
        ingest_evidence_events,
        run_identity_matching,
    )

    evidence_jsonl = (
        '{"event_id": "EV-S01", "event_type": "ai_closed", '
        '"occurred_at": "2026-06-02T08:01:00", "customer_id": "CUST-S01", '
        '"outcome_id": "OUT-S01"}\n'
        '{"event_id": "EV-S02", "event_type": "downstream_failed", '
        '"occurred_at": "2026-06-03T10:30:00", "customer_id": "CUST-S02", '
        '"outcome_id": "OUT-S02"}\n'
    )
    result = parse_evidence_jsonl(evidence_jsonl, "test_source")
    assert len(result.accepted) == 2

    with test_db.begin() as session:
        state = ensure_pilot_state(session)
        upload = create_upload(session, "evidence", "test.jsonl", "test_source")
        count = ingest_evidence_events(session, upload, result)
        finalize_upload(session, upload, result)
        state.evidence_uploaded = True

    assert count == 2

    with test_db.begin() as session:
        summary = run_identity_matching(session)

    assert summary.direct_matches == 2
    assert summary.unresolved == 0


def test_store_clear(test_db):
    """Clear resets pilot data."""
    from app.upload.store import clear_pilot_data, pilot_status

    with test_db.begin() as session:
        clear_pilot_data(session)

    with test_db() as session:
        status = pilot_status(session)
        assert status["claims"] == 0
        assert status["events"] == 0
