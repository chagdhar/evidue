import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import App from "./App";
import type { DataReadiness, Summary } from "./api";

const ruleDefinitions = [
  {
    id: "R1",
    title: "No same-intent recontact",
    description: "No same-intent contact within seven days.",
    operation: "prohibit_event_within",
    priority: 30,
    parameters: { window_value: 7, window_unit: "days" },
  },
  {
    id: "R2",
    title: "No human completion",
    description: "No human completion within 24 hours.",
    operation: "prohibit_event_within",
    priority: 40,
    parameters: { window_value: 24, window_unit: "hours" },
  },
  {
    id: "R3",
    title: "Downstream action succeeds",
    description: "The promised downstream action succeeds within two hours.",
    operation: "require_success_event_within",
    priority: 50,
    parameters: { window_value: 2, window_unit: "hours" },
  },
  {
    id: "R4",
    title: "Single attribution",
    description: "Only one otherwise-payable outcome is billable.",
    operation: "unique_first_claim_within",
    priority: 100,
    parameters: { window_value: 24, window_unit: "hours" },
  },
  {
    id: "R5",
    title: "Account and action match",
    description: "Operational evidence matches the expected account and action.",
    operation: "prohibit_field_mismatch_event",
    priority: 60,
    parameters: {},
  },
  {
    id: "R6",
    title: "Billing period",
    description: "The outcome closes inside the billing period.",
    operation: "claim_datetime_in_range",
    priority: 20,
    parameters: { start: "2026-06-01", end_exclusive: "2026-07-01" },
  },
  {
    id: "R7",
    title: "Sufficient identifiers",
    description: "The claim has sufficient identifiers.",
    operation: "validate_evidence_envelope",
    priority: 10,
    parameters: {},
  },
];

const compiledRules = ruleDefinitions.map((rule) => ({
  ...rule,
  clause_text: `Contract clause for ${rule.id}`,
  evidence_required: ["ai_closed"],
  consequence: rule.id === "R7" ? "needs_review" : "disputed",
  compilation_id: "COMP-RECORDED-GEMINI-V1",
}));

const compilation = {
  id: "COMP-RECORDED-GEMINI-V1",
  contract_id: "CONTRACT-1",
  source_document: "Acme-Nova-Outcome-Pricing-Order-Form.pdf",
  source_hash: "sha256:contract",
  prompt_hash: "sha256:prompt",
  provider: "google-gemini",
  model: "gemini-2.5-flash-lite",
  compiler_version: "1.0",
  status: "approved" as const,
  version: 1,
  live_model_call: false,
  created_at: "2026-07-01T08:10:00",
  approved_at: "2026-07-01T08:15:00",
  rules: compiledRules,
  safety_boundary: "The LLM proposes only schema-validated rules; the deterministic interpreter evaluates claims.",
};

const contract = {
  id: "CONTRACT-1",
  customer: "Acme Commerce",
  vendor: "Nova Support AI",
  period_start: "2026-06-01T00:00:00",
  period_end: "2026-07-01T00:00:00",
  price_per_outcome: "1.50",
  clauses: compiledRules.map((rule) => ({
    id: `CLAUSE-${rule.id}`,
    text: rule.clause_text,
    rule,
  })),
  evidence_sources: ["Payment processor", "Acme support desk"],
  contract_text: "Synthetic contract excerpt — demonstration only\nPrice: $1.50 per supported outcome",
  compilation,
  latest_compilation: compilation,
};

const invoice = {
  invoice_id: "INV-1",
  claimed_outcomes: 10000,
  submitted_amount: "15000.00",
  status: "submitted",
  billing_period_start: "2026-06-01T00:00:00",
  billing_period_end: "2026-07-01T00:00:00",
};

const scenarios = [
  {
    id: "headline",
    name: "Full invoice reconciliation",
    description: "The complete 10,000-line invoice across all confirmed dispute rules.",
    demo_outcome_id: "OUT-004821",
  },
  {
    id: "evidence_review",
    name: "Contradictory evidence",
    description: "Directly matched success and failure evidence requires review.",
    demo_outcome_id: "CASE-REVIEW-001",
  },
  {
    id: "recovery",
    name: "Failed action, valid follow-up",
    description: "An invalid first claim cannot suppress a later valid claim.",
    demo_outcome_id: "CASE-RECOVERY-001",
  },
  {
    id: "duplicate_window",
    name: "Duplicate attribution window",
    description: "Three otherwise-payable claims demonstrate the deterministic winner.",
    demo_outcome_id: "CASE-DUP-002",
  },
];

const headlineStatus = {
  public_demo: false,
  seeded: true,
  reconciled: false,
  claimed_outcomes: 10000,
  billing_period: "June",
  scenario_id: "headline",
  scenario_name: "Full invoice reconciliation",
  scenario_description: scenarios[0].description,
  demo_outcome_id: "OUT-004821",
};

const summary: Summary = {
  reconciliation_id: "REC-1",
  scenario_id: "headline",
  scenario_name: "Headline invoice",
  status: "completed",
  claimed_outcomes: 10000,
  payable_outcomes: 8320,
  disputed_outcomes: 1680,
  needs_review_outcomes: 0,
  submitted_amount: "15000.00",
  confirmed_payable_amount: "12480.00",
  recommended_deduction: "2520.00",
  needs_review_amount: "0.00",
  price_per_outcome: "1.50",
  categories: {
    R1: { label: "Same-intent recontacts", count: 720, amount: "1080.00" },
    R2: { label: "Human completions or corrections", count: 360, amount: "540.00" },
    R3: { label: "Failed downstream actions", count: 300, amount: "450.00" },
    R4: { label: "Duplicate charges", count: 180, amount: "270.00" },
    R5: { label: "Account or action mismatches", count: 120, amount: "180.00" },
  },
  synthetic_disclosure: "No real customer or vendor data is shown.",
};

const readiness: DataReadiness = {
  status: "ready",
  synthetic_disclosure: "No real customer or vendor data is shown.",
  collection_note: "Source-shaped records are preserved, normalized, matched, and evaluated.",
  totals: {
    claimed_outcomes: 10000,
    raw_records: 50121,
    sampled_raw_records: 122,
    normalized_events: 30000,
    direct_matches: 9975,
    secondary_matches: 25,
    review_records: 0,
    claim_coverage_percent: 100,
    contract_rules_approved: 7,
  },
  sources: [
    {
      id: "vendor_claim_manifest",
      name: "Vendor claim manifest",
      category: "Invoice claims",
      owner: "Nova Support AI",
      authority: "Vendor assertion",
      collection_method: "CSV upload",
      production_method: "SFTP or invoice API",
      source_format: "CSV",
      schedule: "Per invoice",
      status: "fixture_loaded",
      description: "Outcome-level claims.",
      fields: ["outcome_id"],
      raw_records: 10000,
      normalized_records: 10000,
      rejected_records: 0,
      matched_records: 10000,
      secondary_matches: 0,
      review_records: 0,
      last_synced_at: "2026-07-01T08:00:00",
      trust_boundary: "Declares the claim; does not decide payability.",
    },
    ...["Vendor agent execution log", "Customer support desk", "Payment processor", "Product operations", "Billing ledger", "Customer identity map", "Contract documents"].map((name, index) => ({
      id: `source-${index}`,
      name,
      category: "Operational evidence",
      owner: "Acme Commerce",
      authority: "Customer system of record",
      collection_method: "JSONL fixture",
      production_method: "Read-only API or warehouse view",
      source_format: "JSONL",
      schedule: "Daily",
      status: "fixture_loaded",
      description: "Operational evidence.",
      fields: ["source_record_id"],
      raw_records: 5000,
      normalized_records: 5000,
      rejected_records: 0,
      matched_records: 5000,
      secondary_matches: index === 1 ? 25 : 0,
      review_records: 0,
      last_synced_at: "2026-07-01T08:00:00",
      trust_boundary: "Read-only customer evidence.",
    })),
  ],
  pipeline: [
    { id: "collect", label: "Collect", description: "Receive records." },
    { id: "raw", label: "Preserve raw", description: "Keep originals." },
    { id: "normalize", label: "Normalize", description: "Map fields." },
    { id: "match", label: "Match evidence", description: "Resolve identifiers." },
    { id: "evaluate", label: "Evaluate", description: "Apply rules." },
  ],
  onboarding: [
    { phase: "1", label: "Start with exports", description: "CSV and JSONL." },
    { phase: "2", label: "Connect read-only systems", description: "APIs and warehouse views." },
    { phase: "3", label: "Incremental sync", description: "Webhooks and polling." },
  ],
};

const reviewInvoice = {
  ...invoice,
  claimed_outcomes: 2,
  submitted_amount: "3.00",
};

const reviewStatus = {
  ...headlineStatus,
  claimed_outcomes: 2,
  scenario_id: "evidence_review",
  scenario_name: "Contradictory evidence",
  scenario_description: scenarios[1].description,
  demo_outcome_id: "CASE-REVIEW-001",
};

const reviewSummary = {
  ...summary,
  reconciliation_id: "REC-REVIEW",
  scenario_id: "evidence_review",
  scenario_name: "Contradictory evidence",
  claimed_outcomes: 2,
  payable_outcomes: 1,
  disputed_outcomes: 0,
  needs_review_outcomes: 1,
  submitted_amount: "3.00",
  confirmed_payable_amount: "1.50",
  recommended_deduction: "0.00",
  needs_review_amount: "1.50",
  categories: {},
};

const failedRefund = {
  outcome_id: "OUT-004821",
  customer_id: "CUST-004821",
  intent: "refund",
  vendor_claim: "resolved",
  status: "disputed",
  reason: "Promised downstream action failed within the required two-hour window",
  rule_id: "R3",
  billed_amount: "1.50",
  confirmed_payable_amount: "0.00",
  confirmed_disputed_amount: "1.50",
  needs_review_amount: "0.00",
  closed_at: "2026-06-04T17:21:00",
};

const reviewOutcome = {
  ...failedRefund,
  outcome_id: "CASE-REVIEW-001",
  customer_id: "CUST-REVIEW-001",
  status: "needs_review",
  reason: "Contradictory directly matched downstream evidence requires review",
  rule_id: "R7",
  confirmed_disputed_amount: "0.00",
  needs_review_amount: "1.50",
};

const provenance = {
  connector_id: "payment_processor",
  connector_name: "Payment processor",
  authority: "Customer system of record",
  collection_method: "JSONL fixture",
  production_method: "Read-only API",
  raw_record_id: "RAW-PAY-4821",
  raw_payload: { transaction_id: "processor-4821", result: "rejected" },
  payload_hash: "sha256:test",
  schema_version: "2026-06-01",
  match_status: "matched",
  match_method: "direct_outcome_id",
  match_confidence: "1.0000",
  match_reason: "Stable outcome ID supplied.",
  received_at: "2026-07-01T08:00:00",
};

const detail = {
  ...failedRefund,
  account_id: "ACC-004821",
  expected_action: "refund",
  vendor_claim_id: "CLM-004821",
  agent_version: "refund-v2.3",
  claim_provenance: { ...provenance, connector_id: "vendor_claim_manifest", connector_name: "Vendor claim manifest", collection_method: "CSV upload" },
  conversation: {
    id: "CONV-004821",
    intent: "refund",
    closed_at: failedRefund.closed_at,
  },
  contract_clause: "Downstream completion is required.",
  rule: contract.clauses[2].rule,
  duplicate_winner_outcome_id: null,
  evidence: [
    {
      id: "EV-CLOSED",
      source_system: "nova_agent",
      source_record_id: "nova-4821",
      event_type: "ai_closed",
      timestamp: failedRefund.closed_at,
      customer_id: failedRefund.customer_id,
      outcome_id: failedRefund.outcome_id,
      values: { action: "refund" },
      ingested_at: "2026-07-01T08:00:00",
      provenance: { ...provenance, connector_id: "vendor_agent_log", connector_name: "Vendor agent execution log", authority: "Vendor evidence" },
    },
    {
      id: "EV-FAILED",
      source_system: "payment_processor",
      source_record_id: "processor-4821",
      event_type: "downstream_failed",
      timestamp: "2026-06-04T17:41:00",
      customer_id: failedRefund.customer_id,
      outcome_id: failedRefund.outcome_id,
      values: { action: "refund" },
      ingested_at: "2026-07-01T08:00:00",
      provenance,
    },
  ],
  computed_timeline_markers: [
    {
      id: "COMPUTED-DEADLINE",
      marker_type: "completion_window_expired",
      timestamp: "2026-06-04T19:21:00",
      description: "Computed contractual two-hour completion deadline",
    },
  ],
  evaluated_at: "2026-07-01T12:00:00",
  engine_version: "2026.06.1",
};

const reviewDetail = {
  ...detail,
  ...reviewOutcome,
  conversation: {
    id: "CONV-REVIEW-001",
    intent: "refund",
    closed_at: reviewOutcome.closed_at,
  },
  rule: contract.clauses[6].rule,
  contract_clause: "Contract clause for R7",
  evidence: [
    { ...detail.evidence[0], id: "EV-REVIEW-CLOSED", outcome_id: reviewOutcome.outcome_id },
    {
      ...detail.evidence[1],
      id: "EV-REVIEW-SUCCESS",
      event_type: "downstream_succeeded",
      outcome_id: reviewOutcome.outcome_id,
    },
    {
      ...detail.evidence[1],
      id: "EV-REVIEW-FAILED",
      outcome_id: reviewOutcome.outcome_id,
    },
  ],
  computed_timeline_markers: [],
};

function response(body: unknown, ok = true) {
  return Promise.resolve({
    ok,
    status: ok ? 200 : 500,
    json: () => Promise.resolve(body),
    text: () => Promise.resolve(ok ? JSON.stringify(body) : ""),
  } as Response);
}

function mockApi(
  reconciled = false,
  summaryResult = summary,
  statusResult = headlineStatus,
  invoiceResult = invoice,
  outcomeResult = failedRefund,
  detailResult = detail,
) {
  let activeStatus = { ...statusResult, reconciled };
  let activeInvoice = invoiceResult;
  return vi.spyOn(globalThis, "fetch").mockImplementation((input, options) => {
    const url = String(input);
    if (url.endsWith("/api/demo/status")) {
      return response(activeStatus);
    }
    if (url.endsWith("/api/demo/scenarios")) return response(scenarios);
    if (url.includes("/api/demo/reset?") && options?.method === "POST") {
      const scenarioId = new URL(url, "http://localhost").searchParams.get("scenario_id");
      if (scenarioId === "evidence_review") {
        activeStatus = { ...reviewStatus, reconciled: false };
        activeInvoice = reviewInvoice;
      } else if (scenarioId === "headline") {
        activeStatus = { ...headlineStatus, reconciled: false };
        activeInvoice = invoice;
      }
      return response(activeStatus);
    }
    if (url.endsWith("/api/contracts/current")) return response(contract);
    if (url.endsWith("/api/data-readiness")) return response(readiness);
    if (url.endsWith("/api/invoices/current")) return response(activeInvoice);
    if (url.endsWith("/api/reconciliations") && options?.method === "POST") {
      return response(summaryResult);
    }
    if (url.endsWith("/api/reconciliations/current")) return response(summaryResult);
    if (url.includes("/api/reconciliations/current/outcomes?")) {
      const query = new URL(url, "http://localhost").searchParams;
      const reason = query.get("reason");
      const status = query.get("status");
      const total = reason
        ? summaryResult.categories[reason as keyof typeof summaryResult.categories]?.count ?? 0
        : status === "disputed"
          ? summaryResult.disputed_outcomes
          : status === "needs_review"
            ? summaryResult.needs_review_outcomes
          : summaryResult.claimed_outcomes;
      return response({ total, offset: 0, limit: 25, items: [outcomeResult] });
    }
    if (url.endsWith(`/api/reconciliations/current/outcomes/${outcomeResult.outcome_id}`)) {
      return response(detailResult);
    }
    if (url.endsWith("/api/reconciliations/current/exports/evidence.json")) {
      return response({ reconciliation: summaryResult, outcomes: [detail] });
    }
    return response({}, false);
  });
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe("Evidue financial-decision demo", () => {
  it("keeps the pre-reconciliation state honest", async () => {
    mockApi(false);
    render(<App />);

    expect(await screen.findByText("$15,000.00")).toBeInTheDocument();
    expect(screen.getByText("10,000 claimed outcomes from the vendor")).toBeInTheDocument();
    expect(screen.getByText("Ready to reconcile")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Run reconciliation" })).toBeInTheDocument();
    expect(screen.getAllByTestId("evidence-readiness")).toHaveLength(1);
    expect(screen.queryByText("$12,480.00")).not.toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Claims review" })).not.toBeInTheDocument();
  });

  it("offers each deterministic product case without embedding financial results", async () => {
    mockApi(false);
    render(<App scenarioLab />);

    await userEvent.click(await screen.findByLabelText("Synthetic data set"));
    expect(screen.getByRole("option", { name: "Full invoice reconciliation" })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "Contradictory evidence" })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "Failed action, valid follow-up" })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "Duplicate attribution window" })).toBeInTheDocument();
    expect(screen.queryByRole("option", { name: /\$/ })).not.toBeInTheDocument();
  });

  it("switches data sets through reset and returns to an honest ready state", async () => {
    mockApi(true);
    render(<App scenarioLab />);

    await screen.findByText("$12,480.00");
    await userEvent.click(screen.getByLabelText("Synthetic data set"));
    await userEvent.click(screen.getByRole("option", { name: "Contradictory evidence" }));

    await waitFor(() =>
      expect(globalThis.fetch).toHaveBeenCalledWith(
        "/api/demo/reset?scenario_id=evidence_review",
        { method: "POST" },
      ),
    );
    expect(await screen.findByText("$3.00")).toBeInTheDocument();
    expect(screen.getByText("2 claimed outcomes from the vendor")).toBeInTheDocument();
    expect(screen.getByText(scenarios[1].description)).toBeInTheDocument();
    expect(screen.queryByText("$12,480.00")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Run reconciliation" })).toBeInTheDocument();
  });

  it("keeps the primary demo fixed to the headline scenario", async () => {
    mockApi(true, reviewSummary, reviewStatus, reviewInvoice);
    render(<App />);

    await waitFor(() =>
      expect(globalThis.fetch).toHaveBeenCalledWith(
        "/api/demo/reset?scenario_id=headline",
        { method: "POST" },
      ),
    );
    expect(await screen.findByText("$15,000.00")).toBeInTheDocument();
    expect(screen.getByText("10,000 claimed outcomes from the vendor")).toBeInTheDocument();
    expect(screen.queryByLabelText("Synthetic data set")).not.toBeInTheDocument();
    expect(screen.queryByText("$12,480.00")).not.toBeInTheDocument();
  });

  it("keeps both synthetic-data disclosures visible", async () => {
    mockApi(false);
    render(<App />);

    expect(await screen.findByText("Synthetic demonstration data")).toBeInTheDocument();
    expect(screen.getByText("Synthetic demonstration data.")).toBeInTheDocument();
    expect(
      screen.getByText(/Operationally realistic data generated deterministically/),
    ).toBeInTheDocument();
  });

  it("makes the corrected payable amount the dominant reconciled value", async () => {
    mockApi(true);
    render(<App />);

    const payable = await screen.findByText("$12,480.00");
    expect(payable).toHaveClass("payable-amount");
    expect(screen.getByText("$2,520.00")).toBeInTheDocument();
    expect(screen.getByText("8,320 of 10,000 outcomes payable")).toBeInTheDocument();
  });

  it("builds the reconciliation bridge from API category values", async () => {
    mockApi(true);
    render(<App />);

    const bridgeTitle = await screen.findByRole("heading", {
      name: "From submitted invoice to payable amount",
    });
    const bridge = bridgeTitle.closest("section");
    expect(bridge).not.toBeNull();
    const scoped = within(bridge as HTMLElement);
    expect(scoped.getByText("− $1,080.00")).toBeInTheDocument();
    expect(scoped.getByText("− $540.00")).toBeInTheDocument();
    expect(scoped.getByText("− $450.00")).toBeInTheDocument();
    expect(scoped.getByText("− $270.00")).toBeInTheDocument();
    expect(scoped.getByText("− $180.00")).toBeInTheDocument();
    expect(scoped.getByText("= $12,480.00")).toBeInTheDocument();
  });

  it("exposes the launch proof, trust boundary, inputs, limitations, and contact path", async () => {
    mockApi(true);
    render(<App />);

    expect(await screen.findByRole("heading", { name: "Example dispute · OUT-004821" })).toBeInTheDocument();
    expect(screen.getAllByText(failedRefund.reason).length).toBeGreaterThanOrEqual(1);
    expect(screen.getByRole("link", { name: "Natural-language contract" })).toHaveAttribute(
      "href",
      "/api/demo/inputs/contract",
    );
    expect(screen.getByText("The LLM does not decide what gets paid.")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Current limitations" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Email Dharun" })).toHaveAttribute(
      "href",
      expect.stringContaining("subject=Evidue%20invoice%20audit"),
    );
  });

  it("requests disputed claims by default after reconciliation", async () => {
    mockApi(true);
    render(<App />);

    await screen.findByRole("heading", { name: "Disputed outcome evidence" });
    await waitFor(() =>
      expect(globalThis.fetch).toHaveBeenCalledWith(
        expect.stringContaining("status=disputed"),
        undefined,
      ),
    );
    expect(screen.getByText("1,680 matching outcomes")).toBeInTheDocument();
  });

  it("filters claims when a finding row is selected", async () => {
    mockApi(true);
    render(<App />);

    await userEvent.click(
      await screen.findByRole("button", { name: /Failed downstream actions/ }),
    );
    await waitFor(() =>
      expect(globalThis.fetch).toHaveBeenCalledWith(
        expect.stringMatching(/status=disputed.*reason=R3/),
        undefined,
      ),
    );
    expect(screen.getByText("300 matching outcomes · R3 selected")).toBeInTheDocument();
  });

  it("visibly identifies OUT-004821 as the demo example", async () => {
    mockApi(true);
    render(<App />);

    expect(await screen.findByText("OUT-004821")).toBeInTheDocument();
    expect(screen.getByText("Demo example")).toBeInTheDocument();
  });

  it("shows claim, obligation, determination, and readable evidence timeline", async () => {
    mockApi(true);
    render(<App />);

    await userEvent.click(
      await screen.findByRole("button", { name: "Review OUT-004821 evidence" }),
    );
    expect(await screen.findByText("Vendor claim")).toBeInTheDocument();
    expect(screen.getByText("Contract obligation")).toBeInTheDocument();
    expect(screen.getByText("Evidue determination")).toBeInTheDocument();
    expect(screen.getByText("Rule inputs and evaluated result")).toBeInTheDocument();
    expect(screen.getAllByText("require_success_event_within")).toHaveLength(2);
    expect(screen.getByText("What happened, in order")).toBeInTheDocument();
    expect(screen.getByText("AI marked outcome resolved")).toBeInTheDocument();
    expect(screen.getByText("Downstream action failed")).toBeInTheDocument();
    expect(screen.getByText("Completion window expired")).toBeInTheDocument();
    expect(screen.getAllByText(/processor-4821/).length).toBeGreaterThanOrEqual(2);
    expect(screen.getByText("Customer-owned operational evidence")).toBeInTheDocument();
    expect(screen.getByText(/Evidue-computed deadline/)).toBeInTheDocument();
  });

  it("keeps the complete contract mapping accessible", async () => {
    mockApi(false);
    render(<App />);

    await userEvent.click(
      await screen.findByRole("button", { name: "View all contract rules" }),
    );
    expect(await screen.findByRole("heading", { name: "All contract rules" })).toBeInTheDocument();
    expect(screen.getByText("Contract clause for R7")).toBeInTheDocument();
    expect(screen.getAllByText("Executable rule")).toHaveLength(7);
  });

  it("downloads a real evidence export and confirms disputed count and amount", async () => {
    mockApi(true);
    vi.spyOn(URL, "createObjectURL").mockReturnValue("blob:evidue-package");
    vi.spyOn(URL, "revokeObjectURL").mockImplementation(() => undefined);
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => undefined);
    render(<App />);

    await userEvent.click(
      await screen.findByRole("button", { name: "Download dispute package" }),
    );
    await waitFor(() =>
      expect(globalThis.fetch).toHaveBeenCalledWith(
        "/api/reconciliations/current/exports/evidence.json",
      ),
    );
    expect(
      await screen.findByText(
        "Dispute package ready: 1,680 disputed outcomes · $2,520.00.",
      ),
    ).toBeInTheDocument();
  });

  it("frames the export as a vendor dispute readiness action", async () => {
    mockApi(true);
    render(<App />);

    expect(
      await screen.findByRole("heading", { name: "Prepare vendor dispute" }),
    ).toBeInTheDocument();
    expect(screen.getByText("Detected ✓")).toBeInTheDocument();
    expect(screen.getByText("Evidenced ✓")).toBeInTheDocument();
    expect(screen.getByText("Ready to dispute ✓")).toBeInTheDocument();
  });

  it("keeps needs-review money separate from the deduction", async () => {
    mockApi(true, {
      ...summary,
      payable_outcomes: 8319,
      needs_review_outcomes: 1,
      confirmed_payable_amount: "12478.50",
      recommended_deduction: "2520.00",
      needs_review_amount: "1.50",
    });
    render(<App />);

    expect(await screen.findByText("$12,478.50")).toHaveClass("payable-amount");
    expect(
      screen.getAllByText("$1.50").find((element) => element.classList.contains("review")),
    ).toBeInTheDocument();
    expect(screen.getByText("$2,520.00")).toHaveClass("disputed");
  });

  it("presents a review-only scenario without turning it into a deduction", async () => {
    mockApi(
      true,
      reviewSummary,
      reviewStatus,
      reviewInvoice,
      reviewOutcome,
      reviewDetail,
    );
    render(<App scenarioLab />);

    expect(
      await screen.findByRole("heading", { name: "Needs-review outcome evidence" }),
    ).toBeInTheDocument();
    expect(screen.getByText("No confirmed deductions")).toBeInTheDocument();
    expect(screen.getByText("− $1.50")).toBeInTheDocument();
    expect(screen.getByText("CASE-REVIEW-001")).toBeInTheDocument();
    await waitFor(() =>
      expect(globalThis.fetch).toHaveBeenCalledWith(
        expect.stringContaining("status=needs_review"),
        undefined,
      ),
    );
    expect(
      screen.getAllByText("$0.00").find((element) => element.classList.contains("disputed")),
    ).toBeInTheDocument();
  });

  it("applies and clears advanced filters only when requested", async () => {
    const fetchSpy = mockApi(true);
    render(<App />);

    await screen.findByRole("heading", { name: "Disputed outcome evidence" });
    await userEvent.click(screen.getByRole("button", { name: "Advanced filters" }));
    fetchSpy.mockClear();

    await userEvent.type(screen.getByLabelText("Outcome ID"), "OUT-004821");
    await userEvent.type(screen.getByLabelText("Customer ID"), "CUST-004821");
    expect(fetchSpy).not.toHaveBeenCalled();

    await userEvent.click(screen.getByRole("button", { name: "Apply filters" }));
    await waitFor(() =>
      expect(fetchSpy).toHaveBeenCalledWith(
        expect.stringMatching(/outcome_id=OUT-004821.*customer_id=CUST-004821/),
        undefined,
      ),
    );
    expect(screen.getByText(/filters applied/)).toBeInTheDocument();

    fetchSpy.mockClear();
    await userEvent.click(screen.getByRole("button", { name: "Clear all" }));
    await waitFor(() => {
      const calls = fetchSpy.mock.calls.map(([input]) => String(input));
      expect(calls.some((url) =>
        url.includes("/api/reconciliations/current/outcomes?") &&
        !url.includes("status=") &&
        !url.includes("reason=") &&
        !url.includes("outcome_id=") &&
        !url.includes("customer_id=") &&
        !url.includes("intent=")
      )).toBe(true);
    });
    expect(screen.getByText("No filters applied.")).toBeInTheDocument();
  });

  it("renders backend failures honestly", async () => {
    mockApi(false).mockImplementationOnce(() => response({}, false));
    render(<App />);
    expect(await screen.findByText(/Request failed/)).toBeInTheDocument();
  });
});
