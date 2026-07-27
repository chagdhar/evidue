from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ContractCompileRequest(StrictModel):
    contract_text: str = Field(min_length=50, max_length=50_000)
    source_document: str = Field(
        default="Acme-Nova-Outcome-Pricing-Order-Form.pdf",
        min_length=3,
        max_length=255,
    )


class HealthResponse(StrictModel):
    status: str


class DemoStatusResponse(StrictModel):
    seeded: bool
    reconciled: bool
    claimed_outcomes: int
    billing_period: str
    scenario_id: str
    scenario_name: str
    scenario_description: str
    demo_outcome_id: str


class DemoScenarioResponse(StrictModel):
    id: str
    name: str
    description: str
    demo_outcome_id: str


class CategorySummary(StrictModel):
    label: str
    count: int
    amount: str


class ReconciliationSummary(StrictModel):
    reconciliation_id: str
    status: str
    scenario_id: str
    scenario_name: str
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
    vendor_claim_id: str
    agent_version: str
    claim_provenance: dict[str, Any] | None
    conversation: dict[str, Any]
    contract_clause: str | None
    rule: dict[str, Any] | None
    evidence: list[dict[str, Any]]
    computed_timeline_markers: list[dict[str, Any]]
    duplicate_winner_outcome_id: str | None
    evaluated_at: str
    engine_version: str


class DataSourceSummary(StrictModel):
    id: str
    name: str
    category: str
    owner: str
    authority: str
    collection_method: str
    production_method: str
    source_format: str
    schedule: str
    status: str
    description: str
    fields: list[str]
    raw_records: int
    normalized_records: int
    rejected_records: int
    matched_records: int
    secondary_matches: int
    review_records: int
    last_synced_at: str
    trust_boundary: str


class DataReadinessTotals(StrictModel):
    claimed_outcomes: int
    raw_records: int
    sampled_raw_records: int
    normalized_events: int
    direct_matches: int
    secondary_matches: int
    review_records: int
    claim_coverage_percent: float
    contract_rules_approved: int


class DataReadinessResponse(StrictModel):
    status: str
    synthetic_disclosure: str
    collection_note: str
    totals: DataReadinessTotals
    sources: list[DataSourceSummary]
    pipeline: list[dict[str, Any]]
    onboarding: list[dict[str, Any]]


class RawRecordSample(StrictModel):
    id: str
    connector_id: str
    source_record_id: str
    record_type: str
    occurred_at: str | None
    received_at: str
    payload: dict[str, Any]
    normalized_payload: dict[str, Any]
    payload_hash: str
    schema_version: str
    matched_outcome_id: str | None
    match_status: str | None
    match_method: str | None
    match_confidence: str | None
    match_reason: str | None


class DataSourceSamplesResponse(StrictModel):
    source: DataSourceSummary
    records: list[RawRecordSample]
    sample_note: str
