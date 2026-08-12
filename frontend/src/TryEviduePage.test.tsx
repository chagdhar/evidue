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
  window.localStorage.clear();
});

it("delivers one successful reconciliation before asking for contact", async () => {
  const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
    const url = String(input);
    if (url.endsWith("/api/public-try/analyze")) {
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
    if (url.includes("/api/public-try/TRY-123/approve-and-reconcile")) {
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
    if (url.includes("/api/public-try/TRY-123/outcomes/OUT-004821")) {
      return response({
        outcome_id: "OUT-004821",
        vendor_claim_id: "VC-4821",
        vendor_claim: "Refund completed",
        agent_version: "refund-v2.4",
        customer_id: "CUST-4821",
        account_id: "ACCT-4821",
        intent: "refund",
        status: "disputed",
        reason: "Payment processor rejected the refund before the contract deadline.",
        rule_id: "R3",
        rule: { id: "R3", title: "Refund completion", description: "Refund must post successfully.", clause_text: "A refund is complete only when the payment processor confirms success.", operation: "require_event_within", evidence_required: ["payment processor"], consequence: "disputed" },
        billed_amount: "1.50",
        confirmed_payable_amount: "0.00",
        confirmed_disputed_amount: "1.50",
        needs_review_amount: "0.00",
        evidence: [{
          id: "EV-1",
          source_system: "payment_processor",
          source_record_id: "PAY-4821",
          event_type: "refund_rejected",
          timestamp: "2026-06-04T10:15:00",
          values: { status: "rejected" },
          provenance: { connector_name: "Payment processor", authority: "customer-controlled", collection_method: "API", raw_record_id: "RAW-1", raw_payload: { status: "rejected" }, payload_hash: "sha256:abc123", schema_version: "1.0", match_status: "matched", match_method: "direct_outcome_id", match_confidence: "1.0000", match_reason: "Stable outcome ID", received_at: "2026-06-04T10:16:00" },
        }],
        claim_provenance: { connector_name: "Vendor invoice", raw_record_id: "RAW-CLAIM", source_record_id: "VC-4821", payload_hash: "sha256:claim123", schema_version: "1.0" },
        engine_version: "test-engine",
        compilation_id: "TRY-123",
        program_version: 1,
        source_hash: "abc",
        evaluated_at: "2026-06-30T00:00:00",
      });
    }
    throw new Error(`Unexpected URL ${url}`);
  });

  const user = userEvent.setup();
  render(<TryEviduePage />, { wrapper: MemoryRouter });

  expect(screen.getByRole("heading", { name: /Nova AI billed Acme \$150 for 100 outcomes/i })).toBeInTheDocument();
  expect(screen.queryByRole("link", { name: "Share your workflow" })).not.toBeInTheDocument();
  expect(await screen.findByRole("dialog", { name: "Start with the vendor invoice" })).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "Skip tour" }));

  await user.click(screen.getByRole("button", { name: "Verify the invoice" }));
  expect(await screen.findByText("No same-intent recontact")).toBeInTheDocument();
  expect(screen.getByText("CONTRACT INTERPRETED", { exact: true })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: /Review proposed rules/i })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Re-read contract" })).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "Approve 1 contract rule" }));
  await user.click(screen.getByRole("button", { name: "Verify 100 claims" }));

  expect((await screen.findAllByText("$124.50")).length).toBeGreaterThan(0);
  expect(screen.getAllByText("$25.50").length).toBeGreaterThan(0);
  expect(screen.getByText("17 claims contradicted an approved contract rule.")).toBeInTheDocument();
  expect(screen.queryByRole("link", { name: "R3 · OUT-004821" })).not.toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "R3 · OUT-004821" }));
  expect(await screen.findByRole("heading", { name: /One charge, from assertion to financial consequence/i })).toBeInTheDocument();
  expect(screen.getAllByText("Payment processor").length).toBeGreaterThanOrEqual(1);
  expect(screen.getAllByText("sha256:abc123").length).toBeGreaterThanOrEqual(1);
  expect(screen.getByText("Proof envelope")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Copy dispute summary" })).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Share your workflow" })).toHaveAttribute("href", "/contact");
  expect(fetchMock).toHaveBeenCalledTimes(3);
});
