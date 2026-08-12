import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { ReactNode } from "react";
import { afterEach, expect, it, vi } from "vitest";
import { track } from "./analytics";
import LandingPage from "./LandingPage";
import { PublicConfigProvider } from "./BetaApplicationCTA";

function Wrapper({ children }: { children: ReactNode }) {
  return <MemoryRouter><PublicConfigProvider>{children}</PublicConfigProvider></MemoryRouter>;
}

vi.mock("./analytics", async (importOriginal) => ({
  ...(await importOriginal<typeof import("./analytics")>()),
  track: vi.fn(),
}));

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
  categories: { R3: { label: "Failed downstream actions", count: 300, amount: "450.00" } },
  synthetic_disclosure: "No real customer or vendor data is shown.",
};

afterEach(() => { vi.restoreAllMocks(); vi.clearAllMocks(); });

function mockPublicConfig(beta = true) {
  vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
    const url = String(input);
    const body = url.endsWith("/api/invoices/current")
      ? invoice
      : url.endsWith("/api/public-config")
        ? { beta_form_configured: beta, beta_form_url: beta ? "https://tally.so/r/test-form" : null, contact_form_configured: true }
        : summary;
    return Promise.resolve({ ok: true, json: () => Promise.resolve(body) } as Response);
  });
}

it("leads with the financial loss and makes the verification loop visible", async () => {
  mockPublicConfig();
  render(<LandingPage />, { wrapper: Wrapper });

  expect(screen.getByRole("heading", { name: /Stop paying AI vendors for outcomes that didn’t happen/i })).toBeInTheDocument();
  expect((await screen.findAllByText("$15,000")).length).toBeGreaterThan(0);
  expect(screen.getAllByText("$12,480").length).toBeGreaterThan(0);
  expect(screen.getAllByText("$2,520").length).toBeGreaterThan(0);
  expect(screen.getByText(/1,680 charges fail approved contract verification/i)).toBeInTheDocument();
  expect(screen.getAllByRole("button", { name: "Verify a sample invoice" }).length).toBeGreaterThan(0);
  expect(screen.getAllByRole("button", { name: "Talk to us" }).length).toBeGreaterThanOrEqual(2);
  expect(screen.getByText("The LLM interprets the contract. It never decides the invoice.")).toBeInTheDocument();
  const talkToUs = screen.getAllByRole("button", { name: "Talk to us" })[0];
  await userEvent.click(talkToUs);
  expect(track).toHaveBeenCalledWith("talk_to_us_clicked");
});

it("keeps direct contact in the header when no beta form is configured", async () => {
  mockPublicConfig(false);
  render(<LandingPage />, { wrapper: Wrapper });
  const talkToUs = screen.getAllByRole("button", { name: "Talk to us" })[0];
  expect(talkToUs.closest("header")).not.toBeNull();
});
