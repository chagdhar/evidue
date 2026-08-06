"""Persistence for the pilot upload path.

All functions use the same SessionLocal and tables as the demo path.
The pilot path writes to OutcomeClaimRow and OperationalEventRow — the
same tables the existing reconciliation code reads from — so the
unmodified run_reconciliation() works on uploaded data.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.db.models import (
    ConversationRow,
    EvidenceReferenceRow,
    InvoiceRow,
    ManualMatchRow,
    OperationalEventRow,
    OutcomeClaimRow,
    OutcomeDeterminationRow,
    PilotStateRow,
    ReconciliationRow,
    UploadRejectionRow,
    UploadRow,
)
from app.upload.match import (
    ClaimIdentity,
    IdentityMapping,
    MatchCandidate,
    MatchingSummary,
    MatchResult,
    run_matching,
)
from app.upload.parsers import ParseResult


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _uid() -> str:
    return uuid.uuid4().hex[:12]


# ---------------------------------------------------------------------------
# Pilot state
# ---------------------------------------------------------------------------


def ensure_pilot_state(session: Session) -> PilotStateRow:
    state = session.get(PilotStateRow, 1)
    if state is None:
        state = PilotStateRow(id=1, initialized=True)
        session.add(state)
        session.flush()
    return state


# ---------------------------------------------------------------------------
# Upload tracking
# ---------------------------------------------------------------------------


def create_upload(
    session: Session,
    upload_type: str,
    filename: str,
    source_type: str | None = None,
) -> UploadRow:
    row = UploadRow(
        id=f"UPL-{_uid()}",
        upload_type=upload_type,
        filename=filename,
        uploaded_at=_now(),
        status="processing",
        source_type=source_type,
    )
    session.add(row)
    session.flush()
    return row


def finalize_upload(
    session: Session,
    upload: UploadRow,
    result: ParseResult,
) -> None:
    upload.rows_parsed = len(result.accepted) + len(result.rejected)
    upload.rows_accepted = len(result.accepted)
    upload.rows_rejected = len(result.rejected)
    upload.status = "complete" if result.accepted else "failed"
    if result.rejected:
        upload.error_summary = f"{len(result.rejected)} rows rejected"
    for rej in result.rejected:
        session.add(
            UploadRejectionRow(
                upload_id=upload.id,
                row_number=rej.row_number,
                reason=rej.reason,
                raw_data=rej.raw_data,
            )
        )


def fail_upload(session: Session, upload: UploadRow, reason: str) -> None:
    upload.status = "failed"
    upload.error_summary = reason


# ---------------------------------------------------------------------------
# Invoice ingestion
# ---------------------------------------------------------------------------


def ingest_invoice_claims(
    session: Session,
    upload: UploadRow,
    result: ParseResult,
    invoice_id: str,
) -> int:
    """Write parsed invoice rows to OutcomeClaimRow + ConversationRow.

    Returns number of claims ingested.
    """
    count = 0
    for row in result.accepted:
        d = row.data
        # Skip duplicates
        existing = session.get(OutcomeClaimRow, d["outcome_id"])
        if existing:
            continue

        claim = OutcomeClaimRow(
            outcome_id=d["outcome_id"],
            vendor_claim_id=d["vendor_claim_id"],
            external_conversation_id=d.get("conversation_id", ""),
            agent_version=d.get("agent_version", "unknown"),
            raw_record_id=None,
            invoice_id=invoice_id,
            customer_id=d["customer_id"],
            intent=d["intent"],
            vendor_claim=d["vendor_claim"],
            closed_at=d["closed_at"],
            expected_action=d["expected_action"],
            account_id=d["account_id"],
            billed_amount=d["billed_amount"],
        )
        session.add(claim)

        conversation = ConversationRow(
            id=d.get("conversation_id", "") or d["outcome_id"],
            outcome_id=d["outcome_id"],
            customer_id=d["customer_id"],
            intent=d["intent"],
            closed_at=d["closed_at"],
        )
        session.add(conversation)
        count += 1

    return count


# ---------------------------------------------------------------------------
# Evidence ingestion
# ---------------------------------------------------------------------------


def ingest_evidence_events(
    session: Session,
    upload: UploadRow,
    result: ParseResult,
) -> int:
    """Write parsed evidence rows to OperationalEventRow.

    Returns number of events ingested.
    """
    now = _now()
    count = 0
    for row in result.accepted:
        d = row.data
        event_id = d["event_id"]

        # Deduplicate by source_record_id
        existing = session.scalar(
            select(OperationalEventRow).where(
                OperationalEventRow.source_record_id == d["source_record_id"]
            )
        )
        if existing:
            continue

        event = OperationalEventRow(
            id=event_id,
            source_system=d["source_system"],
            source_record_id=d["source_record_id"],
            event_type=d["event_type"],
            timestamp=d["timestamp"],
            customer_id=d["customer_id"],
            outcome_id=d.get("outcome_id"),
            values=d.get("values", {}),
            ingested_at=now,
            connector_id=None,
            raw_record_id=None,
            match_method="pending",
            match_confidence=Decimal("0.0000"),
            payload_hash=d.get("payload_hash", ""),
            schema_version="upload-v1",
            source_locator=upload.id,
            external_keys={},
        )
        session.add(event)
        count += 1

    return count


# ---------------------------------------------------------------------------
# Identity matching
# ---------------------------------------------------------------------------


def run_identity_matching(
    session: Session,
    identity_mappings: list[IdentityMapping] | None = None,
) -> MatchingSummary:
    """Run the matching pipeline across all events and claims in the DB."""
    claims = session.scalars(select(OutcomeClaimRow)).all()
    events = session.scalars(
        select(OperationalEventRow).where(
            OperationalEventRow.match_method.in_(["pending", "unresolved"])
        )
    ).all()

    if not claims or not events:
        return MatchingSummary(
            total_events=len(events),
            direct_matches=0,
            identity_map_matches=0,
            composite_matches=0,
            unresolved=len(events),
            unresolved_value=Decimal("0.00"),
        )

    # Also fold in manual matches
    manual_matches = session.scalars(select(ManualMatchRow)).all()
    manual_by_event = {m.event_id: m.outcome_id for m in manual_matches}

    claim_identities = [
        ClaimIdentity(
            outcome_id=c.outcome_id,
            customer_id=c.customer_id,
            conversation_id=c.external_conversation_id,
            account_id=c.account_id,
            closed_at=c.closed_at.isoformat(),
            intent=c.intent,
        )
        for c in claims
    ]

    event_candidates = [
        MatchCandidate(
            event_id=e.id,
            event_outcome_id=e.outcome_id,
            event_customer_id=e.customer_id,
            event_timestamp=e.timestamp.isoformat(),
            event_type=e.event_type,
            event_values=e.values or {},
        )
        for e in events
    ]

    results, summary = run_matching(
        event_candidates, claim_identities, identity_mappings
    )

    # Apply manual overrides
    for result in results:
        if result.event_id in manual_by_event:
            outcome_id = manual_by_event[result.event_id]
            result = MatchResult(
                event_id=result.event_id,
                outcome_id=outcome_id,
                method="manual",
                confidence=Decimal("1.0000"),
                reason="Manually matched by operator",
            )

    # Update event rows with match results
    events_by_id = {e.id: e for e in events}
    for result in results:
        event = events_by_id.get(result.event_id)
        if not event:
            continue

        # Manual overrides take precedence
        if result.event_id in manual_by_event:
            event.outcome_id = manual_by_event[result.event_id]
            event.match_method = "manual"
            event.match_confidence = Decimal("1.0000")
        elif result.outcome_id:
            event.outcome_id = result.outcome_id
            event.match_method = result.method
            event.match_confidence = result.confidence
        else:
            event.match_method = "unresolved"
            event.match_confidence = Decimal("0.0000")

    return summary


# ---------------------------------------------------------------------------
# Manual matching (review workbench)
# ---------------------------------------------------------------------------


def get_unmatched_events(
    session: Session, limit: int = 50, offset: int = 0,
) -> tuple[int, list[dict]]:
    """Return events that have no resolved match."""
    base = select(OperationalEventRow).where(
        OperationalEventRow.match_method.in_(["unresolved", "pending"])
    )
    total = session.scalar(
        select(func.count()).select_from(base.subquery())
    ) or 0

    events = session.scalars(
        base.order_by(OperationalEventRow.timestamp).offset(offset).limit(limit)
    ).all()

    results = []
    for e in events:
        results.append({
            "event_id": e.id,
            "source_system": e.source_system,
            "event_type": e.event_type,
            "timestamp": e.timestamp.isoformat(),
            "customer_id": e.customer_id,
            "outcome_id": e.outcome_id,
            "values": e.values,
        })

    return total, results


def get_match_candidates(
    session: Session, event_id: str, limit: int = 10,
) -> list[dict]:
    """For an unmatched event, suggest claims it might belong to."""
    event = session.get(OperationalEventRow, event_id)
    if not event:
        return []

    # Find claims by the same customer
    candidates = session.scalars(
        select(OutcomeClaimRow)
        .where(OutcomeClaimRow.customer_id == event.customer_id)
        .order_by(OutcomeClaimRow.closed_at)
        .limit(limit)
    ).all()

    results = []
    for c in candidates:
        time_delta = abs((event.timestamp - c.closed_at).total_seconds())
        results.append({
            "outcome_id": c.outcome_id,
            "customer_id": c.customer_id,
            "intent": c.intent,
            "closed_at": c.closed_at.isoformat(),
            "expected_action": c.expected_action,
            "time_delta_seconds": int(time_delta),
            "time_delta_human": _format_delta(time_delta),
        })

    return sorted(results, key=lambda r: r["time_delta_seconds"])


def confirm_manual_match(
    session: Session,
    event_id: str,
    outcome_id: str,
    rationale: str,
    confirmed_by: str = "operator",
) -> ManualMatchRow:
    """Record a manual match and update the event."""
    match_row = ManualMatchRow(
        event_id=event_id,
        outcome_id=outcome_id,
        confirmed_by=confirmed_by,
        confirmed_at=_now(),
        rationale=rationale,
    )
    session.add(match_row)

    event = session.get(OperationalEventRow, event_id)
    if event:
        event.outcome_id = outcome_id
        event.match_method = "manual"
        event.match_confidence = Decimal("1.0000")

    return match_row


def _format_delta(seconds: float) -> str:
    if seconds < 60:
        return f"{int(seconds)}s"
    if seconds < 3600:
        return f"{int(seconds / 60)}m"
    if seconds < 86400:
        return f"{seconds / 3600:.1f}h"
    return f"{seconds / 86400:.1f}d"


# ---------------------------------------------------------------------------
# Pilot status / clear
# ---------------------------------------------------------------------------


def pilot_status(session: Session) -> dict:
    """Return current pilot ingestion status."""
    state = ensure_pilot_state(session)

    uploads = session.scalars(select(UploadRow).order_by(UploadRow.uploaded_at.desc())).all()
    claim_count = session.scalar(select(func.count()).select_from(OutcomeClaimRow)) or 0
    event_count = session.scalar(select(func.count()).select_from(OperationalEventRow)) or 0
    matched_count = session.scalar(
        select(func.count()).select_from(
            select(OperationalEventRow)
            .where(OperationalEventRow.match_method.notin_(["pending", "unresolved"]))
            .subquery()
        )
    ) or 0
    unmatched_count = session.scalar(
        select(func.count()).select_from(
            select(OperationalEventRow)
            .where(OperationalEventRow.match_method.in_(["pending", "unresolved"]))
            .subquery()
        )
    ) or 0

    reconciliation = session.scalar(
        select(ReconciliationRow).order_by(ReconciliationRow.evaluated_at.desc())
    )

    return {
        "initialized": state.initialized,
        "invoice_uploaded": state.invoice_uploaded,
        "evidence_uploaded": state.evidence_uploaded,
        "matching_complete": state.matching_complete,
        "reconciled": state.reconciled,
        "active_invoice_id": state.active_invoice_id,
        "active_contract_id": state.active_contract_id,
        "claims": claim_count,
        "events": event_count,
        "matched_events": matched_count,
        "unmatched_events": unmatched_count,
        "match_rate": (
            f"{matched_count / event_count * 100:.1f}"
            if event_count > 0
            else "0.0"
        ),
        "reconciliation_id": reconciliation.id if reconciliation else None,
        "uploads": [
            {
                "id": u.id,
                "type": u.upload_type,
                "filename": u.filename,
                "uploaded_at": u.uploaded_at.isoformat(),
                "status": u.status,
                "rows_accepted": u.rows_accepted,
                "rows_rejected": u.rows_rejected,
                "source_type": u.source_type,
            }
            for u in uploads
        ],
    }


def clear_pilot_data(session: Session) -> None:
    """Delete all pilot-uploaded data, keeping demo data untouched.

    This is intentionally aggressive — it clears all claim, event,
    determination, and upload data. In the pilot phase there is only
    one customer's data in the DB at a time.
    """
    session.execute(delete(EvidenceReferenceRow))
    session.execute(delete(OutcomeDeterminationRow))
    session.execute(delete(ReconciliationRow))
    session.execute(delete(ManualMatchRow))
    session.execute(delete(ConversationRow))
    session.execute(delete(OperationalEventRow))
    session.execute(delete(OutcomeClaimRow))
    session.execute(delete(UploadRejectionRow))
    session.execute(delete(UploadRow))
    session.execute(delete(InvoiceRow))
    state = ensure_pilot_state(session)
    state.invoice_uploaded = False
    state.evidence_uploaded = False
    state.matching_complete = False
    state.reconciled = False
    state.active_invoice_id = None
