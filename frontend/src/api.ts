export type DemoStatus = {
  public_demo: boolean;
  seeded: boolean;
  reconciled: boolean;
  claimed_outcomes: number;
  billing_period: string;
  scenario_id: string;
  scenario_name: string;
  scenario_description: string;
  demo_outcome_id: string;
};

export type PublicConfig = {
  beta_form_configured: boolean;
  beta_form_url: string | null;
  contact_form_configured: boolean;
};

export type ContactSubmissionPayload = {
  name: string;
  email: string;
  company: string;
  discussion_type: string;
  message: string;
  confirmed_no_confidential_data: true;
  attribution_source: "hacker_news" | "yc_demo" | "direct_outreach" | "unknown";
  campaign: "railway_beta";
  demo_version: "hn_demo";
  submission_id: string;
  browser_session_id: string;
  form_started_at: string;
  website: string;
};

export type DemoScenario = {
  id: string;
  name: string;
  description: string;
  demo_outcome_id: string;
};

export type Rule = {
  id: string;
  title: string;
  description: string;
  parameters: Record<string, unknown>;
  evidence_required: string[];
  consequence: string;
  operation: string;
  priority: number;
  compilation_id?: string;
};

export type RuleCompilation = {
  id: string;
  contract_id: string;
  source_document: string;
  source_text: string;
  source_hash: string;
  prompt_hash: string;
  provider: string;
  model: string;
  compiler_version: string;
  status: "pending_approval" | "approved" | "superseded";
  version: number;
  live_model_call: boolean;
  created_at: string;
  approved_at: string | null;
  rules: Array<Rule & { clause_text: string }>;
  safety_boundary: string;
  fallback_reason?: string | null;
  validation: {
    schema_valid: boolean;
    allowlisted_operations: boolean;
    unique_rule_ids: boolean;
    unique_priorities: boolean;
    rule_count: number;
  };
};

export type Contract = {
  id: string;
  customer: string;
  vendor: string;
  period_start: string;
  period_end: string;
  price_per_outcome: string;
  clauses: Array<{ id: string; text: string; rule: Rule }>;
  evidence_sources: string[];
  contract_text: string;
  demo_contract_text: string;
  live_compilation_available: boolean;
  compilation: RuleCompilation;
  latest_compilation: RuleCompilation;
};

export type Invoice = {
  invoice_id: string;
  claimed_outcomes: number;
  submitted_amount: string;
  status: string;
  billing_period_start: string;
  billing_period_end: string;
};

export type Category = { label: string; count: number; amount: string };
export type Summary = {
  reconciliation_id: string;
  scenario_id: string;
  scenario_name: string;
  status: string;
  claimed_outcomes: number;
  payable_outcomes: number;
  disputed_outcomes: number;
  needs_review_outcomes: number;
  submitted_amount: string;
  confirmed_payable_amount: string;
  recommended_deduction: string;
  needs_review_amount: string;
  price_per_outcome: string;
  categories: Record<string, Category>;
  synthetic_disclosure: string;
};

export type Outcome = {
  outcome_id: string;
  customer_id: string;
  intent: string;
  vendor_claim: string;
  status: string;
  reason: string;
  rule_id: string | null;
  billed_amount: string;
  confirmed_payable_amount: string;
  confirmed_disputed_amount: string;
  needs_review_amount: string;
  closed_at: string;
};

export type EvidenceProvenance = {
  connector_id: string | null;
  connector_name: string | null;
  authority: string | null;
  collection_method: string | null;
  production_method: string | null;
  raw_record_id: string | null;
  raw_payload: Record<string, unknown> | null;
  payload_hash: string | null;
  schema_version: string | null;
  match_status: string | null;
  match_method: string | null;
  match_confidence: string | null;
  match_reason: string | null;
  received_at: string;
};

export type EvidenceEvent = {
  id: string;
  source_system: string;
  source_record_id: string;
  event_type: string;
  timestamp: string;
  customer_id: string;
  outcome_id: string;
  values: Record<string, string>;
  ingested_at: string;
  provenance: EvidenceProvenance;
};

export type OutcomeDetail = Outcome & {
  account_id: string;
  expected_action: string;
  vendor_claim_id: string;
  agent_version: string;
  claim_provenance: EvidenceProvenance | null;
  conversation: { id: string; intent: string; closed_at: string };
  contract_clause: string | null;
  rule: Rule | null;
  evidence: EvidenceEvent[];
  computed_timeline_markers: Array<{
    id: string;
    marker_type: string;
    timestamp: string;
    description: string;
  }>;
  duplicate_winner_outcome_id: string | null;
  evaluated_at: string;
  engine_version: string;
};

export type OutcomePage = {
  total: number;
  offset: number;
  limit: number;
  items: Outcome[];
};

export type RecordedProposalValidation = {
  valid: boolean;
  contract_id: string;
  source_hash: string;
  prompt_hash: string;
  rule_count: number;
  rule_ids: string[];
  compiler_version: string;
  live_model_call: boolean;
  duration_ms: number;
};

export type PublicOutcomeEvaluation = {
  outcome_id: string;
  status: string;
  rule_id: string | null;
  reason: string;
  confirmed_payable_amount: string;
  confirmed_disputed_amount: string;
  needs_review_amount: string;
  evidence_ids: string[];
  engine_version: string;
  compilation_id: string;
  program_version: number;
  source_hash: string;
  canonical: OutcomeDetail | null;
  duration_ms: number;
};

export type PublicReconciliationSample = {
  sample_size: number;
  payable_outcomes: number;
  disputed_outcomes: number;
  needs_review_outcomes: number;
  submitted_amount: string;
  confirmed_payable_amount: string;
  recommended_deduction: string;
  representative_findings: Array<{ rule_id: string; outcome_id: string }>;
  sampling_method: string;
  compilation_id: string;
  program_version: number;
  source_hash: string;
  engine_version: string;
  duration_ms: number;
};

export type DataSource = {
  id: string;
  name: string;
  category: string;
  owner: string;
  authority: string;
  collection_method: string;
  production_method: string;
  source_format: string;
  schedule: string;
  status: string;
  description: string;
  fields: string[];
  raw_records: number;
  normalized_records: number;
  rejected_records: number;
  matched_records: number;
  secondary_matches: number;
  review_records: number;
  last_synced_at: string;
  trust_boundary: string;
};

export type DataReadiness = {
  status: string;
  synthetic_disclosure: string;
  collection_note: string;
  totals: {
    claimed_outcomes: number;
    raw_records: number;
    sampled_raw_records: number;
    normalized_events: number;
    direct_matches: number;
    secondary_matches: number;
    review_records: number;
    claim_coverage_percent: number;
    contract_rules_approved: number;
  };
  sources: DataSource[];
  pipeline: Array<{ id: string; label: string; description: string }>;
  onboarding: Array<{ phase: string; label: string; description: string }>;
};

export type RawRecordSample = {
  id: string;
  connector_id: string;
  source_record_id: string;
  record_type: string;
  occurred_at: string | null;
  received_at: string;
  payload: Record<string, unknown>;
  normalized_payload: Record<string, unknown>;
  payload_hash: string;
  schema_version: string;
  matched_outcome_id: string | null;
  match_status: string | null;
  match_method: string | null;
  match_confidence: string | null;
  match_reason: string | null;
};

export type DataSourceSamples = {
  source: DataSource;
  records: RawRecordSample[];
  sample_note: string;
};

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`/api${path}`, options);
  if (!response.ok) {
    const body = await response.text();
    let message = body;
    try {
      const parsed = JSON.parse(body) as { detail?: string };
      message = parsed.detail || body;
    } catch {
      // Keep the plain-text response.
    }
    throw new Error(message || `Request failed (${response.status})`);
  }
  return response.json() as Promise<T>;
}

export const api = {
  publicConfig: () => request<PublicConfig>("/public-config"),
  createContactSubmission: (submission: ContactSubmissionPayload) =>
    request<{ accepted: boolean }>("/contact-submissions", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(submission),
    }),
  status: () => request<DemoStatus>("/demo/status"),
  scenarios: () => request<DemoScenario[]>("/demo/scenarios"),
  contract: () => request<Contract>("/contracts/current"),
  compileContract: (
    mode: "auto" | "live" | "recorded" = "auto",
    contractText?: string,
    sourceDocument = "Acme-Nova-Outcome-Pricing-Order-Form.pdf",
  ) =>
    request<RuleCompilation>(`/contracts/current/compile?mode=${mode}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: contractText === undefined
        ? undefined
        : JSON.stringify({ contract_text: contractText, source_document: sourceDocument }),
    }),
  compilations: () => request<RuleCompilation[]>("/contracts/current/compilations"),
  approveCompilation: (compilationId: string) =>
    request<RuleCompilation>(
      `/contracts/current/compilations/${encodeURIComponent(compilationId)}/approve`,
      { method: "POST" },
    ),
  dataReadiness: () => request<DataReadiness>("/data-readiness"),
  sourceSamples: (sourceId: string, outcomeId?: string, limit = 8) => {
    const query = new URLSearchParams({ limit: String(limit) });
    if (outcomeId) query.set("outcome_id", outcomeId);
    return request<DataSourceSamples>(`/data-sources/${sourceId}/samples?${query}`);
  },
  invoice: () => request<Invoice>("/invoices/current"),
  current: () => request<Summary>("/reconciliations/current"),
  reconcile: () => request<Summary>("/reconciliations", { method: "POST" }),
  validateRecordedProposal: () =>
    request<RecordedProposalValidation>("/public-demo/rules/validate", { method: "POST" }),
  evaluatePublicOutcome: (id: string) =>
    request<PublicOutcomeEvaluation>(`/public-demo/outcomes/${encodeURIComponent(id)}/evaluate`, {
      method: "POST",
    }),
  publicReconciliationSample: () =>
    request<PublicReconciliationSample>("/public-demo/reconciliations/sample", { method: "POST" }),
  reset: (scenarioId = "headline") =>
    request<DemoStatus>(
      `/demo/reset?scenario_id=${encodeURIComponent(scenarioId)}`,
      { method: "POST" },
    ),
  outcomes: (query: URLSearchParams) =>
    request<OutcomePage>(`/reconciliations/current/outcomes?${query}`),
  outcome: (id: string) =>
    request<OutcomeDetail>(`/reconciliations/current/outcomes/${id}`),
};
