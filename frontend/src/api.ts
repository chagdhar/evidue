export type DemoStatus = {
  seeded: boolean;
  reconciled: boolean;
  claimed_outcomes: number;
  billing_period: string;
};

export type Rule = {
  id: string;
  title: string;
  description: string;
  parameters: Record<string, string>;
  evidence_required: string[];
  consequence: string;
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
  status: string;
  claimed_outcomes: number;
  payable_outcomes: number;
  disputed_outcomes: number;
  needs_review_outcomes: number;
  submitted_amount: string;
  payable_amount: string;
  recommended_deduction: string;
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
  payable_amount: string;
  closed_at: string;
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
};

export type OutcomeDetail = Outcome & {
  account_id: string;
  expected_action: string;
  conversation: { id: string; intent: string; closed_at: string };
  contract_clause: string | null;
  rule: Rule | null;
  evidence: EvidenceEvent[];
  evaluated_at: string;
  engine_version: string;
};

export type OutcomePage = {
  total: number;
  offset: number;
  limit: number;
  items: Outcome[];
};

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`/api${path}`, options);
  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || `Request failed (${response.status})`);
  }
  return response.json() as Promise<T>;
}

export const api = {
  status: () => request<DemoStatus>("/demo/status"),
  contract: () => request<Contract>("/contracts/current"),
  invoice: () => request<Invoice>("/invoices/current"),
  current: () => request<Summary>("/reconciliations/current"),
  reconcile: () => request<Summary>("/reconciliations", { method: "POST" }),
  reset: () => request<DemoStatus>("/demo/reset", { method: "POST" }),
  outcomes: (query: URLSearchParams) =>
    request<OutcomePage>(`/reconciliations/current/outcomes?${query}`),
  outcome: (id: string) =>
    request<OutcomeDetail>(`/reconciliations/current/outcomes/${id}`),
};
