import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, it, vi } from "vitest";
import TryEviduePage from "./TryEviduePage";

function response(body: unknown) {
  return Promise.resolve({ ok: true, text: () => Promise.resolve(JSON.stringify(body)), json: () => Promise.resolve(body) } as Response);
}

afterEach(() => {
  vi.restoreAllMocks();
  sessionStorage.clear();
});

it("delivers one successful reconciliation before asking for contact", async () => {
  const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
    const url = String(input);
    if (url.endsWith("/api/public-demo/try/analyze")) {
      return response({
        sandbox_id: "TRY-123",
        contract_text: "A qualifying resolution is billable at $1.50 only when customer-side evidence satisfies the approved conditions.",
        contract_id: "CONTRACT-ACME-NOVA-2026",
        source_document: "Acme-Nova-Outcome-Pricing-Order-Form.pdf",
        source_hash: "abc",
        mode: "recorded_replay",
        live_model_call: false,
        model: "gemini-test",
        compiler_version: "1.1",
        approval_required: true,
        approval_ready: true,
        rules: [{ id: "R1", title: "No same-intent recontact", description: "Invalid if the customer recontacts within 7 days.", clause_text: "No recontact within seven days.", operation: "prohibit_event_within", evidence_required: ["support events"], consequence: "disputed", priority: 1 }],
        diagnostics: [],
        fallback_reason: "Live Gemini is not configured on this deployment.",
        session_expires_in_seconds: 1800,
        duration_ms: 20,
      });
    }
    if (url.includes("/api/public-demo/try/TRY-123/approve-and-reconcile")) {
      return response({
        sandbox_id: "TRY-123",
        human_approval_recorded: true,
        compiler_mode: "recorded_replay",
        live_model_call: false,
        sample_size: 100,
        payable_outcomes: 83,
        disputed_outcomes: 17,
        needs_review_outcomes: 0,
        submitted_amount: "150.00",
        confirmed_payable_amount: "124.50",
        recommended_deduction: "25.50",
        representative_findings: [{ rule_id: "R3", outcome_id: "OUT-004821" }],
        sampling_method: "deterministic",
        compilation_id: "TRY-123",
        program_version: 1,
        source_hash: "abc",
        engine_version: "test-engine",
        duration_ms: 8,
      });
    }
    throw new Error(`Unexpected URL ${url}`);
  });

  const user = userEvent.setup();
  render(<TryEviduePage />, { wrapper: MemoryRouter });

  expect(screen.getByRole("heading", { name: /Nova AI billed Acme \$150 for 100 outcomes/i })).toBeInTheDocument();
  expect(screen.queryByRole("link", { name: "Share your workflow" })).not.toBeInTheDocument();

  await user.click(screen.getByRole("button", { name: "Analyze synthetic contract" }));
  expect(await screen.findByText("No same-intent recontact")).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "Approve rules & verify invoice" }));

  expect(await screen.findByText("$124.50")).toBeInTheDocument();
  expect(screen.getByText("$25.50")).toBeInTheDocument();
  expect(screen.getByText(/17 claims/)).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "R3 · OUT-004821" })).toHaveAttribute("href", "/demo/invoices/current?outcome=OUT-004821");
  expect(screen.getByRole("link", { name: "Share your workflow" })).toHaveAttribute("href", "/contact");
  expect(fetchMock).toHaveBeenCalledTimes(2);
});
