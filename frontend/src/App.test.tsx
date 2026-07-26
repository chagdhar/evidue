import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import App from "./App";

const ruleDefinitions = [
  {
    id: "R1",
    title: "No same-intent recontact",
    description: "No same-intent contact within seven days.",
    parameters: { window_days: "7" },
  },
  {
    id: "R2",
    title: "No human completion",
    description: "No human completion within 24 hours.",
    parameters: { window_hours: "24" },
  },
  {
    id: "R3",
    title: "Downstream action succeeds",
    description: "The promised downstream action succeeds within two hours.",
    parameters: { window_hours: "2" },
  },
  {
    id: "R4",
    title: "Single attribution",
    description: "Only one otherwise-payable outcome is billable.",
    parameters: { window_hours: "24" },
  },
  {
    id: "R5",
    title: "Account and action match",
    description: "Operational evidence matches the expected account and action.",
    parameters: {},
  },
  {
    id: "R6",
    title: "Billing period",
    description: "The outcome closes inside the billing period.",
    parameters: { start: "2026-06-01", end_exclusive: "2026-07-01" },
  },
  {
    id: "R7",
    title: "Sufficient identifiers",
    description: "The claim has sufficient identifiers.",
    parameters: {},
  },
];

const contract = {
  id: "CONTRACT-1",
  customer: "Acme Commerce",
  vendor: "Nova Support AI",
  period_start: "2026-06-01T00:00:00",
  period_end: "2026-07-01T00:00:00",
  price_per_outcome: "1.50",
  clauses: ruleDefinitions.map((rule) => ({
    id: `CLAUSE-${rule.id}`,
    text: `Contract clause for ${rule.id}`,
    rule: {
      ...rule,
      evidence_required: ["ai_closed"],
      consequence: "Charge is not payable.",
    },
  })),
  evidence_sources: ["Payment processor", "Acme support desk"],
};

const invoice = {
  invoice_id: "INV-1",
  claimed_outcomes: 10000,
  submitted_amount: "15000.00",
  status: "submitted",
  billing_period_start: "2026-06-01T00:00:00",
  billing_period_end: "2026-07-01T00:00:00",
};

const summary = {
  reconciliation_id: "REC-1",
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

const detail = {
  ...failedRefund,
  account_id: "ACC-004821",
  expected_action: "refund",
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

function response(body: unknown, ok = true) {
  return Promise.resolve({
    ok,
    status: ok ? 200 : 500,
    json: () => Promise.resolve(body),
    text: () => Promise.resolve(ok ? JSON.stringify(body) : ""),
  } as Response);
}

function mockApi(reconciled = false, summaryResult = summary) {
  return vi.spyOn(globalThis, "fetch").mockImplementation((input, options) => {
    const url = String(input);
    if (url.endsWith("/api/demo/status")) {
      return response({
        seeded: true,
        reconciled,
        claimed_outcomes: 10000,
        billing_period: "June",
      });
    }
    if (url.endsWith("/api/contracts/current")) return response(contract);
    if (url.endsWith("/api/invoices/current")) return response(invoice);
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
          : summaryResult.claimed_outcomes;
      return response({ total, offset: 0, limit: 25, items: [failedRefund] });
    }
    if (url.endsWith(`/api/reconciliations/current/outcomes/${failedRefund.outcome_id}`)) {
      return response(detail);
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
    expect(screen.queryByText("$12,480.00")).not.toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Claims review" })).not.toBeInTheDocument();
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
    expect(screen.getByText("What happened, in order")).toBeInTheDocument();
    expect(screen.getByText("AI marked outcome resolved")).toBeInTheDocument();
    expect(screen.getByText("Downstream action failed")).toBeInTheDocument();
    expect(screen.getByText("Completion window expired")).toBeInTheDocument();
    expect(screen.getByText(/processor-4821/)).toBeInTheDocument();
    expect(screen.getByText("Imported operational evidence")).toBeInTheDocument();
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

  it("renders backend failures honestly", async () => {
    mockApi(false).mockImplementationOnce(() => response({}, false));
    render(<App />);
    expect(await screen.findByText(/Request failed/)).toBeInTheDocument();
  });
});
