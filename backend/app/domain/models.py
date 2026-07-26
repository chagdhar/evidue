from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Literal

Money = Decimal
DeterminationStatus = Literal["payable", "disputed", "needs_review"]
PRICE = Decimal("1.50")


@dataclass(frozen=True)
class Contract:
    id: str
    customer: str
    vendor: str
    period_start: datetime
    period_end: datetime
    price_per_outcome: Money


@dataclass(frozen=True)
class ContractClause:
    id: str
    contract_id: str
    text: str
    rule_id: str


@dataclass(frozen=True)
class ContractRule:
    id: str
    title: str
    description: str
    parameters: dict[str, str]
    evidence_required: tuple[str, ...]


@dataclass(frozen=True)
class Invoice:
    id: str
    contract_id: str
    billing_period_start: datetime
    billing_period_end: datetime
    submitted_at: datetime


@dataclass(frozen=True)
class OutcomeClaim:
    outcome_id: str
    invoice_id: str
    customer_id: str
    intent: str
    vendor_claim: str
    closed_at: datetime
    expected_action: str
    account_id: str
    billed_amount: Money = PRICE


@dataclass(frozen=True)
class Conversation:
    id: str
    customer_id: str
    intent: str
    closed_at: datetime
    outcome_id: str


@dataclass(frozen=True)
class OperationalEvent:
    id: str
    source_system: str
    source_record_id: str
    event_type: str
    timestamp: datetime
    customer_id: str
    outcome_id: str | None
    values: dict[str, str]
    ingested_at: datetime


@dataclass(frozen=True)
class EvidenceReference:
    event_id: str
    purpose: str


@dataclass(frozen=True)
class OutcomeDetermination:
    claim: OutcomeClaim
    status: DeterminationStatus
    reason: str
    rule_id: str | None
    evidence: tuple[EvidenceReference, ...]
    payable_amount: Money
    evaluated_at: datetime
    engine_version: str = "2026.06.1"


@dataclass(frozen=True)
class Reconciliation:
    id: str
    invoice_id: str
    evaluated_at: datetime
    engine_version: str


RULES = (
    ContractRule(
        "R1",
        "No same-intent recontact",
        "No same-intent customer contact within seven calendar days.",
        {"window_days": "7"},
        ("ai_closed", "customer_recontact"),
    ),
    ContractRule(
        "R2",
        "No human completion",
        "No human completion or material correction within 24 hours.",
        {"window_hours": "24"},
        ("ai_closed", "human_completion"),
    ),
    ContractRule(
        "R3",
        "Downstream action succeeds",
        "The promised downstream action succeeds within two hours.",
        {"window_hours": "2"},
        ("ai_closed", "downstream_succeeded"),
    ),
    ContractRule(
        "R4",
        "Single attribution",
        "Only one outcome is billable for a customer and intent in 24 hours.",
        {"window_hours": "24"},
        ("ai_closed", "duplicate_attribution"),
    ),
    ContractRule(
        "R5",
        "Account and action match",
        "Operational evidence matches the expected account and action.",
        {},
        ("ai_closed", "account_verified"),
    ),
    ContractRule(
        "R6",
        "Billing period",
        "The outcome closes inside the invoice billing period.",
        {"start": "2026-06-01", "end_exclusive": "2026-07-01"},
        ("ai_closed",),
    ),
    ContractRule(
        "R7",
        "Sufficient identifiers",
        "The claim can be associated with conversation and operational evidence.",
        {},
        ("ai_closed",),
    ),
)
