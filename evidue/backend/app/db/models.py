from datetime import datetime
from decimal import Decimal

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class DemoStateRow(Base):
    __tablename__ = "demo_state"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    seeded: Mapped[bool] = mapped_column(Boolean, default=False)
    reconciled: Mapped[bool] = mapped_column(Boolean, default=False)
    scenario_id: Mapped[str] = mapped_column(String, default="headline")
    active_compilation_id: Mapped[str | None] = mapped_column(String, nullable=True)


class ConnectorRow(Base):
    __tablename__ = "connectors"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String)
    category: Mapped[str] = mapped_column(String)
    owner: Mapped[str] = mapped_column(String)
    authority: Mapped[str] = mapped_column(String)
    collection_method: Mapped[str] = mapped_column(String)
    production_method: Mapped[str] = mapped_column(String)
    source_format: Mapped[str] = mapped_column(String)
    schedule: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String)
    description: Mapped[str] = mapped_column(Text)
    fields: Mapped[list] = mapped_column(JSON)
    records_received: Mapped[int] = mapped_column(Integer)
    records_normalized: Mapped[int] = mapped_column(Integer)
    records_rejected: Mapped[int] = mapped_column(Integer)
    last_synced_at: Mapped[datetime] = mapped_column(DateTime)
    trust_boundary: Mapped[str] = mapped_column(Text)


class RawRecordRow(Base):
    __tablename__ = "raw_records"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    connector_id: Mapped[str] = mapped_column(ForeignKey("connectors.id"), index=True)
    source_record_id: Mapped[str] = mapped_column(String, index=True)
    record_type: Mapped[str] = mapped_column(String, index=True)
    occurred_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    received_at: Mapped[datetime] = mapped_column(DateTime)
    payload: Mapped[dict] = mapped_column(JSON)
    normalized_payload: Mapped[dict] = mapped_column(JSON)
    payload_hash: Mapped[str] = mapped_column(String)
    schema_version: Mapped[str] = mapped_column(String)
    sampled: Mapped[bool] = mapped_column(Boolean, default=True)


class EvidenceMatchRow(Base):
    __tablename__ = "evidence_matches"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    raw_record_id: Mapped[str] = mapped_column(ForeignKey("raw_records.id"), index=True)
    outcome_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    status: Mapped[str] = mapped_column(String, index=True)
    match_method: Mapped[str] = mapped_column(String)
    confidence: Mapped[Decimal] = mapped_column(Numeric(6, 4))
    reason: Mapped[str] = mapped_column(Text)
    matched_at: Mapped[datetime] = mapped_column(DateTime)


class IngestionBatchRow(Base):
    __tablename__ = "ingestion_batches"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    scenario_id: Mapped[str] = mapped_column(String, index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime)
    completed_at: Mapped[datetime] = mapped_column(DateTime)
    claims_received: Mapped[int] = mapped_column(Integer)
    direct_matches: Mapped[int] = mapped_column(Integer)
    secondary_matches: Mapped[int] = mapped_column(Integer)
    unresolved_matches: Mapped[int] = mapped_column(Integer)
    source_records_received: Mapped[int] = mapped_column(Integer)
    source_records_normalized: Mapped[int] = mapped_column(Integer)
    source_records_rejected: Mapped[int] = mapped_column(Integer)
    contract_rules_approved: Mapped[int] = mapped_column(Integer)


class ContractRow(Base):
    __tablename__ = "contracts"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    customer: Mapped[str] = mapped_column(String)
    vendor: Mapped[str] = mapped_column(String)
    period_start: Mapped[datetime] = mapped_column(DateTime)
    period_end: Mapped[datetime] = mapped_column(DateTime)
    price_per_outcome: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    clauses: Mapped[list["ContractClauseRow"]] = relationship(
        cascade="all, delete-orphan", back_populates="contract"
    )


class ContractRuleRow(Base):
    __tablename__ = "contract_rules"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    title: Mapped[str] = mapped_column(String)
    description: Mapped[str] = mapped_column(Text)
    clause_text: Mapped[str] = mapped_column(Text)
    operation: Mapped[str] = mapped_column(String)
    parameters: Mapped[dict] = mapped_column(JSON)
    evidence_required: Mapped[list] = mapped_column(JSON)
    priority: Mapped[int] = mapped_column(Integer)
    consequence: Mapped[str] = mapped_column(String)
    compilation_id: Mapped[str] = mapped_column(String, index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)


class RuleCompilationRow(Base):
    __tablename__ = "rule_compilations"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    contract_id: Mapped[str] = mapped_column(String, index=True)
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


class ContractClauseRow(Base):
    __tablename__ = "contract_clauses"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    contract_id: Mapped[str] = mapped_column(ForeignKey("contracts.id"))
    rule_id: Mapped[str] = mapped_column(ForeignKey("contract_rules.id"))
    text: Mapped[str] = mapped_column(Text)
    contract: Mapped[ContractRow] = relationship(back_populates="clauses")
    rule: Mapped[ContractRuleRow] = relationship()


class InvoiceRow(Base):
    __tablename__ = "invoices"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    contract_id: Mapped[str] = mapped_column(ForeignKey("contracts.id"))
    billing_period_start: Mapped[datetime] = mapped_column(DateTime)
    billing_period_end: Mapped[datetime] = mapped_column(DateTime)
    submitted_at: Mapped[datetime] = mapped_column(DateTime)


class OutcomeClaimRow(Base):
    __tablename__ = "outcome_claims"
    outcome_id: Mapped[str] = mapped_column(String, primary_key=True)
    vendor_claim_id: Mapped[str] = mapped_column(String, unique=True, index=True)
    external_conversation_id: Mapped[str] = mapped_column(String, index=True)
    agent_version: Mapped[str] = mapped_column(String)
    raw_record_id: Mapped[str | None] = mapped_column(
        ForeignKey("raw_records.id"), nullable=True, index=True
    )
    invoice_id: Mapped[str] = mapped_column(ForeignKey("invoices.id"), index=True)
    customer_id: Mapped[str] = mapped_column(String, index=True)
    intent: Mapped[str] = mapped_column(String, index=True)
    vendor_claim: Mapped[str] = mapped_column(String)
    closed_at: Mapped[datetime] = mapped_column(DateTime)
    expected_action: Mapped[str] = mapped_column(String)
    account_id: Mapped[str] = mapped_column(String)
    billed_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))


class ConversationRow(Base):
    __tablename__ = "conversations"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    outcome_id: Mapped[str] = mapped_column(ForeignKey("outcome_claims.outcome_id"), unique=True)
    customer_id: Mapped[str] = mapped_column(String)
    intent: Mapped[str] = mapped_column(String)
    closed_at: Mapped[datetime] = mapped_column(DateTime)


class OperationalEventRow(Base):
    __tablename__ = "operational_events"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    source_system: Mapped[str] = mapped_column(String, index=True)
    source_record_id: Mapped[str] = mapped_column(String, unique=True)
    event_type: Mapped[str] = mapped_column(String, index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime)
    customer_id: Mapped[str] = mapped_column(String, index=True)
    outcome_id: Mapped[str | None] = mapped_column(
        ForeignKey("outcome_claims.outcome_id"), index=True
    )
    values: Mapped[dict] = mapped_column(JSON)
    ingested_at: Mapped[datetime] = mapped_column(DateTime)
    connector_id: Mapped[str | None] = mapped_column(
        ForeignKey("connectors.id"), nullable=True, index=True
    )
    raw_record_id: Mapped[str | None] = mapped_column(
        ForeignKey("raw_records.id"), nullable=True, index=True
    )
    match_method: Mapped[str] = mapped_column(String, default="direct_outcome_id")
    match_confidence: Mapped[Decimal] = mapped_column(Numeric(6, 4), default=Decimal("1.0000"))
    payload_hash: Mapped[str] = mapped_column(String, default="")
    schema_version: Mapped[str] = mapped_column(String, default="1.0")
    source_locator: Mapped[str] = mapped_column(String, default="")
    external_keys: Mapped[dict] = mapped_column(JSON, default=dict)


class ReconciliationRow(Base):
    __tablename__ = "reconciliations"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    invoice_id: Mapped[str] = mapped_column(ForeignKey("invoices.id"))
    evaluated_at: Mapped[datetime] = mapped_column(DateTime)
    engine_version: Mapped[str] = mapped_column(String)


class OutcomeDeterminationRow(Base):
    __tablename__ = "outcome_determinations"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    reconciliation_id: Mapped[str] = mapped_column(ForeignKey("reconciliations.id"))
    outcome_id: Mapped[str] = mapped_column(
        ForeignKey("outcome_claims.outcome_id"), unique=True, index=True
    )
    rule_id: Mapped[str | None] = mapped_column(
        ForeignKey("contract_rules.id"), nullable=True, index=True
    )
    status: Mapped[str] = mapped_column(String, index=True)
    reason: Mapped[str] = mapped_column(Text)
    billed_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    confirmed_payable_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    confirmed_disputed_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    needs_review_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    duplicate_winner_outcome_id: Mapped[str | None] = mapped_column(
        ForeignKey("outcome_claims.outcome_id"), nullable=True
    )
    evaluated_at: Mapped[datetime] = mapped_column(DateTime)
    engine_version: Mapped[str] = mapped_column(String)


class EvidenceReferenceRow(Base):
    __tablename__ = "evidence_references"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    determination_id: Mapped[int] = mapped_column(
        ForeignKey("outcome_determinations.id"), index=True
    )
    event_id: Mapped[str] = mapped_column(ForeignKey("operational_events.id"))
    purpose: Mapped[str] = mapped_column(String)


# ---------------------------------------------------------------------------
# Product-path models (pilot upload, matching, review)
# ---------------------------------------------------------------------------


class PilotStateRow(Base):
    """Singleton row tracking whether the pilot path has been initialized."""

    __tablename__ = "pilot_state"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    initialized: Mapped[bool] = mapped_column(Boolean, default=False)
    invoice_uploaded: Mapped[bool] = mapped_column(Boolean, default=False)
    evidence_uploaded: Mapped[bool] = mapped_column(Boolean, default=False)
    matching_complete: Mapped[bool] = mapped_column(Boolean, default=False)
    reconciled: Mapped[bool] = mapped_column(Boolean, default=False)
    active_invoice_id: Mapped[str | None] = mapped_column(String, nullable=True)
    active_contract_id: Mapped[str | None] = mapped_column(String, nullable=True)


class UploadRow(Base):
    __tablename__ = "uploads"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    upload_type: Mapped[str] = mapped_column(String, index=True)
    filename: Mapped[str] = mapped_column(String)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String, index=True)
    rows_parsed: Mapped[int] = mapped_column(Integer, default=0)
    rows_accepted: Mapped[int] = mapped_column(Integer, default=0)
    rows_rejected: Mapped[int] = mapped_column(Integer, default=0)
    error_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_type: Mapped[str | None] = mapped_column(String, nullable=True)


class UploadRejectionRow(Base):
    __tablename__ = "upload_rejections"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    upload_id: Mapped[str] = mapped_column(ForeignKey("uploads.id"), index=True)
    row_number: Mapped[int] = mapped_column(Integer)
    reason: Mapped[str] = mapped_column(Text)
    raw_data: Mapped[dict] = mapped_column(JSON)


class ManualMatchRow(Base):
    __tablename__ = "manual_matches"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_id: Mapped[str] = mapped_column(ForeignKey("operational_events.id"), index=True)
    outcome_id: Mapped[str] = mapped_column(String, index=True)
    confirmed_by: Mapped[str] = mapped_column(String)
    confirmed_at: Mapped[datetime] = mapped_column(DateTime)
    rationale: Mapped[str] = mapped_column(Text)
