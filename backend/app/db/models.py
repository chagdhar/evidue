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
    parameters: Mapped[dict] = mapped_column(JSON)
    evidence_required: Mapped[list] = mapped_column(JSON)


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
