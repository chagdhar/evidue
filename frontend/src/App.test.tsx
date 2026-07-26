import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import App from "./App";

const contract = {
  id: "CONTRACT-1",
  customer: "Acme Commerce",
  vendor: "Nova Support AI",
  period_start: "2026-06-01T00:00:00",
  period_end: "2026-07-01T00:00:00",
  price_per_outcome: "1.50",
  clauses: Array.from({ length: 7 }, (_, index) => ({
    id: `CLAUSE-R${index + 1}`,
    text: `Contract clause ${index + 1}`,
    rule: {
      id: `R${index + 1}`,
      title: `Rule ${index + 1}`,
      description: "Executable rule",
      parameters: {},
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
  payable_amount: "12480.00",
  recommended_deduction: "2520.00",
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
  payable_amount: "0.00",
  closed_at: "2026-06-04T17:21:00",
};

function response(body: unknown, ok = true) {
  return Promise.resolve({
    ok,
    status: ok ? 200 : 500,
    json: () => Promise.resolve(body),
    text: () => Promise.resolve(ok ? JSON.stringify(body) : ""),
  } as Response);
}

function mockApi(reconciled = false) {
  return vi.spyOn(globalThis, "fetch").mockImplementation((input, options) => {
    const url = String(input);
    if (url.endsWith("/api/demo/status")) {
      return response({ seeded: true, reconciled, claimed_outcomes: 10000, billing_period: "June" });
    }
    if (url.endsWith("/api/contracts/current")) return response(contract);
    if (url.endsWith("/api/invoices/current")) return response(invoice);
    if (url.endsWith("/api/reconciliations") && options?.method === "POST") return response(summary);
    if (url.endsWith("/api/reconciliations/current")) return response(summary);
    if (url.includes("/api/reconciliations/current/outcomes?")) {
      return response({ total: 1, offset: 0, limit: 25, items: [failedRefund] });
    }
    if (url.endsWith("/api/reconciliations/current/outcomes/OUT-004821")) {
      return response({
        ...failedRefund,
        account_id: "ACC-004821",
        expected_action: "refund",
        conversation: { id: "CONV-004821", intent: "refund", closed_at: failedRefund.closed_at },
        contract_clause: "Downstream completion is required.",
        rule: contract.clauses[2].rule,
        evidence: [
          {
            id: "EV-1",
            source_system: "payment_processor",
            source_record_id: "processor-1",
            event_type: "downstream_failed",
            timestamp: failedRefund.closed_at,
            customer_id: failedRefund.customer_id,
            outcome_id: failedRefund.outcome_id,
            values: { action: "refund" },
            ingested_at: "2026-07-01T08:00:00",
          },
        ],
        evaluated_at: "2026-07-01T12:00:00",
        engine_version: "2026.06.1",
      });
    }
    return response({}, false);
  });
}

afterEach(() => vi.restoreAllMocks());

describe("Evidue demo", () => {
  it("shows disclosure and submitted invoice without pretending reconciliation ran", async () => {
    mockApi(false);
    render(<App />);
    expect(await screen.findByText("Synthetic demonstration data.")).toBeInTheDocument();
    expect(screen.getByText("$15,000.00")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Run reconciliation" })).toBeInTheDocument();
    expect(screen.queryByText("$12,480.00")).not.toBeInTheDocument();
  });

  it("runs the backend reconciliation and displays exact results and exports", async () => {
    mockApi(false);
    render(<App />);
    await userEvent.click(await screen.findByRole("button", { name: "Run reconciliation" }));
    expect(await screen.findByText("$12,480.00")).toBeInTheDocument();
    expect(screen.getByText("$2,520.00")).toBeInTheDocument();
    expect(screen.getByText("8,320")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Dispute CSV" })).toHaveAttribute(
      "href",
      "/api/reconciliations/current/exports/disputes.csv",
    );
  });

  it("filters disputed outcomes and opens traceable evidence", async () => {
    mockApi(true);
    render(<App />);
    const status = await screen.findByRole("combobox", { name: "Status" });
    fireEvent.mouseDown(status);
    await userEvent.click(await screen.findByRole("option", { name: "Disputed" }));
    await waitFor(() =>
      expect(globalThis.fetch).toHaveBeenCalledWith(
        expect.stringContaining("status=disputed"),
        undefined,
      ),
    );
    await userEvent.click(await screen.findByText("OUT-004821"));
    expect(await screen.findByText("OUT-004821", { selector: "h5" })).toBeInTheDocument();
    expect(screen.getByText("downstream failed")).toBeInTheDocument();
    expect(screen.getByText(/Source record processor-1/)).toBeInTheDocument();
  });

  it("renders backend failures honestly", async () => {
    mockApi(false).mockImplementationOnce(() => response({}, false));
    render(<App />);
    expect(await screen.findByText(/Request failed/)).toBeInTheDocument();
  });
});
