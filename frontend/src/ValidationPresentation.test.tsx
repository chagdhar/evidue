import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ExportWorkspace, Overview } from "./PilotApp";
import { pilotApi, type Reconciliation } from "./pilotApi";

const reconciliation: Reconciliation = {
  reconciliation_id: "rec-1",
  invoice_id: "inv-1",
  run_number: 1,
  submitted_amount: "150.00",
  confirmed_payable_amount: "124.50",
  recommended_deduction: "25.50",
  needs_review_amount: "0.00",
  currency: "USD",
  identified_dispute_percent: "17.0",
  claimed_outcomes: 100,
  payable_outcomes: 83,
  disputed_outcomes: 17,
  needs_review_outcomes: 0,
  rule_program_version: 1,
  engine_version: "test",
};

describe("validation-critical finance presentation", () => {
  beforeEach(() => vi.restoreAllMocks());

  it("puts the four invoice-decision numbers and dispute percentage first", () => {
    render(<Overview status={null} reconciliation={reconciliation} />);

    expect(screen.getByText("Vendor billed")).toBeInTheDocument();
    expect(screen.getByText("Verified payable")).toBeInTheDocument();
    expect(screen.getByText("Identified for dispute")).toBeInTheDocument();
    expect(screen.getByText("Needs review")).toBeInTheDocument();
    expect(screen.getByText("17.0% of invoice value identified for dispute.")).toBeInTheDocument();
    expect(screen.getByText("$150.00")).toBeInTheDocument();
    expect(screen.getByText("$124.50")).toBeInTheDocument();
    expect(screen.getByText("$25.50")).toBeInTheDocument();
  });


  it("does not recommend a vendor dispute when no disputed dollars were identified", async () => {
    const noDispute: Reconciliation = {
      ...reconciliation,
      confirmed_payable_amount: "150.00",
      recommended_deduction: "0.00",
      disputed_outcomes: 0,
    };
    const vendorEmail = vi.spyOn(pilotApi, "vendorEmail").mockResolvedValue("should not load");
    const act = vi.fn(async (label: string, action: () => Promise<void>) => {
      void label;
      await action();
    });

    render(<ExportWorkspace reconciliation={noDispute} act={act} />);

    expect(screen.getByText(/No vendor dispute is needed/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Copy vendor dispute email" })).not.toBeInTheDocument();
    await waitFor(() => expect(vendorEmail).not.toHaveBeenCalled());
  });

  it("surfaces the generated vendor dispute email and copies the exact backend output", async () => {
    const email = [
      "Subject: June invoice reconciliation",
      "We reconciled your June invoice against our agreement and customer systems.",
      "Of $150.00 billed, $124.50 is verified. We are disputing $25.50 across 17 claims.",
    ].join("\n\n");
    vi.spyOn(pilotApi, "vendorEmail").mockResolvedValue(email);
    const clipboard = { writeText: vi.fn().mockResolvedValue(undefined) };
    Object.defineProperty(navigator, "clipboard", { configurable: true, value: clipboard });
    const act = vi.fn(async (label: string, action: () => Promise<void>) => {
      void label;
      await action();
    });

    render(<ExportWorkspace reconciliation={reconciliation} act={act} />);

    expect(await screen.findByText(/We reconciled your June invoice/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Copy vendor dispute email" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Download dispute package" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Download disputed lines" })).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Copy vendor dispute email" }));
    await waitFor(() => expect(clipboard.writeText).toHaveBeenCalledWith(email));
  });
});
