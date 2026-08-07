const PILOT_TOKEN_KEY = "evidue.pilot.token";
const PILOT_ROOT = "/api/pilot";

export type CompilerDiagnostic = {
  code: string;
  severity: "info" | "warning" | "blocking";
  message: string;
  clause_text?: string | null;
  suggested_action?: string | null;
};

export type ClauseCoverage = {
  clause_id: string;
  clause_text: string;
  status: "compiled" | "needs_review" | "not_applicable";
  rule_ids: string[];
  explanation: string;
};

export type PilotRule = {
  id: string;
  title: string;
  description: string;
  clause_text: string;
  operation: string;
  parameters: Record<string, unknown>;
  evidence_required: string[];
  priority: number;
  consequence: "payable" | "disputed" | "needs_review";
};

export type PilotCompilation = {
  id: string;
  contract_id: string;
  source_document: string;
  source_hash: string;
  prompt_hash: string;
  provider: string;
  model: string;
  compiler_version: string;
  status: string;
  version: number;
  live_model_call: boolean;
  created_at: string;
  approved_at: string | null;
  rules: PilotRule[];
  diagnostics: CompilerDiagnostic[];
  clause_coverage: ClauseCoverage[];
  approval_ready: boolean;
  blocking_diagnostic_count: number;
  safety_boundary: string;
};

export type PilotContract = {
  id: string;
  customer: string;
  vendor: string;
  period_start: string;
  period_end: string;
  price_per_outcome: string;
  source_document: string;
  source_hash: string;
  active_compilation_id: string | null;
  agreement_bundle_id?: string | null;
  created_at: string;
  compilations: PilotCompilation[];
};

export type PilotUploadSummary = {
  id: string;
  type: string;
  filename: string;
  status: string;
  rows_accepted: number;
  rows_rejected: number;
  uploaded_at: string;
  error_summary?: string | null;
};

export type PilotStatus = {
  workspace_id?: string;
  initialized: boolean;
  active_contract_id: string | null;
  contract_approved: boolean;
  active_air_version_id?: string | null;
  active_invoice_id: string | null;
  claims: number;
  events: number;
  accepted_matches: number;
  suggested_matches: number;
  unresolved_events: number;
  accepted_match_rate: string;
  latest_reconciliation_id: string | null;
  latest_run_number: number | null;
  uploads: PilotUploadSummary[];
};

export type UploadResult = {
  upload_id: string;
  invoice_id?: string;
  claims_ingested?: number;
  events_ingested?: number;
  mappings_persisted?: number;
  rows_parsed?: number;
  rows_accepted?: number;
  rows_rejected?: number;
  rejections?: Array<{ row: number; reason: string }>;
  contract?: PilotContract;
  matching_summary?: MatchSummary;
};

export type MatchSummary = {
  invoice_id?: string;
  total_events: number;
  direct_matches: number;
  identity_map_matches: number;
  suggested_composite_matches: number;
  unresolved: number;
  policy?: string;
};

export type ReviewItem = {
  id: string;
  event_id?: string;
  source_record_id?: string;
  source_system?: string;
  event_type?: string;
  timestamp?: string;
  customer_id?: string;
  account_id?: string;
  outcome_id?: string | null;
  match_status?: string;
  match_method?: string | null;
  match_confidence?: string | number | null;
  match_reason?: string | null;
  [key: string]: unknown;
};

export type MatchCandidate = {
  claim_id: string;
  outcome_id?: string;
  customer_id?: string;
  account_id?: string;
  confidence?: string | number;
  method?: string;
  reason?: string;
  [key: string]: unknown;
};

export type Determination = {
  outcome_id: string;
  status: "payable" | "disputed" | "needs_review";
  rule_id: string | null;
  reason: string;
  billed_amount: string;
  confirmed_payable_amount: string;
  confirmed_disputed_amount: string;
  needs_review_amount: string;
  engine_version: string;
  rule_program_version: number;
  normalizer_version: string;
  matching_version: string;
  contract_clauses?: Array<{
    id: string;
    text: string;
    document_id: string;
    source_start?: number | null;
    source_end?: number | null;
    text_hash?: string | null;
  }>;
  evidence?: Array<{
    event_id: string;
    purpose: string;
    source_system: string;
    source_record_id: string;
    event_type: string;
    timestamp: string;
    match_method: string;
    match_confidence: string;
  }>;
};

export type Reconciliation = {
  reconciliation_id: string;
  invoice_id: string;
  run_number: number;
  supersedes_run_id?: string | null;
  submitted_amount: string;
  confirmed_payable_amount: string;
  recommended_deduction: string;
  needs_review_amount: string;
  claimed_outcomes: number;
  payable_outcomes: number;
  disputed_outcomes: number;
  needs_review_outcomes: number;
  rule_program_version: number;
  engine_version: string;
  real_data_disclosure?: string;
  determinations?: Determination[];
  [key: string]: unknown;
};

export type CustomerReviewRequest = {
  reviewed_by: string;
  claims_sampled: number;
  confirmed_disputes: number;
  rejected_disputes: number;
  missing_disputes: number;
  estimated_overpayment_prevented: string;
  estimated_hours_saved: string;
  would_use_next_month: boolean;
  willingness_to_pay: string;
  permission_to_quote: boolean;
  notes: string;
};

export type InvoicePreview = {
  headers: string[];
  auto_mapping: Record<string, string | null>;
  required: string[];
  missing_required_fields: string[];
  sample_rows: Record<string, string>[];
};

export type CompilerAssurance = {
  assurance_version: string;
  agreement_id: string;
  source_hash: string;
  hard_gate_passed: boolean;
  review_required: boolean;
  checks: Array<{ id: string; status: "pass" | "fail" | "review"; hard_gate: boolean; summary: string; details: string[] }>;
  execution_probes?: Array<{ id: string; predicate_id: string; status: string; observed_truth?: string | null; detail: string }>;
  mutation_probes?: Array<{ id: string; predicate_id: string; status: string; original_hash: string; mutated_hash?: string | null; detail: string }>;
};

export type AuditEvent = {
  id: string; action: string; object_type: string; object_id: string | null; actor: string; occurred_at: string; details: Record<string, unknown>;
};

export class PilotApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "PilotApiError";
    this.status = status;
  }
}

export function loadPilotToken(): string {
  return sessionStorage.getItem(PILOT_TOKEN_KEY) ?? "";
}

export function savePilotToken(token: string): void {
  sessionStorage.setItem(PILOT_TOKEN_KEY, token.trim());
}

export function clearPilotToken(): void {
  sessionStorage.removeItem(PILOT_TOKEN_KEY);
}

function errorMessage(payload: unknown, fallback: string): string {
  if (!payload || typeof payload !== "object") return fallback;
  const detail = (payload as { detail?: unknown }).detail;
  if (typeof detail === "string") return detail;
  if (detail && typeof detail === "object") {
    const nested = (detail as { detail?: unknown }).detail;
    if (typeof nested === "string") return nested;
    return JSON.stringify(detail);
  }
  return fallback;
}

async function request<T>(
  path: string,
  options: RequestInit = {},
  token = loadPilotToken(),
): Promise<T> {
  const headers = new Headers(options.headers);
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (options.body && !(options.body instanceof FormData) && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  const response = await fetch(`${PILOT_ROOT}${path}`, { ...options, headers });
  if (!response.ok) {
    let payload: unknown;
    try {
      payload = await response.json();
    } catch {
      payload = null;
    }
    throw new PilotApiError(
      errorMessage(payload, `Pilot request failed with HTTP ${response.status}`),
      response.status,
    );
  }
  const contentType = response.headers.get("content-type") ?? "";
  if (contentType.includes("application/json")) return (await response.json()) as T;
  return (await response.text()) as T;
}

function query(values: Record<string, string | number | boolean | undefined>): string {
  const params = new URLSearchParams();
  Object.entries(values).forEach(([key, value]) => {
    if (value !== undefined && value !== "") params.set(key, String(value));
  });
  return params.toString();
}

export const pilotApi = {
  status: () => request<PilotStatus>("/status"),
  contract: (contractId: string) => request<PilotContract>(`/contracts/${contractId}`),
  uploadContract: async (input: {
    file: File;
    customer: string;
    vendor: string;
    periodStart: string;
    periodEnd: string;
    pricePerOutcome: string;
  }) => {
    const body = new FormData();
    body.append("file", input.file);
    const params = query({
      customer: input.customer,
      vendor: input.vendor,
      period_start: input.periodStart,
      period_end: input.periodEnd,
      price_per_outcome: input.pricePerOutcome,
    });
    return request<UploadResult>(`/contract?${params}`, { method: "POST", body });
  },
  createContractFromText: (input: {
    customer: string; vendor: string; periodStart: string; periodEnd: string; pricePerOutcome: string; sourceText: string; sourceDocument?: string;
  }) => request<UploadResult>("/contract/text", {
    method: "POST",
    body: JSON.stringify({
      customer: input.customer, vendor: input.vendor, period_start: input.periodStart, period_end: input.periodEnd,
      price_per_outcome: input.pricePerOutcome, source_document: input.sourceDocument ?? "pasted-contract.txt", source_text: input.sourceText,
    }),
  }),
  previewInvoice: async (file: File) => {
    const body = new FormData(); body.append("file", file);
    return request<InvoicePreview>("/invoice/preview", { method: "POST", body });
  },
  compile: (contractId: string, mode: "auto" | "live" | "recorded") =>
    request<PilotCompilation>(`/contracts/${contractId}/compile?${query({ mode })}`, {
      method: "POST",
    }),
  approve: (compilationId: string) =>
    request<PilotCompilation>(`/compilations/${compilationId}/approve`, { method: "POST" }),
  uploadInvoice: async (input: {
    file: File;
    contractId: string;
    invoiceId: string;
    periodStart: string;
    periodEnd: string;
    columnMapping?: Record<string, string>;
  }) => {
    const body = new FormData();
    body.append("file", input.file);
    const params = query({
      contract_id: input.contractId,
      invoice_id: input.invoiceId,
      billing_period_start: input.periodStart,
      billing_period_end: input.periodEnd,
      column_mapping: input.columnMapping ? JSON.stringify(input.columnMapping) : undefined,
    });
    return request<UploadResult>(`/invoice?${params}`, { method: "POST", body });
  },
  uploadEvidence: async (file: File, invoiceId: string, sourceType: string, completeExport = false) => {
    const body = new FormData();
    body.append("file", file);
    return request<UploadResult>(
      `/evidence?${query({ invoice_id: invoiceId, source_type: sourceType, complete_export: completeExport })}`,
      { method: "POST", body },
    );
  },
  uploadIdentityMap: async (file: File, invoiceId: string) => {
    const body = new FormData();
    body.append("file", file);
    return request<UploadResult>(`/identity-map?${query({ invoice_id: invoiceId })}`, {
      method: "POST",
      body,
    });
  },
  match: (invoiceId: string) =>
    request<MatchSummary>(`/match?${query({ invoice_id: invoiceId })}`, { method: "POST" }),
  unmatched: (invoiceId: string) =>
    request<{ total: number; items: ReviewItem[] }>(
      `/review/unmatched?${query({ invoice_id: invoiceId, limit: 200 })}`,
    ),
  candidates: (invoiceId: string, eventId: string) =>
    request<{ candidates: MatchCandidate[] }>(
      `/review/candidates/${eventId}?${query({ invoice_id: invoiceId })}`,
    ),
  confirmMatch: (input: {
    invoiceId: string;
    eventId: string;
    claimId: string;
    rationale: string;
  }) =>
    request<Record<string, unknown>>(
      `/review/confirm?${query({
        invoice_id: input.invoiceId,
        event_id: input.eventId,
        claim_id: input.claimId,
        rationale: input.rationale,
      })}`,
      { method: "POST" },
    ),
  reconcile: (invoiceId: string) =>
    request<Reconciliation>(`/reconcile?${query({ invoice_id: invoiceId })}`, {
      method: "POST",
    }),
  reconciliation: (runId?: string) =>
    request<Reconciliation>(`/reconciliation${runId ? `?${query({ run_id: runId })}` : ""}`),
  compare: (runId: string, priorRunId: string) =>
    request<Record<string, unknown>>(`/reconciliations/${runId}/compare/${priorRunId}`),
  recordCustomerReview: (runId: string, payload: CustomerReviewRequest) =>
    request<Record<string, unknown>>(`/reconciliations/${runId}/customer-review`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  clear: () => request<{ cleared: boolean }>("/clear", { method: "POST" }),
  seedSample: () => request<{ sample: boolean; contract_id: string; invoice_id: string; air_version_id: string; verification_plan_id: string; reconciliation: Reconciliation }>("/sample/seed", { method: "POST" }),
  auditLog: (limit = 100) => request<{ events: AuditEvent[] }>(`/audit-log?${query({ limit })}`),
  exportUrl: (runId: string, kind: "summary.json" | "evidence.json" | "disputes.csv" | "corrected-invoice.csv" | "review-report.html") =>
    `${PILOT_ROOT}/reconciliations/${runId}/exports/${kind}`,
  downloadExport: async (
    runId: string,
    kind: "summary.json" | "evidence.json" | "disputes.csv" | "corrected-invoice.csv" | "review-report.html",
  ) => {
    const token = loadPilotToken();
    const response = await fetch(
      `${PILOT_ROOT}/reconciliations/${runId}/exports/${kind}`,
      { headers: { Authorization: `Bearer ${token}` } },
    );
    if (!response.ok) throw new PilotApiError(`Export failed with HTTP ${response.status}`, response.status);
    const blob = await response.blob();
    const href = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = href;
    anchor.download = `${runId}-${kind}`;
    anchor.click();
    URL.revokeObjectURL(href);
  },

  // AIR version management
  listAIRVersions: (contractId: string) =>
    request<{ contract_id: string; versions: AIRVersion[] }>(
      `/air-versions?${query({ contract_id: contractId })}`,
    ),
  getAIRVersion: (versionId: string) =>
    request<AIRVersion & { agreement_ir: AgreementIRView }>(`/air-versions/${versionId}`),
  approveAIR: (versionId: string) =>
    request<{ id: string; approved_at: string; approved_by: string }>(
      `/air-versions/${versionId}/approve`,
      { method: "POST" },
    ),
  compileNative: (contractId: string, mode: "auto" | "live" | "recorded") =>
    request<NativeCompileResult>(
      `/contracts/${contractId}/compile-native?${query({ mode })}`,
      { method: "POST", body: JSON.stringify({}) },
    ),
  getAIRConformance: (versionId: string) =>
    request<ConformanceReport>(`/air-versions/${versionId}/conformance`),
  getAIRAssurance: (versionId: string) =>
    request<CompilerAssurance>(`/air-versions/${versionId}/assurance`),
  getActiveAIR: (contractId: string) =>
    request<{ version: AIRVersion; conformance: ConformanceReport }>(
      `/contracts/${contractId}/air-active`,
    ),
  getAgreementComparison: (runId: string) =>
    request<AgreementComparisonEnvelope>(`/reconciliations/${runId}/agreement-comparison`),
  getAgreementBundle: (contractId: string) =>
    request<AgreementBundleView>(`/contracts/${contractId}/agreement-bundle`),
  uploadAgreementDocument: async (input: {
    contractId: string;
    file: File;
    title: string;
    documentType: string;
    effectiveFrom: string;
    effectiveUntil?: string;
    precedence: number;
  }) => {
    const body = new FormData();
    body.append("file", input.file);
    const params = query({
      title: input.title,
      document_type: input.documentType,
      effective_from: input.effectiveFrom,
      effective_until: input.effectiveUntil,
      precedence: input.precedence,
    });
    return request<AgreementBundleView>(
      `/contracts/${input.contractId}/agreement-bundle/documents?${params}`,
      { method: "POST", body },
    );
  },
  addAgreementRelation: (
    contractId: string,
    payload: { source_document_id: string; target_document_id: string; relation: string },
  ) =>
    request<AgreementBundleView>(`/contracts/${contractId}/agreement-bundle/relations`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  createVerificationPlan: (versionId: string, sources: EvidenceSourceDescriptor[]) =>
    request<VerificationPlanEnvelope>(`/air-versions/${versionId}/verification-plan`, {
      method: "POST",
      body: JSON.stringify({ sources }),
    }),
  autoVerificationPlan: (versionId: string, invoiceId: string) =>
    request<VerificationPlanEnvelope>(`/air-versions/${versionId}/verification-plan/auto?${query({ invoice_id: invoiceId })}`, { method: "POST" }),
  getVerificationPlan: (versionId: string) =>
    request<VerificationPlanEnvelope>(`/air-versions/${versionId}/verification-plan`),
  deriveFacts: (invoiceId: string, versionId: string) =>
    request<{ invoice_id: string; air_version_id: string; facts: DerivedFact[] }>(
      `/invoices/${invoiceId}/facts/derive?${query({ air_version_id: versionId })}`,
      { method: "POST" },
    ),
  facts: (invoiceId: string, versionId?: string) =>
    request<{ invoice_id: string; facts: DerivedFact[] }>(
      `/invoices/${invoiceId}/facts?${query({ air_version_id: versionId })}`,
    ),

};

// ---------------------------------------------------------------------------
// AIR / agreement verification types
// ---------------------------------------------------------------------------

export interface AIRVersion {
  id: string;
  version_number: number;
  compiler_mode: string;
  schema_version?: string;
  created_at?: string | null;
  approved_at: string | null;
  approved_by?: string | null;
  payload_hash: string;
  lifecycle_status?: "validation_failed" | "ready_for_review" | "active" | "superseded";
  assurance_hard_gate_passed?: boolean;
  superseded_by_id?: string | null;
}

export interface ConformanceReport {
  agreement_id: string;
  material_clause_count: number;
  covered_material_clause_count: number;
  fully_executable_count: number;
  data_dependent_count: number;
  model_assisted_count: number;
  human_attestation_count: number;
  procedural_count: number;
  non_operational_count: number;
  unsupported_count: number;
  unrepresented_material_clause_count: number;
  norm_count: number;
  proof_requirement_count: number;
  settlement_policy_count: number;
  blocking_diagnostic_count: number;
  approvable: boolean;
  coverage_percent: number;
}

export interface AgreementIRView {
  agreement_id: string;
  schema_version: string;
  clauses: Array<{ id: string; document_id: string; text: string; material: boolean; source_start?: number | null; source_end?: number | null; text_hash?: string | null }>;
  norms: Array<{ id: string; norm_type: string; subject: string; consequence: string; source_clause_ids: string[]; automation_class: string; violation_reason_code?: string | null }>;
  proof_requirements: Array<{ id: string; norm_id: string; description: string; acceptable_fact_types: string[]; preferred_authority: string; requires_absence_proof?: boolean }>;
  settlement_policies: Array<{ id: string; claim_type: string; source_clause_ids: string[]; currency: string; amount_expression: Record<string, unknown> }>;
  diagnostics: Array<{ code: string; severity: string; message: string; clause_ids?: string[] }>;
}

export interface NativeCompileResult {
  air_version_id: string;
  version_number: number;
  compiler_mode: string;
  clauses: number;
  norms: number;
  proof_requirements: number;
  settlement_policies: number;
  blocking_diagnostics: number;
  approval_ready: boolean;
  diagnostics: Array<{ code: string; severity: string; message: string; clause_ids?: string[] }>;
  conformance: ConformanceReport;
  agreement_ir: AgreementIRView;
}

export interface AgreementComparisonEnvelope {
  run_id: string;
  created_at: string;
  air_version: string;
  exact_match: boolean;
  mismatch_count: number;
  report: {
    total_claims?: number;
    exact_matches?: number;
    exact_mismatches?: number;
    amounts_match?: boolean;
    legacy_payable?: string;
    legacy_disputed?: string;
    air_payable?: string;
    air_disputed?: string;
    differences?: unknown[];
    air_version_id?: string | null;
    verification_plan_id?: string | null;
    [key: string]: unknown;
  };
}

export interface AgreementBundleView {
  id: string;
  contract_id: string;
  effective_at: string;
  parties: Record<string, string>;
  documents: Array<{ id: string; title: string; effective_from: string; effective_until: string | null; precedence: number; source_hash: string; effective: boolean }>;
  relations: Array<{ source_document_id: string; target_document_id: string; relation: string }>;
}

export interface EvidenceCapability {
  fact_type: string;
  entity_type: string;
  fields?: string[];
  event_types?: string[];
  state_transitions?: string[];
  authority: string;
  identity_keys?: string[];
  timestamp_semantics?: string;
  source_timezone?: string;
  freshness_seconds?: number | null;
  retention_days?: number | null;
  historical_snapshots?: boolean;
  absence_provable?: boolean;
  completeness_guarantee?: string;
  parser_version?: string | null;
}

export interface EvidenceSourceDescriptor {
  source_id: string;
  source_type: string;
  system: string;
  capabilities: EvidenceCapability[];
}

export interface VerificationPlanEnvelope {
  id: string;
  contract_id: string;
  air_version_id: string;
  version: number;
  created_at: string;
  payload_hash: string;
  plan: { agreement_id: string; items: Array<{ proof_requirement_id: string; status: string; selected_source_ids: string[]; missing_fact_types: string[]; missing_capabilities?: string[]; rationale: string }> };
}

export interface DerivedFact {
  id: string;
  invoice_id: string;
  claim_id: string;
  air_version_id: string;
  fact_type: string;
  truth: "true" | "false" | "unknown" | "conflicting";
  evidence_ids: string[];
  authority: string;
  derivation_method: string;
  evaluator_version: string;
  input_hash: string;
  created_at: string;
  review_status: string;
}

