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

const status = {
  public_demo: true,
  seeded: true,
  reconciled: true,
  claimed_outcomes: 10000,
  billing_period: "2026-06-01 through 2026-06-30",
  scenario_id: "headline",
  scenario_name: "Full invoice reconciliation",
  scenario_description: "Headline scenario",
  demo_outcome_id: "OUT-004821",
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
    R3: { label: "Failed downstream actions", count: 300, amount: "450.00" },
  },
  synthetic_disclosure: "No real customer or vendor data is shown.",
};

afterEach(() => {
  vi.restoreAllMocks();
  vi.clearAllMocks();
});

it("states the product and financial result plainly with working launch calls to action", async () => {
  vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
    const url = String(input);
    const body = url.endsWith("/api/demo/status")
      ? status
      : url.endsWith("/api/invoices/current")
        ? invoice
        : url.endsWith("/api/public-config")
          ? { beta_form_configured: true, beta_form_url: "https://tally.so/r/test-form", contact_form_configured: true }
          : summary;
    return Promise.resolve({ ok: true, json: () => Promise.resolve(body) } as Response);
  });

  render(<LandingPage />, { wrapper: Wrapper });

  expect(
    screen.getByText("Evidue checks outcome-priced AI vendor invoices against the contract and the customer’s own system evidence."),
  ).toBeInTheDocument();
  expect(
    await screen.findByText("This technical preview reconciles 10,000 synthetic outcomes and determines that $12,480 of a $15,000 invoice is payable."),
  ).toBeInTheDocument();
  expect(screen.getByRole("button", { name: /Open the \$15,000 reconciliation/ })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Inspect one disputed outcome" })).toBeInTheDocument();
  const betaLink = await screen.findByRole("link", { name: "Apply for the Evidue beta" });
  expect(betaLink).toHaveAttribute(
    "href",
    "https://tally.so/r/test-form?source=unknown&campaign=railway_beta&demo_version=hn_demo",
  );
  expect(betaLink).toHaveAttribute("target", "_blank");
  expect(betaLink).toHaveAttribute("rel", "noopener noreferrer");
  await userEvent.click(betaLink);
  expect(track).toHaveBeenCalledWith("beta_form_opened");
  expect(screen.queryByText("Join the beta waitlist")).not.toBeInTheDocument();
  expect(screen.queryByText("Give feedback")).not.toBeInTheDocument();
  expect(betaLink.closest("header")).not.toBeNull();
  expect(document.querySelector(".landing-cta-band")).not.toBeInTheDocument();
});

it("falls back to direct contact when no beta form is configured", async () => {
  vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
    const url = String(input);
    const body = url.endsWith("/api/demo/status")
      ? status
      : url.endsWith("/api/invoices/current")
        ? invoice
        : url.endsWith("/api/public-config")
          ? { beta_form_configured: false, beta_form_url: null, contact_form_configured: true }
          : summary;
    return Promise.resolve({ ok: true, json: () => Promise.resolve(body) } as Response);
  });

  render(<LandingPage />, { wrapper: Wrapper });

  const contacts = await screen.findAllByRole("link", { name: "Send product feedback" });
  const contact = contacts.find((link) => link.closest("header"));
  if (!contact) throw new Error("Expected feedback link in the persistent header");
  expect(contact).toHaveAttribute("href", "/contact");
  expect(contact.closest("header")).not.toBeNull();
  expect(screen.queryByRole("link", { name: "Apply for the Evidue beta" })).not.toBeInTheDocument();
});
