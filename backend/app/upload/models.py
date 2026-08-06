"""Database models dedicated to the real-data pilot path.

These tables intentionally use a ``pilot_`` prefix and live in a separate
SQLite database.  The demo and pilot share deterministic domain code, never
unscoped persisted data.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models import Base


class PilotStateRow(Base):
    __tablename__ = "pilot_state_v2"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    initialized: Mapped[bool] = mapped_column(Boolean, default=True)
    active_contract_id: Mapped[str | None] = mapped_column(String, nullable=True)
    active_invoice_id: Mapped[str | None] = mapped_column(String, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime)


class PilotUploadRow(Base):
    __tablename__ = "pilot_uploads"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    upload_type: Mapped[str] = mapped_column(String, index=True)
    filename: Mapped[str] = mapped_column(String)
    content_type: Mapped[str | None] = mapped_column(String, nullable=True)
    uploaded_by: Mapped[str] = mapped_column(String)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String, index=True)
    rows_parsed: Mapped[int] = mapped_column(Integer, default=0)
    rows_accepted: Mapped[int] = mapped_column(Integer, default=0)
    rows_rejected: Mapped[int] = mapped_column(Integer, default=0)
    error_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_type: Mapped[str | None] = mapped_column(String, nullable=True)
    invoice_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    sha256: Mapped[str] = mapped_column(String)


class PilotUploadRejectionRow(Base):
    __tablename__ = "pilot_upload_rejections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    upload_id: Mapped[str] = mapped_column(ForeignKey("pilot_uploads.id"), index=True)
    row_number: Mapped[int] = mapped_column(Integer)
    reason: Mapped[str] = mapped_column(Text)
    raw_data: Mapped[dict] = mapped_column(JSON)


class PilotContractRow(Base):
    __tablename__ = "pilot_contracts"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    customer: Mapped[str] = mapped_column(String)
    vendor: Mapped[str] = mapped_column(String)
    period_start: Mapped[datetime] = mapped_column(DateTime)
    period_end: Mapped[datetime] = mapped_column(DateTime)
    price_per_outcome: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"))
    source_document: Mapped[str] = mapped_column(String)
    source_text: Mapped[str] = mapped_column(Text)
    source_hash: Mapped[str] = mapped_column(String)
    upload_id: Mapped[str] = mapped_column(ForeignKey("pilot_uploads.id"))
    active_compilation_id: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime)


class PilotRuleCompilationRow(Base):
    __tablename__ = "pilot_rule_compilations"
    __table_args__ = (
        UniqueConstraint("contract_id", "version", name="uq_pilot_compilation_version"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    contract_id: Mapped[str] = mapped_column(ForeignKey("pilot_contracts.id"), index=True)
    source_document: Mapped[str] = mapped_column(String)
    source_hash: Mapped[str] = mapped_column(String)
    prompt_hash: Mapped[str] = mapped_column(String)
    provider: Mapped[str] = mapped_column(String)
    model: Mapped[str] = mapped_column(String)
    compiler_version: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, index=True)
    version: Mapped[int] = mapped_column(Integer)
    live_model_call: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    rules: Mapped[list] = mapped_column(JSON)
    raw_response: Mapped[dict] = mapped_column(JSON)


class PilotContractRuleRow(Base):
    __tablename__ = "pilot_contract_rules"
    __table_args__ = (
        UniqueConstraint("compilation_id", "rule_id", name="uq_pilot_compilation_rule"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    compilation_id: Mapped[str] = mapped_column(
        ForeignKey("pilot_rule_compilations.id"), index=True
    )
    rule_id: Mapped[str] = mapped_column(String, index=True)
    title: Mapped[str] = mapped_column(String)
    description: Mapped[str] = mapped_column(Text)
    clause_text: Mapped[str] = mapped_column(Text)
    operation: Mapped[str] = mapped_column(String)
    parameters: Mapped[dict] = mapped_column(JSON)
    evidence_required: Mapped[list] = mapped_column(JSON)
    priority: Mapped[int] = mapped_column(Integer)
    consequence: Mapped[str] = mapped_column(String)


class PilotInvoiceRow(Base):
    __tablename__ = "pilot_invoices"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    contract_id: Mapped[str] = mapped_column(ForeignKey("pilot_contracts.id"), index=True)
    invoice_upload_id: Mapped[str] = mapped_column(ForeignKey("pilot_uploads.id"))
    billing_period_start: Mapped[datetime] = mapped_column(DateTime)
    billing_period_end: Mapped[datetime] = mapped_column(DateTime)
    submitted_at: Mapped[datetime] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime)


class PilotRawRecordRow(Base):
    __tablename__ = "pilot_raw_records"
    __table_args__ = (UniqueConstraint("upload_id", "row_number", name="uq_pilot_raw_upload_row"),)

    id: Mapped[str] = mapped_column(String, primary_key=True)
    upload_id: Mapped[str] = mapped_column(ForeignKey("pilot_uploads.id"), index=True)
    invoice_id: Mapped[str | None] = mapped_column(
        ForeignKey("pilot_invoices.id"), nullable=True, index=True
    )
    row_number: Mapped[int] = mapped_column(Integer)
    source_record_id: Mapped[str] = mapped_column(String, index=True)
    record_type: Mapped[str] = mapped_column(String, index=True)
    source_system: Mapped[str] = mapped_column(String, index=True)
    occurred_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    received_at: Mapped[datetime] = mapped_column(DateTime)
    raw_payload: Mapped[dict] = mapped_column(JSON)
    normalized_payload: Mapped[dict] = mapped_column(JSON)
    payload_hash: Mapped[str] = mapped_column(String, index=True)
    parser_version: Mapped[str] = mapped_column(String)
    mapping_version: Mapped[str] = mapped_column(String)
    normalization_warnings: Mapped[list] = mapped_column(JSON, default=list)


class PilotClaimRow(Base):
    __tablename__ = "pilot_claims"
    __table_args__ = (
        UniqueConstraint("invoice_id", "external_outcome_id", name="uq_pilot_invoice_outcome"),
        UniqueConstraint("invoice_id", "vendor_claim_id", name="uq_pilot_invoice_vendor_claim"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    invoice_id: Mapped[str] = mapped_column(ForeignKey("pilot_invoices.id"), index=True)
    raw_record_id: Mapped[str] = mapped_column(ForeignKey("pilot_raw_records.id"), index=True)
    external_outcome_id: Mapped[str] = mapped_column(String, index=True)
    vendor_claim_id: Mapped[str] = mapped_column(String, index=True)
    external_conversation_id: Mapped[str] = mapped_column(String, index=True)
    agent_version: Mapped[str] = mapped_column(String)
    customer_id: Mapped[str] = mapped_column(String, index=True)
    intent: Mapped[str] = mapped_column(String, index=True)
    vendor_claim: Mapped[str] = mapped_column(String)
    closed_at: Mapped[datetime] = mapped_column(DateTime)
    expected_action: Mapped[str] = mapped_column(String)
    account_id: Mapped[str] = mapped_column(String)
    billed_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))


class PilotEventRow(Base):
    __tablename__ = "pilot_events"
    __table_args__ = (UniqueConstraint("invoice_id", "dedupe_key", name="uq_pilot_invoice_event"),)

    id: Mapped[str] = mapped_column(String, primary_key=True)
    invoice_id: Mapped[str] = mapped_column(ForeignKey("pilot_invoices.id"), index=True)
    upload_id: Mapped[str] = mapped_column(ForeignKey("pilot_uploads.id"), index=True)
    raw_record_id: Mapped[str] = mapped_column(ForeignKey("pilot_raw_records.id"), index=True)
    source_system: Mapped[str] = mapped_column(String, index=True)
    source_record_id: Mapped[str] = mapped_column(String, index=True)
    dedupe_key: Mapped[str] = mapped_column(String)
    event_type: Mapped[str] = mapped_column(String, index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime)
    customer_id: Mapped[str] = mapped_column(String, index=True)
    claimed_outcome_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    matched_claim_id: Mapped[str | None] = mapped_column(
        ForeignKey("pilot_claims.id"), nullable=True, index=True
    )
    values: Mapped[dict] = mapped_column(JSON)
    ingested_at: Mapped[datetime] = mapped_column(DateTime)
    match_status: Mapped[str] = mapped_column(String, default="pending", index=True)
    match_method: Mapped[str] = mapped_column(String, default="pending")
    match_confidence: Mapped[Decimal] = mapped_column(Numeric(6, 4), default=Decimal("0.0000"))
    match_reason: Mapped[str] = mapped_column(Text, default="")
    payload_hash: Mapped[str] = mapped_column(String)
    parser_version: Mapped[str] = mapped_column(String)
    mapping_version: Mapped[str] = mapped_column(String)


class PilotIdentityMappingRow(Base):
    __tablename__ = "pilot_identity_mappings"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    invoice_id: Mapped[str] = mapped_column(ForeignKey("pilot_invoices.id"), index=True)
    upload_id: Mapped[str] = mapped_column(ForeignKey("pilot_uploads.id"), index=True)
    conversation_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    customer_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    account_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    outcome_id: Mapped[str] = mapped_column(String, index=True)
    mapping_version: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime)


class PilotManualMatchRow(Base):
    __tablename__ = "pilot_manual_matches"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    invoice_id: Mapped[str] = mapped_column(ForeignKey("pilot_invoices.id"), index=True)
    event_id: Mapped[str] = mapped_column(ForeignKey("pilot_events.id"), index=True)
    claim_id: Mapped[str] = mapped_column(ForeignKey("pilot_claims.id"), index=True)
    confirmed_by: Mapped[str] = mapped_column(String)
    confirmed_at: Mapped[datetime] = mapped_column(DateTime)
    rationale: Mapped[str] = mapped_column(Text)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class PilotReconciliationRunRow(Base):
    __tablename__ = "pilot_reconciliation_runs"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    invoice_id: Mapped[str] = mapped_column(ForeignKey("pilot_invoices.id"), index=True)
    compilation_id: Mapped[str] = mapped_column(
        ForeignKey("pilot_rule_compilations.id"), index=True
    )
    run_number: Mapped[int] = mapped_column(Integer)
    started_at: Mapped[datetime] = mapped_column(DateTime)
    completed_at: Mapped[datetime] = mapped_column(DateTime)
    engine_version: Mapped[str] = mapped_column(String)
    rule_program_version: Mapped[int] = mapped_column(Integer)
    normalizer_version: Mapped[str] = mapped_column(String)
    matching_version: Mapped[str] = mapped_column(String)
    claimed_outcomes: Mapped[int] = mapped_column(Integer)
    payable_outcomes: Mapped[int] = mapped_column(Integer)
    disputed_outcomes: Mapped[int] = mapped_column(Integer)
    needs_review_outcomes: Mapped[int] = mapped_column(Integer)
    submitted_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    confirmed_payable_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    recommended_deduction: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    needs_review_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    supersedes_run_id: Mapped[str | None] = mapped_column(String, nullable=True)


class PilotDeterminationRow(Base):
    __tablename__ = "pilot_determinations"
    __table_args__ = (UniqueConstraint("run_id", "claim_id", name="uq_pilot_run_claim"),)

    id: Mapped[str] = mapped_column(String, primary_key=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("pilot_reconciliation_runs.id"), index=True)
    claim_id: Mapped[str] = mapped_column(ForeignKey("pilot_claims.id"), index=True)
    external_outcome_id: Mapped[str] = mapped_column(String, index=True)
    rule_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    status: Mapped[str] = mapped_column(String, index=True)
    reason: Mapped[str] = mapped_column(Text)
    billed_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    confirmed_payable_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    confirmed_disputed_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    needs_review_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    duplicate_winner_outcome_id: Mapped[str | None] = mapped_column(String, nullable=True)
    evaluated_at: Mapped[datetime] = mapped_column(DateTime)
    engine_version: Mapped[str] = mapped_column(String)
    rule_program_version: Mapped[int] = mapped_column(Integer)
    normalizer_version: Mapped[str] = mapped_column(String)
    matching_version: Mapped[str] = mapped_column(String)


class PilotCustomerReviewRow(Base):
    __tablename__ = "pilot_customer_reviews"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("pilot_reconciliation_runs.id"), index=True)
    reviewed_by: Mapped[str] = mapped_column(String)
    reviewed_at: Mapped[datetime] = mapped_column(DateTime)
    claims_sampled: Mapped[int] = mapped_column(Integer, default=0)
    confirmed_disputes: Mapped[int] = mapped_column(Integer, default=0)
    rejected_disputes: Mapped[int] = mapped_column(Integer, default=0)
    missing_disputes: Mapped[int] = mapped_column(Integer, default=0)
    estimated_overpayment_prevented: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), default=Decimal("0.00")
    )
    estimated_hours_saved: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0.00"))
    would_use_next_month: Mapped[bool] = mapped_column(Boolean, default=False)
    willingness_to_pay: Mapped[str] = mapped_column(String, default="")
    permission_to_quote: Mapped[bool] = mapped_column(Boolean, default=False)
    notes: Mapped[str] = mapped_column(Text, default="")


class PilotEvidenceReferenceRow(Base):
    __tablename__ = "pilot_evidence_references"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    determination_id: Mapped[str] = mapped_column(ForeignKey("pilot_determinations.id"), index=True)
    event_id: Mapped[str] = mapped_column(ForeignKey("pilot_events.id"), index=True)
    purpose: Mapped[str] = mapped_column(String)
