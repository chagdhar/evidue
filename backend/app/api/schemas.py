from typing import Any

from pydantic import BaseModel, ConfigDict


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class HealthResponse(StrictModel):
    status: str


class DemoStatusResponse(StrictModel):
    seeded: bool
    reconciled: bool
    claimed_outcomes: int
    billing_period: str


class CategorySummary(StrictModel):
    label: str
    count: int
    amount: str


class ReconciliationSummary(StrictModel):
    reconciliation_id: str
    status: str
    claimed_outcomes: int
    payable_outcomes: int
    disputed_outcomes: int
    needs_review_outcomes: int
    submitted_amount: str
    confirmed_payable_amount: str
    recommended_deduction: str
    needs_review_amount: str
    price_per_outcome: str
    categories: dict[str, CategorySummary]
    synthetic_disclosure: str


class OutcomeListItem(StrictModel):
    outcome_id: str
    customer_id: str
    intent: str
    vendor_claim: str
    status: str
    reason: str
    rule_id: str | None
    billed_amount: str
    confirmed_payable_amount: str
    confirmed_disputed_amount: str
    needs_review_amount: str
    closed_at: str


class OutcomePage(StrictModel):
    total: int
    offset: int
    limit: int
    items: list[OutcomeListItem]


class OutcomeDetail(OutcomeListItem):
    account_id: str
    expected_action: str
    conversation: dict[str, Any]
    contract_clause: str | None
    rule: dict[str, Any] | None
    evidence: list[dict[str, Any]]
    computed_timeline_markers: list[dict[str, Any]]
    duplicate_winner_outcome_id: str | None
    evaluated_at: str
    engine_version: str
