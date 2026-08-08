"""Persistent finance-product entities.

These tables intentionally reference the immutable pilot/kernel records instead of
copying their logic.  Human review and approval are overlays: they never mutate a
machine determination or an approved Agreement IR version.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
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


class ProductOrganizationRow(Base):
    __tablename__ = "product_organizations"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String)
    currency: Mapped[str] = mapped_column(String, default="USD")
    timezone: Mapped[str] = mapped_column(String, default="UTC")
    created_at: Mapped[datetime] = mapped_column(DateTime)
    updated_at: Mapped[datetime] = mapped_column(DateTime)


class ProductVendorRow(Base):
    __tablename__ = "product_vendors"
    __table_args__ = (UniqueConstraint("normalized_name", name="uq_product_vendor_name"),)

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String)
    normalized_name: Mapped[str] = mapped_column(String, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime)


class ProductVendorEngagementRow(Base):
    __tablename__ = "product_vendor_engagements"
    __table_args__ = (
        UniqueConstraint("organization_id", "vendor_id", name="uq_product_org_vendor"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    organization_id: Mapped[str] = mapped_column(ForeignKey("product_organizations.id"), index=True)
    vendor_id: Mapped[str] = mapped_column(ForeignKey("product_vendors.id"), index=True)
    display_name: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, default="active", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime)
    updated_at: Mapped[datetime] = mapped_column(DateTime)


class ProductEngagementContractRow(Base):
    __tablename__ = "product_engagement_contracts"
    __table_args__ = (UniqueConstraint("contract_id", name="uq_product_contract_link"),)

    id: Mapped[str] = mapped_column(String, primary_key=True)
    engagement_id: Mapped[str] = mapped_column(
        ForeignKey("product_vendor_engagements.id"), index=True
    )
    contract_id: Mapped[str] = mapped_column(ForeignKey("pilot_contracts.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime)


class ProductEngagementInvoiceRow(Base):
    __tablename__ = "product_engagement_invoices"
    __table_args__ = (UniqueConstraint("invoice_id", name="uq_product_invoice_link"),)

    id: Mapped[str] = mapped_column(String, primary_key=True)
    engagement_id: Mapped[str] = mapped_column(
        ForeignKey("product_vendor_engagements.id"), index=True
    )
    invoice_id: Mapped[str] = mapped_column(ForeignKey("pilot_invoices.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime)


class ProductReviewCaseRow(Base):
    __tablename__ = "product_review_cases"
    __table_args__ = (UniqueConstraint("determination_id", name="uq_product_review_determination"),)

    id: Mapped[str] = mapped_column(String, primary_key=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("pilot_reconciliation_runs.id"), index=True)
    determination_id: Mapped[str] = mapped_column(ForeignKey("pilot_determinations.id"), index=True)
    external_outcome_id: Mapped[str] = mapped_column(String, index=True)
    reason_code: Mapped[str] = mapped_column(String, index=True)
    reason: Mapped[str] = mapped_column(Text)
    exposure_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    priority: Mapped[str] = mapped_column(String, default="normal", index=True)
    status: Mapped[str] = mapped_column(String, default="open", index=True)
    assigned_to: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime)
    updated_at: Mapped[datetime] = mapped_column(DateTime)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class ProductReviewDecisionRow(Base):
    __tablename__ = "product_review_decisions"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    review_case_id: Mapped[str] = mapped_column(ForeignKey("product_review_cases.id"), index=True)
    decision: Mapped[str] = mapped_column(String, index=True)
    rationale: Mapped[str] = mapped_column(Text)
    decided_by: Mapped[str] = mapped_column(String)
    decided_at: Mapped[datetime] = mapped_column(DateTime)
    sequence: Mapped[int] = mapped_column(Integer)


class ProductReconciliationStatementRow(Base):
    __tablename__ = "product_reconciliation_statements"
    __table_args__ = (UniqueConstraint("run_id", name="uq_product_statement_run"),)

    id: Mapped[str] = mapped_column(String, primary_key=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("pilot_reconciliation_runs.id"), index=True)
    submitted_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    machine_payable_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    machine_disputed_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    review_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    review_resolved_payable_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    review_resolved_disputed_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    open_review_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    recommended_final_payable_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    recommended_final_disputed_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    status: Mapped[str] = mapped_column(String, default="draft", index=True)
    calculation_hash: Mapped[str] = mapped_column(String, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime)
    updated_at: Mapped[datetime] = mapped_column(DateTime)


class ProductApprovalRow(Base):
    __tablename__ = "product_approvals"
    __table_args__ = (UniqueConstraint("run_id", name="uq_product_approval_run"),)

    id: Mapped[str] = mapped_column(String, primary_key=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("pilot_reconciliation_runs.id"), index=True)
    statement_id: Mapped[str] = mapped_column(
        ForeignKey("product_reconciliation_statements.id"), index=True
    )
    approved_payable_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    approved_disputed_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    approved_by: Mapped[str] = mapped_column(String)
    approved_at: Mapped[datetime] = mapped_column(DateTime)
    calculation_hash: Mapped[str] = mapped_column(String, index=True)
    note: Mapped[str] = mapped_column(Text, default="")


class ProductDisputeCaseRow(Base):
    __tablename__ = "product_dispute_cases"
    __table_args__ = (UniqueConstraint("case_number", name="uq_product_dispute_number"),)

    id: Mapped[str] = mapped_column(String, primary_key=True)
    case_number: Mapped[str] = mapped_column(String, index=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("pilot_reconciliation_runs.id"), index=True)
    approval_id: Mapped[str] = mapped_column(ForeignKey("product_approvals.id"), index=True)
    status: Mapped[str] = mapped_column(String, default="draft", index=True)
    subject: Mapped[str] = mapped_column(String)
    disputed_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    item_count: Mapped[int] = mapped_column(Integer)
    vendor_response: Mapped[str] = mapped_column(Text, default="")
    vendor_response_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_by: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime)
    updated_at: Mapped[datetime] = mapped_column(DateTime)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class ProductDisputeItemRow(Base):
    __tablename__ = "product_dispute_items"
    __table_args__ = (
        UniqueConstraint("dispute_case_id", "determination_id", name="uq_product_dispute_item"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    dispute_case_id: Mapped[str] = mapped_column(ForeignKey("product_dispute_cases.id"), index=True)
    determination_id: Mapped[str] = mapped_column(ForeignKey("pilot_determinations.id"), index=True)
    external_outcome_id: Mapped[str] = mapped_column(String, index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    reason_code: Mapped[str] = mapped_column(String, index=True)
    reason: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String, index=True)
    accepted_by_vendor: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
