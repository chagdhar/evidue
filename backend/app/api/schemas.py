from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


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


class PublicConfigResponse(StrictModel):
    beta_form_configured: bool
    beta_form_url: str | None
    contact_form_configured: bool


class ContactSubmissionRequest(StrictModel):
    name: str = Field(min_length=2, max_length=100)
    email: str = Field(min_length=5, max_length=254)
    company: str = Field(min_length=2, max_length=120)
    discussion_type: Literal["Product feedback", "Invoice review", "Partnership", "Other"]
    message: str = Field(min_length=10, max_length=4_000)
    confirmed_no_confidential_data: Literal[True]
    attribution_source: Literal[
        "hacker_news", "indie_hackers", "yc_demo", "direct_outreach", "unknown"
    ]
    campaign: Literal["railway_beta"]
    demo_version: Literal["hn_demo"]
    submission_id: UUID
    browser_session_id: UUID
    form_started_at: datetime
    website: str = Field(default="", max_length=0)

    @field_validator(
        "name",
        "email",
        "company",
        "message",
        mode="before",
    )
    @classmethod
    def strip_text(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @field_validator("email")
    @classmethod
    def validate_email_shape(cls, value: str) -> str:
        local, separator, domain = value.rpartition("@")
        if not separator or not local or "." not in domain or domain.startswith("."):
            raise ValueError("Enter a valid email address")
        return value


class ContactSubmissionResponse(StrictModel):
    accepted: bool


class RecordedProposalValidationResponse(StrictModel):
    valid: bool
    contract_id: str
    source_hash: str
    prompt_hash: str
    rule_count: int
    rule_ids: list[str]
    compiler_version: str
    live_model_call: bool
    duration_ms: int


class PublicOutcomeEvaluationResponse(StrictModel):
    outcome_id: str
    status: str
    rule_id: str | None
    reason: str
    confirmed_payable_amount: str
    confirmed_disputed_amount: str
    needs_review_amount: str
    evidence_ids: list[str]
    engine_version: str
    compilation_id: str
    program_version: int
    source_hash: str
    canonical: dict[str, Any] | None
    duration_ms: int


class RepresentativeFinding(StrictModel):
    rule_id: str
    outcome_id: str


class PublicReconciliationSampleResponse(StrictModel):
    sample_size: int
    payable_outcomes: int
    disputed_outcomes: int
    needs_review_outcomes: int
    submitted_amount: str
    confirmed_payable_amount: str
    recommended_deduction: str
    representative_findings: list[RepresentativeFinding]
    sampling_method: str
    compilation_id: str
    program_version: int
    source_hash: str
    engine_version: str
    duration_ms: int


class DemoStatusResponse(StrictModel):
    public_demo: bool
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
